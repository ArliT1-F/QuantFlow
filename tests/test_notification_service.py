import pytest

from app.core.config import settings
from app.services.notification_service import NotificationService


class DummySMTP:
    def __init__(self):
        self.logged_in = False
        self.sent = False
        self.last_from = None
        self.last_to = None
        self.last_text = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        return None

    def login(self, user, password):
        self.logged_in = bool(user and password)

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent = True
        self.last_from = from_addr
        self.last_to = to_addrs
        self.last_text = msg


@pytest.mark.asyncio
async def test_send_email_uses_configured_recipient_list(monkeypatch):
    smtp = DummySMTP()
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "EMAIL_PORT", 587)
    monkeypatch.setattr(settings, "EMAIL_USER", "bot@example.com")
    monkeypatch.setattr(settings, "EMAIL_PASSWORD", "secret")
    monkeypatch.setattr(settings, "EMAIL_TO", ["ops@example.com", "alerts@example.com"])
    monkeypatch.setattr(
        "app.services.notification_service.smtplib.SMTP",
        lambda host, port, timeout=None: smtp,
    )

    service = NotificationService()
    sent = await service.send_alert("Test", "Body", "LOW")

    assert sent
    assert smtp.logged_in
    assert smtp.sent
    assert smtp.last_to == ["ops@example.com", "alerts@example.com"]
