import itertools
from dataclasses import dataclass, field
from pathlib import Path

from artemis.app_memory import ids
from artemis.app_memory.abstraction import abstract
from artemis.app_memory.models import (
    ActionKind,
    CanonicalAction,
    EdgeId,
    MapId,
    ObservationRecord,
    ObservationStatus,
    ScreenObservation,
    StateId,
    TargetDescriptor,
)
from artemis.app_memory.store import MapStore
from tests.unit.app_memory.fixtures.parts import SETTINGS, element

SETTINGS_MAP = MapId(SETTINGS, 34)
NOW = 1_700_000_000.0
ROWS = 4


def tap(
    text: str, resource_id: str | None = None, class_name: str | None = None
) -> CanonicalAction:
    target = TargetDescriptor(resource_id=resource_id, text=text, class_name=class_name)
    return CanonicalAction(ActionKind.CLICK, target)


def launch(package: str = SETTINGS) -> CanonicalAction:
    return CanonicalAction(ActionKind.MANAGE_APP, params={"action": "launch", "package": package})


def page(name: str, package: str = SETTINGS, version_code: int = 34) -> ScreenObservation:
    """A screen whose title id and label derive from `name`, so each name is its own state."""
    slug = name.lower().replace(" ", "_")
    title = element(
        "android.widget.TextView",
        (0, 100, 1080, 200),
        rid=f"{package}:id/{slug}_title",
        text=name,
        package=package,
    )
    rows = [
        element("android.view.View", (0, 300 + 150 * i, 1080, 430 + 150 * i), package=package)
        for i in range(ROWS)
    ]
    activity = "." + name.title().replace(" ", "")
    return ScreenObservation(package, activity, version_code, (title, *rows))


@dataclass
class MapBuilder:
    """Writes a hand-built map: described states, edges and their observations."""

    store: MapStore
    map_id: MapId = SETTINGS_MAP
    _steps: itertools.count = field(default_factory=itertools.count)

    @classmethod
    def open(cls, path: Path, map_id: MapId = SETTINGS_MAP) -> "MapBuilder":
        return cls(MapStore.open(path), map_id)

    def state(self, name: str, purpose: str = "", affordances: tuple[str, ...] = ()) -> StateId:
        screen = abstract(page(name, self.map_id.package, self.map_id.version_code))
        state_id = ids.state_id(self.map_id, screen.coarse_key)
        self.store.put_state(self.map_id, state_id, screen, NOW)
        self.store.documents.describe_state(state_id, name, purpose or f"{name}.", affordances)
        return state_id

    def outside(self) -> StateId:
        return self.store.put_outside_state(self.map_id, NOW)

    def edge(
        self,
        src: StateId,
        dst: StateId,
        action: CanonicalAction,
        *,
        confirmed: int = 1,
        provisional: int = 0,
        discounted: int = 0,
        dropped: int = 0,
        no_effect: int = 0,
        seen_at: float = NOW,
    ) -> EdgeId:
        edge_id = self.store.put_edge(self.map_id, src, dst, [action], seen_at)
        counts = {
            ObservationStatus.CONFIRMED: confirmed,
            ObservationStatus.PROVISIONAL: provisional,
            ObservationStatus.DISCOUNTED: discounted,
            ObservationStatus.DROPPED: dropped,
        }
        for status, count in counts.items():
            self._observe(src, action, edge_id, status, count)
        self._observe(src, action, None, ObservationStatus.CONFIRMED, no_effect)
        return edge_id

    def _observe(
        self,
        src: StateId,
        action: CanonicalAction,
        edge_id: EdgeId | None,
        status: ObservationStatus,
        count: int,
    ) -> None:
        for _ in range(count):
            record = ObservationRecord(
                session_id="s1",
                step_id=str(next(self._steps)),
                src_state_id=src,
                action_signature=ids.action_signature([action]),
                status=status,
                recorded_at=NOW,
                edge_id=edge_id,
            )
            self.store.record_observation(record)
