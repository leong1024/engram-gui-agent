import pytest

from artemis.config.llm import LLMConfig, _expand_default_into_nodes

DEFAULT = {
    "provider": "google",
    "model": "gemini-default",
    "fallback": {"provider": "google", "model": "gemini-default-fallback"},
}


def resolve(nodes: dict) -> LLMConfig:
    return LLMConfig.model_validate(
        _expand_default_into_nodes({"default": DEFAULT, "nodes": nodes})
    )


def test_a_planner_validation_override_changes_the_resolved_model():
    assert resolve({}).get_agent("planner_validation").model == "gemini-3.5-flash-lite"

    config = resolve({"planner_validation": {"model": "gemini-judge"}})

    resolved = config.get_agent("planner_validation")
    assert resolved.model == "gemini-judge"
    assert resolved.temperature == 0.0
    assert resolved.fallback.model == "gemini-3.1-flash-lite"


@pytest.mark.parametrize(
    ("node", "inherits"), [("history_analyzer", "operator"), ("output_analyzer", "log_analyzer")]
)
def test_an_optional_node_override_merges_onto_the_node_it_inherits(node, inherits):
    config = resolve({inherits: {"thinking_level": "high"}, node: {"model": "override"}})

    resolved = config.get_agent(node)
    assert (resolved.model, resolved.thinking_level) == ("override", "high")
    assert resolve({}).get_agent(node) == resolve({}).get_agent(inherits)


@pytest.mark.parametrize("node", ["app_memory_describer", "app_memory_selector"])
def test_app_memory_nodes_default_to_the_run_default_and_take_overrides(node):
    assert resolve({}).get_agent(node).model == "gemini-default"
    assert resolve({node: {"model": "other"}}).get_agent(node).model == "other"


def test_an_unknown_node_name_is_reported(caplog):
    resolve({"planer": {"model": "typo"}})

    assert "planer" in caplog.text
