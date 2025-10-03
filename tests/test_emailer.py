import SmartCFDTradingAgent.emailer as emailer


class DummySMTP:
    def __init__(self, *args, **kwargs):
        self.called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, user, pwd):
        self.called = True

    def sendmail(self, sender, recipients, msg):
        self.sent = (sender, tuple(recipients))


class DummySMTPSSL(DummySMTP):
    pass


def test_send_email(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_SENDER", "digest@example.com")
    dummy = DummySMTP()
    monkeypatch.setenv("DIGEST_EMAILS", "a@example.com,b@example.com")

    def fake_smtp(host, port):
        assert host == "smtp.example.com"
        assert port == 587
        return dummy

    monkeypatch.setattr(emailer, "smtplib", type("_", (), {"SMTP": fake_smtp, "SMTP_SSL": DummySMTPSSL}))
    result = emailer.send_email("Subject", "Body", None)
    assert result is True
    assert dummy.called is True


def test_send_email_without_recipients(monkeypatch):
    monkeypatch.delenv("DIGEST_EMAILS", raising=False)
    result = emailer.send_email("Sub", "Body", [])
    assert result is False


def test_send_email_requires_credentials(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    try:
        emailer.send_email("Sub", "Body", ["x@example.com"])
    except RuntimeError as exc:
        assert "SMTP credentials" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
