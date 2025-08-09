import logging, datetime, pathlib

def get_logger(name: str = "SmartCFD") -> logging.Logger:
    log_dir = pathlib.Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logfile = log_dir / f"{datetime.datetime.now():%Y%m%d}.log"
    logger = logging.getLogger(name)
    if not logger.handlers:
        h1 = logging.StreamHandler()
        h2 = logging.FileHandler(logfile, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        h1.setFormatter(fmt); h2.setFormatter(fmt)
        logger.addHandler(h1); logger.addHandler(h2)
        logger.setLevel(logging.INFO)
        logger.info("Logging to %s", logfile)
    return logger
