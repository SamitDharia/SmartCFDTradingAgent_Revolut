import logging
import logging.config
import sys

def setup_logging(level: str = "INFO") -> None:
    """
    Set up logging using a dictionary configuration for robustness.
    This ensures our JSON formatter is used consistently.
    """
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            },
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "json",
            },
        },
        "root": {
            "level": level.upper(),
            "handlers": ["console"],
        },
        "loggers": {
            "urllib3": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "requests": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(LOGGING_CONFIG)
