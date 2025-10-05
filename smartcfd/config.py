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
    offline_behavior: str = "halt"

def load_config() -> AppConfig:
    return AppConfig(
        timezone=os.getenv("TIMEZONE", "Europe/Dublin"),
        alpaca_env=os.getenv("ALPACA_ENV", "paper"),
        api_timeout_seconds=float(os.getenv("API_TIMEOUT_SECONDS", "10")),
        network_max_backoff_seconds=int(os.getenv("NETWORK_MAX_BACKOFF_SECONDS", "60")),
        on_reconnect_reconcile=_as_bool(os.getenv("ON_RECONNECT_RECONCILE", "true")),
        run_container_smoke_test=_as_bool(os.getenv("RUN_CONTAINER_SMOKE_TEST", "1")),
        order_client_id_prefix=os.getenv("ORDER_CLIENT_ID_PREFIX", "SCFD"),
        offline_behavior=os.getenv("OFFLINE_BEHAVIOR", "halt"),
    )

def to_dict(cfg: AppConfig) -> dict:
    return asdict(cfg)
