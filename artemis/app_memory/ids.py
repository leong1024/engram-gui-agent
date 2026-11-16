import hashlib
import json
from collections.abc import Sequence

from artemis.app_memory.models import ActionSignature, CanonicalAction, EdgeId, MapId, StateId

OUTSIDE_MARKER = "@outside"


def _sha1(*parts: object) -> str:
    return hashlib.sha1("|".join(str(part) for part in parts).encode()).hexdigest()


def state_id(map_id: MapId, coarse_key: str, cluster_ordinal: int = 0) -> StateId:
    return StateId(_sha1(map_id.package, map_id.version_code, coarse_key, cluster_ordinal))


def outside_state_id(map_id: MapId) -> StateId:
    return StateId(_sha1(map_id.package, map_id.version_code, OUTSIDE_MARKER))


def action_signature(actions: Sequence[CanonicalAction]) -> ActionSignature:
    canonical = json.dumps(
        [a.signature_key() for a in actions], sort_keys=True, separators=(",", ":")
    )
    return ActionSignature(_sha1(canonical))


def edge_id(src: StateId, signature: ActionSignature, dst: StateId) -> EdgeId:
    return EdgeId(_sha1(src, signature, dst))
