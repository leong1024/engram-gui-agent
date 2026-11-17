import pytest

from artemis.app_memory import plan_routes, service
from artemis.config.agent import AgentGlobalConfig

HINTS_OFF = AgentGlobalConfig.model_validate({"app_memory": {"hints": {"enabled": False}}})
HINTS_ON = AgentGlobalConfig.model_validate({"app_memory": {"hints": {"enabled": True}}})


@pytest.fixture(autouse=True)
def no_app_memory_enrichment(monkeypatch):
    """Unit runs never describe, embed or select against a real model; tests that need it pass
    fakes."""
    monkeypatch.setattr(service, "open_enrichment", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "open_navigator", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def no_app_memory_hints(monkeypatch):
    """The Operator prompt and the Pro graph stay as they were unless a test turns hints on."""
    monkeypatch.setattr(plan_routes, "load_agent_config", lambda: HINTS_OFF)


@pytest.fixture
def hints_on(monkeypatch):
    monkeypatch.setattr(plan_routes, "load_agent_config", lambda: HINTS_ON)
