from artemis.app_memory.graph_store import SessionMark
from artemis.app_memory.models import MapId
from artemis.app_memory.routing import RoutingMap
from artemis.app_memory.store import MapStore


class MapGraphCache:
    """The run's routing maps, one per MapId, shared by every milestone in that map.

    Only the store worker thread writes here: it loads a map once, and after each harvest
    pass it swaps in a rebuilt RoutingMap for a map the pass changed. The event loop only
    reads. A RoutingMap is immutable and replaced by reference, so a reader gets the old
    map or the new one, never one half built, and needs no lock."""

    def __init__(self) -> None:
        self._maps: dict[MapId, RoutingMap] = {}
        self._marks: dict[tuple[str, MapId], SessionMark] = {}

    def get(self, map_id: MapId) -> RoutingMap | None:
        return self._maps.get(map_id)

    def load(self, store: MapStore, map_id: MapId) -> RoutingMap:
        if map_id not in self._maps:
            self._maps[map_id] = RoutingMap.build(store.graph.map_graph(map_id))
        return self._maps[map_id]

    def refresh(self, store: MapStore, session_id: str) -> None:
        """Re-reads the rows `session_id` touched in each loaded map whose mark moved."""
        if not self._maps:
            return
        for map_id, mark in store.graph.session_marks(session_id).items():
            current = self._maps.get(map_id)
            if current is None or self._marks.get((session_id, map_id)) == mark:
                continue
            part = store.graph.session_slice(map_id, session_id)
            self._maps[map_id] = RoutingMap.build(current.graph.merged(part))
            self._marks[session_id, map_id] = mark
