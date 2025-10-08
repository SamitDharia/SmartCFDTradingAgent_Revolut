from dataclasses import dataclass, asdict
import os

def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")

@dataclass
class AppConfig:
    timezone: str = "Europe/Dublin"
    alpaca_env: str = "paper"
    api_timeout_seconds: float = 10.0
    network_max_backoff_seconds: int = 60
    on_reconnect_reconcile: bool = True
    run_container_smoke_test: bool = True
    order_client_id_prefix: str = "SCFD"
    run_interval_seconds: int = 60
    offline_behavior: str = "halt"
    watch_list: str = "BTC/USD" # Comma-separated list of symbols
    trade_interval: str = "15m" # Interval for trading data
    max_data_staleness_minutes: int = 30 # Max age of data before it's considered stale
    feed: str = "iex" # Default feed


@dataclass
class RiskConfig:
    max_daily_drawdown_percent: float = -5.0  # e.g. -5.0 for a 5% loss
    max_total_exposure_percent: float = 50.0 # Max total notional value as a % of equity
    max_exposure_per_asset_percent: float = 25.0 # Max notional value per asset as a % of equity
    risk_per_trade_percent: float = 1.0 # Risk 1% of equity per trade
    stop_loss_atr_multiplier: float = 2.5 # e.g., 2.5x ATR for stop-loss distance
    take_profit_atr_multiplier: float = 4.0 # e.g. 4.0 for a 4% take-profit from entry
    correlation_threshold: float = 0.8 # Threshold to consider assets highly correlated
    circuit_breaker_atr_multiplier: float = 3.0 # 0 means disabled. 3.0 means halt if ATR is 3x the recent average.
    min_order_notional: float = 1.0 # Minimum notional value for an order

def load_risk_config() -> RiskConfig:
    return RiskConfig(
        max_daily_drawdown_percent=float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", "-5.0")),
        max_total_exposure_percent=float(os.getenv("MAX_TOTAL_EXPOSURE_PERCENT", "50.0")),
        max_exposure_per_asset_percent=float(os.getenv("MAX_EXPOSURE_PER_ASSET_PERCENT", "25.0")),
        risk_per_trade_percent=float(os.getenv("RISK_PER_TRADE_PERCENT", "1.0")),
        stop_loss_atr_multiplier=float(os.getenv("STOP_LOSS_ATR_MULTIPLIER", "2.5")),
        take_profit_atr_multiplier=float(os.getenv("TAKE_PROFIT_ATR_MULTIPLIER", "4.0")),
        correlation_threshold=float(os.getenv("CORRELATION_THRESHOLD", "0.8")),
        circuit_breaker_atr_multiplier=float(os.getenv("CIRCUIT_BREAKER_ATR_MULTIPLIER", "3.0")),
        min_order_notional=float(os.getenv("MIN_ORDER_NOTIONAL", "1.0")),
    )

def load_config() -> AppConfig:
    return AppConfig(
        timezone=os.getenv("TIMEZONE", "Europe/Dublin"),
        alpaca_env=os.getenv("ALPACA_ENV", "paper"),
        api_timeout_seconds=float(os.getenv("API_TIMEOUT_SECONDS", "10")),
        network_max_backoff_seconds=int(os.getenv("NETWORK_MAX_BACKOFF_SECONDS", "60")),
        on_reconnect_reconcile=_as_bool(os.getenv("ON_RECONNECT_RECONCILE", "true")),
        run_container_smoke_test=_as_bool(os.getenv("RUN_CONTAINER_SMOKE_TEST", "1")),
        order_client_id_prefix=os.getenv("ORDER_CLIENT_ID_PREFIX", "SCFD"),
        run_interval_seconds=int(os.getenv("RUN_INTERVAL_SECONDS", "60")),
        offline_behavior=os.getenv("OFFLINE_BEHAVIOR", "halt"),
        watch_list=os.getenv("WATCH_LIST", "BTC/USD"),
        trade_interval=os.getenv("TRADE_INTERVAL", "15m"),
        max_data_staleness_minutes=int(os.getenv("MAX_DATA_STALENESS_MINUTES", "30")),
    )

def to_dict(cfg: AppConfig) -> dict:
    return asdict(cfg)
