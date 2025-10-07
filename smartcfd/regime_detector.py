import pandas as pd
import logging
from enum import Enum

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
    def __init__(self, short_window: int = 20, long_window: int = 100, threshold_multiplier: float = 1.25):
        """
        Initializes the RegimeDetector.

        :param short_window: The window for the short-term ATR.
        :param long_window: The window for the long-term ATR.
        :param threshold_multiplier: The multiplier to determine the high volatility threshold.
                                     If short_atr > long_atr * multiplier, it's high volatility.
        """
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
            
        self.short_window = short_window
        self.long_window = long_window
        self.threshold_multiplier = threshold_multiplier

    def detect_regime(self, historical_data: pd.DataFrame) -> MarketRegime:
        """
        Detects the market regime from historical data.

        :param historical_data: A DataFrame with 'High', 'Low', and 'Close' columns.
        :return: The detected MarketRegime.
        """
        log.info("regime_detector.detect_regime.start")
        
        if historical_data is None or len(historical_data) < self.long_window:
            log.warning(
                "regime_detector.detect_regime.insufficient_data",
                extra={"extra": {"data_length": len(historical_data) if historical_data is not None else 0, "required": self.long_window}}
            )
            return MarketRegime.UNDEFINED

        try:
            # Calculate short-term and long-term ATR
            short_atr = atr(historical_data['high'], historical_data['low'], historical_data['close'], window=self.short_window).iloc[-1]
            long_atr = atr(historical_data['high'], historical_data['low'], historical_data['close'], window=self.long_window).iloc[-1]

            if pd.isna(short_atr) or pd.isna(long_atr) or long_atr == 0:
                log.warning("regime_detector.detect_regime.atr_calculation_failed")
                return MarketRegime.UNDEFINED

            # Determine the regime
            threshold = long_atr * self.threshold_multiplier
            current_regime = MarketRegime.HIGH_VOLATILITY if short_atr > threshold else MarketRegime.LOW_VOLATILITY

            log.info(
                "regime_detector.detect_regime.result",
                extra={
                    "extra": {
                        "regime": current_regime.value,
                        "short_atr": short_atr,
                        "long_atr": long_atr,
                        "threshold": threshold,
                    }
                },
            )
            return current_regime

        except Exception:
            log.error("regime_detector.detect_regime.fail", exc_info=True)
            return MarketRegime.UNDEFINED
