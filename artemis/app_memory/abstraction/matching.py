from collections import Counter
from collections.abc import Collection, Iterable, Sequence

from artemis.app_memory.abstraction.constants import (
    MATCH_THRESHOLD,
    MAX_DHASH_DISTANCE,
    OVERLAY_PREFIX,
    SKELETON_WEIGHT,
    STATIC_TOKENS_WEIGHT,
    TAB_PREFIX,
)
from artemis.app_memory.models import AbstractScreen, KnownState, StateId
from artemis.utils.image_hash import hamming_distance_hex


def match(screen: AbstractScreen, candidates: Sequence[KnownState]) -> StateId | None:
    if screen.is_opaque:
        return _match_opaque(screen, [c for c in candidates if c.screen.is_opaque])
    return _match_structural(screen, [c for c in candidates if not c.screen.is_opaque])


def _match_structural(screen: AbstractScreen, candidates: Sequence[KnownState]) -> StateId | None:
    same_key = [c for c in candidates if c.screen.coarse_key == screen.coarse_key]
    if len(same_key) == 1:
        return same_key[0].state_id
    pool = same_key or [c for c in candidates if _comparable(screen, c.screen)]
    scored = [(similarity(screen, c.screen), c.state_id) for c in pool]
    qualifying = [(-score, state_id) for score, state_id in scored if score >= MATCH_THRESHOLD]
    return min(qualifying)[1] if qualifying else None


def _comparable(screen: AbstractScreen, other: AbstractScreen) -> bool:
    same_activity = screen.activity is None or screen.activity == other.activity
    return same_activity and _markers(screen) == _markers(other)


def _markers(screen: AbstractScreen) -> tuple[str, ...]:
    return tuple(t for t in screen.skeleton if t.startswith((OVERLAY_PREFIX, TAB_PREFIX)))


def similarity(a: AbstractScreen, b: AbstractScreen) -> float:
    return SKELETON_WEIGHT * _multiset_jaccard(a.skeleton, b.skeleton) + (
        STATIC_TOKENS_WEIGHT * _jaccard(a.static_tokens, b.static_tokens)
    )


def _jaccard(a: Collection[str], b: Collection[str]) -> float:
    union = set(a) | set(b)
    return len(set(a) & set(b)) / len(union) if union else 1.0


def _multiset_jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    left, right = Counter(a), Counter(b)
    union = sum((left | right).values())
    return sum((left & right).values()) / union if union else 1.0


def _match_opaque(screen: AbstractScreen, candidates: Sequence[KnownState]) -> StateId | None:
    ranked = []
    for candidate in candidates:
        distance = hamming_distance_hex(screen.dhash, candidate.screen.dhash)
        if distance is not None and distance <= MAX_DHASH_DISTANCE:
            overlap = _jaccard(screen.ocr_tokens, candidate.screen.ocr_tokens)
            ranked.append((distance, -overlap, candidate.state_id))
    return min(ranked)[2] if ranked else None
