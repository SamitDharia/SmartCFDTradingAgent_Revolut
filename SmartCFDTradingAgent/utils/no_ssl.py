# SmartCFDTradingAgent/utils/no_ssl.py
# Force yfinance to use requests (not libcurl) and ignore corporate MITM certs.
from __future__ import annotations
import os, ssl, requests, urllib3
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
print("[no_ssl] SSL verification disabled for Yahoo requests.")

# Must be set BEFORE yfinance is imported anywhere
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("YF_DISABLE_CURL", "1")

try:
    import yfinance as yf  # noqa
    # yfinance uses a shared requests session; make it skip verification
    sess = getattr(yf.shared, "_requests", None) or requests.Session()
    sess.verify = False
    sess.headers.setdefault('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    sess.headers.setdefault('Accept', 'application/json, text/plain, */*')
    sess.headers.setdefault('Accept-Language', 'en-US,en;q=0.9')

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



try:
    _orig_request = requests.Session.request
except AttributeError:  # pragma: no cover - requests may be stubbed in tests
    _orig_request = None
else:

    def _unsafe_request(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        return _orig_request(self, *args, **kwargs)

    requests.Session.request = _unsafe_request



