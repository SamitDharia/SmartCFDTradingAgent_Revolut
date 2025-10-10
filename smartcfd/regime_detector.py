import pandas as pd
from typing import TYPE_CHECKING
import logging
from enum import Enum

if TYPE_CHECKING:
    from .config import RegimeConfig, AppConfig

from smartcfd.indicators import atr

log = logging.getLogger(__name__)

class MarketRegime(Enum):
    """
    Defines the possible market regimes.
    """
    LOW_VOLATILITY = "low_volatility"
    HIGH_VOLATILITY = "high_volatility"
    UNDEFINED = "undefined"

class RegimeDetector:
    """
    Detects the current market regime based on historical data.
    """
    def __init__(self, app_config: "AppConfig", regime_config: "RegimeConfig"):
        self.short_window = regime_config.short_window
        self.long_window = regime_config.long_window
        self.min_data_points = app_config.min_data_points
        # Threshold multiplier to compare short ATR to long ATR
        self.threshold_multiplier = getattr(regime_config, 'threshold_multiplier', 1.5)
        
        if self.short_window >= self.long_window:
            raise ValueError("Short window must be smaller than long window for regime detection.")

    def detect(self, data: pd.DataFrame) -> MarketRegime:
        """
        Detects the market regime for a given dataset.

        :param data: A DataFrame with 'High', 'Low', and 'Close' columns.
        :return: The detected MarketRegime.
        """
        if data is None or len(data) < self.min_data_points:
            log.warning(
                "regime_detector.detect.insufficient_data",
                extra={"extra": {"rows": len(data) if data is not None else 0, "required": self.min_data_points}}
            )
            return MarketRegime.UNDEFINED

        # Additional check to prevent IndexError in ATR calculation
        if len(data) < self.long_window:
            log.warning(
                "regime_detector.detect.insufficient_data_for_long_window",
                extra={"extra": {"rows": len(data), "required": self.long_window}}
            )
            return MarketRegime.UNDEFINED

        try:
            # Calculate short-term and long-term ATR
            short_atr = atr(data['high'], data['low'], data['close'], window=self.short_window).iloc[-1]
            long_atr = atr(data['high'], data['low'], data['close'], window=self.long_window).iloc[-1]

            if pd.isna(short_atr) or pd.isna(long_atr) or long_atr == 0:
                log.warning("regime_detector.detect_regime.atr_calculation_failed")
                return MarketRegime.UNDEFINED

            # Determine the regime
            threshold = long_atr * self.threshold_multiplier
            current_regime = MarketRegime.HIGH_VOLATILITY if short_atr > threshold else MarketRegime.LOW_VOLATILITY

            return current_regime

        except Exception:
            log.error("regime_detector.detect_regime.fail", exc_info=True)
            return MarketRegime.UNDEFINED
