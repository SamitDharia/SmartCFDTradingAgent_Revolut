from __future__ import annotations
import os, time, json, logging
import requests
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "").strip()

log = logging.getLogger("telegram")

API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 10
MAX_LEN = 4096  # Telegram hard limit

def _post(text: str) -> bool:
    url = API.format(token=BOT_TOKEN)
    data = {
        "chat_id": CHAT_ID,
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
                print(f"[telegram] request error: {e}")
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
    if not BOT_TOKEN or not CHAT_ID:
        log.warning("Telegram bot token or chat id not set; skipping message")
        return False

    ok_all = True
    for part in _chunks(text):
        ok = _post(part)
        ok_all = ok_all and ok
        if not ok:
            break
        time.sleep(0.2)
    return ok_all
