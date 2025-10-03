import os
import tempfile

import SmartCFDTradingAgent.emailer as emailer


class DummySMTP:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.logged_in = False
        self.sent = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, user, pwd):
        self.logged_in = True

    def sendmail(self, sender, recipients, msg):
        self.sent = (sender, tuple(recipients), msg)


class DummySMTPSSL(DummySMTP):
    pass


def test_send_email_plain(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_SENDER", "digest@example.com")
    monkeypatch.setenv("DIGEST_EMAILS", "a@example.com")

    dummy = DummySMTP()

    def fake_smtp(host, port):
        assert host == "smtp.example.com"
        assert port == 587
        return dummy

    monkeypatch.setattr(emailer, "smtplib", type("_", (), {"SMTP": fake_smtp, "SMTP_SSL": DummySMTPSSL}))
    result = emailer.send_email("Subject", "Body", None)
    assert result is True
    assert dummy.logged_in is True
    assert dummy.sent[0] == "digest@example.com"


def test_send_email_html_with_attachment(monkeypatch, tmp_path):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_SENDER", "digest@example.com")

    dummy = DummySMTP()

    def fake_smtp(host, port):
        return dummy

    monkeypatch.setattr(emailer, "smtplib", type("_", (), {"SMTP": fake_smtp, "SMTP_SSL": DummySMTPSSL}))
    attachment = tmp_path / "chart.png"
    attachment.write_bytes(b"fake")
    result = emailer.send_email(
        "Subject",
        "Plain",
        ["x@example.com"],
        html_body="<b>HTML</b>",
        attachments=[attachment],
    )
    assert result is True
    assert dummy.sent is not None


def test_send_email_requires_credentials(monkeypatch):
    for key in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_SENDER"]:
        monkeypatch.delenv(key, raising=False)
    try:
        emailer.send_email("Sub", "Body", ["x@example.com"])
    except RuntimeError as exc:
        assert "SMTP credentials" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
