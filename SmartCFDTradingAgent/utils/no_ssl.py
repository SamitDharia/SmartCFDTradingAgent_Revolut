# SmartCFDTradingAgent/utils/no_ssl.py
# Force yfinance to use requests (not libcurl) and ignore corporate MITM certs.
from __future__ import annotations
import os, ssl, requests

# Must be set BEFORE yfinance is imported anywhere
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("YF_DISABLE_CURL", "1")

try:
    import yfinance as yf  # noqa
    # yfinance uses a shared requests session; make it skip verification
    sess = getattr(yf.shared, "_requests", None) or requests.Session()
    sess.verify = False

    class UnsafeAdapter(requests.adapters.HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["ssl_context"] = ctx
            return super().init_poolmanager(*args, **kwargs)
        def proxy_manager_for(self, *args, **kwargs):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["ssl_context"] = ctx
            return super().proxy_manager_for(*args, **kwargs)

    sess.mount("https://", UnsafeAdapter())
    yf.shared._requests = sess
except Exception:
    # If anything above fails, we still benefit from env vars.
    pass
