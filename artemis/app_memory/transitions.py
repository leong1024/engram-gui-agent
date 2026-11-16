from collections.abc import Sequence
from dataclasses import dataclass

from artemis.app_memory.models import HarvestStep, Sighting, Transition


@dataclass(frozen=True, slots=True)
class Scan:
    transitions: tuple[Transition, ...]
    resume_at: int
    """First step a later scan must see again: the open step, or else the newest step,
    because its execution result is written after it is recorded."""


@dataclass(frozen=True, slots=True)
class _Open:
    index: int
    step: HarvestStep
    source: Sighting


def scan(steps: Sequence[HarvestStep], excluded: frozenset[str]) -> Scan:
    transitions: list[Transition] = []
    opened: _Open | None = None
    for index, step in enumerate(steps):
        if step.is_wait:
            continue
        if opened is not None and step.sighting is not None:
            transitions.append(Transition(opened.step, opened.source, step.sighting))
        opened = _open(index, step, excluded)
    resume_at = opened.index if opened else max(len(steps) - 1, 0)
    return Scan(tuple(transitions), resume_at)


def _open(index: int, step: HarvestStep, excluded: frozenset[str]) -> _Open | None:
    sighting = step.sighting
    if not step.actions or sighting is None or sighting.screen.package in excluded:
        return None
    return _Open(index, step, sighting)
