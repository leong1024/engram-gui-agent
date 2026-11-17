import pydantic
import pytest

from artemis.app_memory.knowledge import render
from artemis.app_memory.knowledge.reports import (
    KnowledgeResponse,
    Level,
    ProbeCandidate,
    ProbeResult,
    ProbeStatus,
)

DISPLAY = ProbeCandidate(
    package="com.android.settings",
    version_code=34,
    page="Display",
    similarity=0.5669,
    hops_from_launch=2,
    borrowed=False,
)
SOUND = DISPLAY.model_copy(update={"page": "Sound", "similarity": 0.4, "hops_from_launch": None})
OLD_HOME = DISPLAY.model_copy(
    update={"version_code": 33, "page": "Home", "similarity": 0.36, "hops_from_launch": 1}
)
SCOPE = "This covers only what Engram has seen in past runs, not everything an app can do.\n"


def test_found_probe_golden():
    result = ProbeResult(
        query="turn on\ndark theme", status=ProbeStatus.FOUND, candidates=(DISPLAY, SOUND)
    )
    assert render(result) == (
        '# Route probe for "turn on dark theme"\n'
        "\n"
        "Engram has seen pages close to this goal.\n"
        "Similarity is how close a page's description is to the goal in a vector search. "
        "It is not a promise that a task will succeed, and a real run can pick another page.\n"
        f"{SCOPE}"
        "\n"
        "Closest pages, most similar first:\n"
        "- Display in `com.android.settings` version_code 34: similarity 0.57, "
        "2 hops from launch\n"
        "- Sound in `com.android.settings` version_code 34: similarity 0.40, "
        "no known route from launch\n"
        "\n"
        "Next: run the task with the goal worded like the top page. "
        "Pass `app` with its package to see what else Engram has seen there."
    )


def test_a_borrowed_candidate_says_it_comes_from_an_older_version():
    borrowed = OLD_HOME.model_copy(update={"borrowed": True})
    text = render(ProbeResult(query="q", status=ProbeStatus.FOUND, candidates=(borrowed,)))
    assert (
        "- Home in `com.android.settings` version_code 33: similarity 0.36, 1 hop from launch, "
        "from an older version because the newest had no match\n"
    ) in text


def test_no_match_probe_golden():
    assert render(ProbeResult(query="order a pizza", status=ProbeStatus.NO_MATCH)) == (
        '# Route probe for "order a pizza"\n'
        "\n"
        "No page Engram has seen is close enough to this goal.\n"
        f"{SCOPE}"
        "\n"
        "Next: call with no arguments to list the apps Engram knows, and word the goal like "
        "what they offer. A task can still run without a known route."
    )


@pytest.mark.parametrize("status", list(ProbeStatus))
def test_every_status_renders_without_claiming_confidence(status):
    candidates = (DISPLAY,) if status is ProbeStatus.FOUND else ()
    text = render(ProbeResult(query="q", status=status, candidates=candidates))
    assert text.splitlines()[-1].startswith("Next: ")
    assert "confidence" not in text.lower()


def test_the_response_holds_a_probe_at_the_probe_level():
    result = ProbeResult(query="q", status=ProbeStatus.FOUND, candidates=(DISPLAY,))
    response = KnowledgeResponse.of(result)
    assert (response.level, response.probe, response.overview) == (Level.PROBE, result, None)
    with pytest.raises(pydantic.ValidationError):
        KnowledgeResponse(level=Level.OVERVIEW, probe=result)


@pytest.mark.parametrize(
    ("status", "candidates"),
    [(ProbeStatus.FOUND, ()), (ProbeStatus.NO_MATCH, (DISPLAY,))],
)
def test_only_a_found_probe_holds_candidates(status, candidates):
    with pytest.raises(pydantic.ValidationError):
        ProbeResult(query="q", status=status, candidates=candidates)
