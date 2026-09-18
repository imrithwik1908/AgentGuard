import pytest


def test_production_refuses_disabled_auth(monkeypatch):
    from agentguard_api.core.config import get_settings

    monkeypatch.setenv("AGENTGUARD_ENVIRONMENT", "production")
    monkeypatch.setenv("AGENTGUARD_AUTH_REQUIRED", "false")
    monkeypatch.setenv("AGENTGUARD_EVALUATION_QUEUE_BACKEND", "redis")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="AUTH_REQUIRED"):
        from agentguard_api.main import create_app

        create_app()

    get_settings.cache_clear()


def test_production_refuses_inline_evaluation_queue(monkeypatch):
    from agentguard_api.core.config import get_settings

    monkeypatch.setenv("AGENTGUARD_ENVIRONMENT", "production")
    monkeypatch.setenv("AGENTGUARD_AUTH_REQUIRED", "true")
    monkeypatch.setenv("AGENTGUARD_EVALUATION_QUEUE_BACKEND", "inline")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="EVALUATION_QUEUE_BACKEND=redis"):
        from agentguard_api.main import create_app

        create_app()

    get_settings.cache_clear()
