from __future__ import annotations

import os
import time
import json

import requests
from dotenv import load_dotenv

from SmartCFDTradingAgent.utils.logger import get_logger


log = logging.getLogger(__name__)


API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 10
MAX_LEN = 4096  # Telegram hard limit


def _load_creds() -> tuple[str, str]:
    """Return the bot token and chat id from the environment.

    Environment variables are read fresh each call.  If either credential is
    missing we intentionally **do not** load ``.env`` to avoid accidentally
    picking up real credentials during tests.  An optional ``TELEGRAM_DISABLE``
    flag can be set to opt‑out entirely.
    """

    if os.getenv("TELEGRAM_DISABLE", "").strip().lower() in {"1", "true", "yes"}:
        return "", ""

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        # No credentials in the environment; skip loading from .env
        return "", ""

    # Re-load .env in case values changed; skipped when creds are absent
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return token, chat_id


def _post(text: str, token: str, chat_id: str) -> bool:
    url = API.format(token=token)
    data = {
        "chat_id": chat_id,
        "text": text,
        # IMPORTANT: no parse_mode → plain text (avoids 'can't parse entities' 400)
        "disable_web_page_preview": True,
        "allow_sending_without_reply": True,
    }
    # small retry loop (handles 429 / transient)
    for attempt in range(4):
        try:
            r = requests.post(url, data=data, timeout=TIMEOUT)
        except Exception as e:
            if attempt == 3:

                log.warning("[telegram] request error: %s", e)

                return False
            time.sleep(1.5 * (attempt + 1))
            continue

        if r.status_code == 200:
            return True

        # 429 backoff if Telegram tells us how long to wait
        if r.status_code == 429:
            try:
                j = r.json()
                retry_after = j.get("parameters", {}).get("retry_after", 2)
            except Exception:
                retry_after = 2
            time.sleep(float(retry_after) + 0.5)
            continue

        # other error
        try:
            body = r.json()
        except Exception:
            body = r.text
        log.error("HTTP %s %s", r.status_code, body)
        return False
    return False

def _chunks(text: str, max_len: int = MAX_LEN):
    # Split on line boundaries where possible
    if len(text) <= max_len:
        yield text
        return
    lines = text.splitlines(keepends=True)
    buf = ""
    for ln in lines:
        if len(buf) + len(ln) <= max_len:
            buf += ln
        else:
            if buf:
                yield buf
            if len(ln) <= max_len:
                buf = ln
            else:
                # very long single line: hard split
                for i in range(0, len(ln), max_len):
                    yield ln[i:i+max_len]
                buf = ""
    if buf:
        yield buf

def send(text: str) -> bool:
    token, chat_id = _load_creds()
    if not token or not chat_id:
        log.warning("Telegram bot token or chat id not set; skipping message")
        return False

    ok_all = True
    for part in _chunks(text):
        ok = _post(part, token, chat_id)
        ok_all = ok_all and ok
        if not ok:
            break
        time.sleep(0.2)
    return ok_all
