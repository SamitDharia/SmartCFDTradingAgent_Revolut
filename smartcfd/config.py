from dataclasses import dataclass, asdict
import os
import configparser

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
    run_interval_seconds: int = 300
    offline_behavior: str = "halt"
    watch_list: str = "BTC/USD" # Comma-separated list of symbols
    trade_interval: str = "15m" # Interval for trading data
    max_data_staleness_minutes: int = 30 # Max age of data before it's considered stale
    feed: str = "iex" # Default feed
    min_data_points: int = 400 # Minimum data points for regime detection
    trade_confidence_threshold: float = 0.75 # Minimum confidence for a trade


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

@dataclass
class AlpacaConfig:
    api_key: str
    secret_key: str

def load_config_from_file(path: str = 'config.ini') -> tuple[AppConfig, RiskConfig, AlpacaConfig]:
    """Loads configuration from a .ini file."""
    parser = configparser.ConfigParser()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found at {path}. Please create it from config.ini.example.")
    
    parser.read(path)

    # --- Load AppConfig ---
    app_cfg = AppConfig(
        timezone=parser.get('settings', 'timezone', fallback=os.getenv("TIMEZONE", "Europe/Dublin")),
        alpaca_env=parser.get('settings', 'alpaca_env', fallback=os.getenv("ALPACA_ENV", "paper")),
        api_timeout_seconds=parser.getfloat('settings', 'api_timeout_seconds', fallback=float(os.getenv("API_TIMEOUT_SECONDS", "10"))),
        network_max_backoff_seconds=parser.getint('settings', 'network_max_backoff_seconds', fallback=int(os.getenv("NETWORK_MAX_BACKOFF_SECONDS", "60"))),
        on_reconnect_reconcile=parser.getboolean('settings', 'on_reconnect_reconcile', fallback=_as_bool(os.getenv("ON_RECONNECT_RECONCILE", "true"))),
        run_container_smoke_test=parser.getboolean('settings', 'run_container_smoke_test', fallback=_as_bool(os.getenv("RUN_CONTAINER_SMOKE_TEST", "1"))),
        order_client_id_prefix=parser.get('settings', 'order_client_id_prefix', fallback=os.getenv("ORDER_CLIENT_ID_PREFIX", "SCFD")),
        run_interval_seconds=parser.getint('settings', 'run_interval_seconds', fallback=int(os.getenv("RUN_INTERVAL_SECONDS", "60"))),
        offline_behavior=parser.get('settings', 'offline_behavior', fallback=os.getenv("OFFLINE_BEHAVIOR", "halt")),
        watch_list=parser.get('settings', 'watch_list', fallback=os.getenv("WATCH_LIST", "BTC/USD")),
        trade_interval=parser.get('settings', 'trade_interval', fallback=os.getenv("TRADE_INTERVAL", "15m")),
        max_data_staleness_minutes=parser.getint('settings', 'max_data_staleness_minutes', fallback=int(os.getenv("MAX_DATA_STALENESS_MINUTES", "30"))),
        feed=parser.get('settings', 'feed', fallback=os.getenv("FEED", "iex")),
        min_data_points=parser.getint('settings', 'min_data_points', fallback=int(os.getenv("MIN_DATA_POINTS", "400"))),
        trade_confidence_threshold=parser.getfloat('settings', 'trade_confidence_threshold', fallback=float(os.getenv("TRADE_CONFIDENCE_THRESHOLD", "0.75"))),
    )

    # --- Load RiskConfig ---
    risk_cfg = RiskConfig(
        max_daily_drawdown_percent=parser.getfloat('risk', 'max_daily_drawdown_percent', fallback=float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", "-5.0"))),
        max_total_exposure_percent=parser.getfloat('risk', 'max_total_exposure_percent', fallback=float(os.getenv("MAX_TOTAL_EXPOSURE_PERCENT", "50.0"))),
        max_exposure_per_asset_percent=parser.getfloat('risk', 'max_exposure_per_asset_percent', fallback=float(os.getenv("MAX_EXPOSURE_PER_ASSET_PERCENT", "25.0"))),
        risk_per_trade_percent=parser.getfloat('risk', 'risk_per_trade_percent', fallback=float(os.getenv("RISK_PER_TRADE_PERCENT", "1.0"))),
        stop_loss_atr_multiplier=parser.getfloat('risk', 'stop_loss_atr_multiplier', fallback=float(os.getenv("STOP_LOSS_ATR_MULTIPLIER", "2.5"))),
        take_profit_atr_multiplier=parser.getfloat('risk', 'take_profit_atr_multiplier', fallback=float(os.getenv("TAKE_PROFIT_ATR_MULTIPLIER", "4.0"))),
        correlation_threshold=parser.getfloat('risk', 'correlation_threshold', fallback=float(os.getenv("CORRELATION_THRESHOLD", "0.8"))),
        circuit_breaker_atr_multiplier=parser.getfloat('risk', 'circuit_breaker_atr_multiplier', fallback=float(os.getenv("CIRCUIT_BREAKER_ATR_MULTIPLIER", "3.0"))),
        min_order_notional=parser.getfloat('risk', 'min_order_notional', fallback=float(os.getenv("MIN_ORDER_NOTIONAL", "1.0"))),
    )

    # --- Load AlpacaConfig ---
    alpaca_api_key = parser.get('alpaca', 'api_key', fallback=os.getenv('APCA_API_KEY_ID'))
    alpaca_secret_key = parser.get('alpaca', 'secret_key', fallback=os.getenv('APCA_API_SECRET_KEY'))

    if not alpaca_api_key or 'YOUR' in alpaca_api_key:
        raise ValueError("Alpaca API key is not configured in config.ini or environment variables.")
    if not alpaca_secret_key or 'YOUR' in alpaca_secret_key:
        raise ValueError("Alpaca secret key is not configured in config.ini or environment variables.")

    alpaca_cfg = AlpacaConfig(api_key=alpaca_api_key, secret_key=alpaca_secret_key)

    return app_cfg, risk_cfg, alpaca_cfg

def to_dict(cfg: AppConfig) -> dict:
    return asdict(cfg)
