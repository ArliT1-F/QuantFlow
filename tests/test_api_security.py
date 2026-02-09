import pytest
from fastapi import HTTPException

from app.api.security import require_api_key
from app.core.config import settings


@pytest.mark.asyncio
async def test_require_api_key_disabled_allows_request(monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", False)
    await require_api_key(None)


@pytest.mark.asyncio
async def test_require_api_key_rejects_missing_or_invalid_key(monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "secret-token")

    with pytest.raises(HTTPException) as missing_exc:
        await require_api_key(None)
    assert missing_exc.value.status_code == 401

    with pytest.raises(HTTPException) as invalid_exc:
        await require_api_key("wrong")
    assert invalid_exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_api_key_accepts_valid_key(monkeypatch):
    monkeypatch.setattr(settings, "API_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "secret-token")
    await require_api_key("secret-token")
