import base64
import hashlib
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from artemis.app_memory.models import ScreenObservation
from artemis.app_memory.trace_reader import screen_observation
from artemis.utils.image_hash import dhash_hex

if TYPE_CHECKING:
    from artemis.data_engine.engine import DataEngine


def current_screen(
    engine: "DataEngine | None", perception: Mapping[str, Any] | None
) -> ScreenObservation | None:
    """The screen the Operator sees now, built from the same keys a recorded step carries, so it
    localizes against the map exactly as a harvested step would."""
    if engine is None or not perception:
        return None
    tree = perception.get("xml_hierarchy")
    image = base64.b64decode(perception.get("screenshot_b64") or "")
    identity = engine.screen_identity(hashlib.sha256(image).hexdigest(), tree)
    extra = {
        **identity,
        "pre_image_dhash": dhash_hex(image),
        "width": perception.get("width"),
        "height": perception.get("height"),
    }
    return screen_observation(extra, tree)
