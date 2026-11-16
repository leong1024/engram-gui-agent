import pytest

from artemis.app_memory import service


@pytest.fixture(autouse=True)
def no_app_memory_enrichment(monkeypatch):
    """Unit runs never describe, embed or select against a real model; tests that need it pass
    fakes."""
    monkeypatch.setattr(service, "open_enrichment", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "open_navigator", lambda *args, **kwargs: None)
