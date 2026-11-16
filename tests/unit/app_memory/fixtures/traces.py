import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from artemis.data_engine.models import ImageRecord, SessionMetadata, StepRecord
from artemis.data_engine.storage import StorageManager
from tests.unit.app_memory.fixtures.parts import CLOCK, Element

Action = dict[str, Any]


def tap(resource_id: str) -> Action:
    return {"action": "tap", "target_resource_id": resource_id, "target_class": "FrameLayout"}


def flash_click(resource_id: str) -> Action:
    return {"action": "click", "args": {"target": 3}, "target_resource_id": resource_id}


def launch(package: str) -> Action:
    return {"action": "launch_app", "app_name": package}


def wait() -> Action:
    return {"action": "wait_for_delay", "time_in_ms": 800}


class Trace:
    """A data_engine.db written the way the DataEngine records runs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.storage = StorageManager(root / "data_engine.db", root)

    def session(
        self,
        session_id: str,
        status: str = "completed",
        *,
        pid: int | None = None,
        started_at: float = 1_000.0,
        task_status: str | None = None,
    ) -> "SessionScript":
        metadata = SessionMetadata(
            session_id=session_id,
            initial_goal="goal",
            start_time=started_at,
            status=status,
            pid=pid,
        )
        self.storage.create_session(metadata)
        if task_status:
            run_dir = self.root / session_id
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run_outcome.json").write_text(json.dumps({"task_status": task_status}))
        return SessionScript(self.storage, session_id, started_at)


class SessionScript:
    def __init__(self, storage: StorageManager, session_id: str, started_at: float) -> None:
        self._storage = storage
        self.session_id = session_id
        self._started_at = started_at
        self._steps = 0

    def step(
        self,
        screen: list[Element] | None,
        *actions: Action,
        package: str = CLOCK,
        status: str | None = "dispatched",
    ) -> str:
        self._steps += 1
        image = self._image(screen) if screen is not None else None
        step_id = f"{self.session_id}-{self._steps}"
        record = StepRecord(
            step_id=step_id,
            session_id=self.session_id,
            step_number=self._steps,
            timestamp=self._started_at + self._steps,
            pre_image_name=image,
            action_taken=list(actions),
            last_execution_result={"status": status} if status else None,
            extra_metadata={"foreground_app": package, "activity": ".Main", "version_code": 1},
        )
        self._storage.create_step(record)
        return step_id

    def _image(self, screen: list[Element]) -> str:
        name = hashlib.sha256(json.dumps(screen, sort_keys=True).encode()).hexdigest()
        if self._storage.get_image(name) is None:
            self._storage.create_image(ImageRecord(image_name=name, ui_tree=screen))
        return name


class MapView:
    """Reads app_memory.db back the way a later run or a reviewer would."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def _rows(self, sql: str, *params: object) -> list[tuple[Any, ...]]:
        with sqlite3.connect(self._path) as conn:
            return conn.execute(sql, params).fetchall()

    def state_count(self, package: str) -> int:
        sql = "SELECT COUNT(*) FROM states WHERE package = ? AND is_virtual = 0"
        return self._rows(sql, package)[0][0]

    def edges(self) -> list[tuple[str, bool, bool, int, int, int, int]]:
        sql = """
            SELECT e.package, src.is_virtual, dst.is_virtual, json_array_length(e.actions),
                   e.confirmed_n, e.discounted_n, e.provisional_n
            FROM edges e
            JOIN states src ON src.state_id = e.src_state_id
            JOIN states dst ON dst.state_id = e.dst_state_id
            ORDER BY e.package, src.is_virtual, dst.is_virtual"""
        return [(r[0], bool(r[1]), bool(r[2]), *r[3:]) for r in self._rows(sql)]

    def observations(self, session_id: str) -> list[tuple[str, bool, str]]:
        sql = """
            SELECT step_id, edge_id IS NOT NULL, status FROM observations
            WHERE session_id = ? ORDER BY step_id"""
        return [(r[0], bool(r[1]), r[2]) for r in self._rows(sql, session_id)]

    def session(self, session_id: str) -> tuple[str, str | None] | None:
        sql = "SELECT status, outcome FROM harvested_sessions WHERE session_id = ?"
        rows = self._rows(sql, session_id)
        return rows[0] if rows else None

    def dump(self) -> list[str]:
        with sqlite3.connect(self._path) as conn:
            return list(conn.iterdump())
