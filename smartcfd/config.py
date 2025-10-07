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

@dataclass
class RiskConfig:
    max_daily_drawdown_percent: float = -5.0  # e.g. -5.0 for a 5% loss
    max_position_size: float = 10000.0  # Max notional value for a single position
    max_total_exposure: float = 25000.0  # Max total notional value of all positions
    risk_per_trade_percent: float = 0.01 # Risk 1% of equity per trade
    circuit_breaker_atr_multiplier: float = 0.0 # 0 means disabled

def load_risk_config() -> RiskConfig:
    return RiskConfig(
        max_daily_drawdown_percent=float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", "-5.0")),
        max_position_size=float(os.getenv("MAX_POSITION_SIZE", "10000.0")),
        max_total_exposure=float(os.getenv("MAX_TOTAL_EXPOSURE", "25000.0")),
        risk_per_trade_percent=float(os.getenv("RISK_PER_TRADE_PERCENT", "0.01")),
        circuit_breaker_atr_multiplier=float(os.getenv("CIRCUIT_BREAKER_ATR_MULTIPLIER", "0.0")),
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
    )

def to_dict(cfg: AppConfig) -> dict:
    return asdict(cfg)
