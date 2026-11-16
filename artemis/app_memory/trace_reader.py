import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from artemis.app_memory.actions import step_actions
from artemis.app_memory.models import (
    UNKNOWN_VERSION_CODE,
    ScreenObservation,
    StateSample,
)
from artemis.app_memory.outcomes import TraceSession
from artemis.app_memory.transitions import HarvestStep, Sighting
from artemis.data_engine.models import StepRecord
from artemis.data_engine.storage import StorageManager
from artemis.runtime.process_probe import pid_is_alive

DATA_ENGINE_DB = "data_engine.db"
RUN_OUTCOME_FILE = "run_outcome.json"


class TraceReader:
    """Reads recorded sessions from the DataEngine as harvestable steps."""

    def __init__(self, storage: StorageManager, traces_dir: Path) -> None:
        self._storage = storage
        self._traces_dir = traces_dir

    @classmethod
    def open(cls, traces_dir: Path) -> "TraceReader":
        storage = StorageManager(traces_dir / DATA_ENGINE_DB, traces_dir, read_only=True)
        return cls(storage, traces_dir)

    def session_ids(self) -> list[str]:
        return self._storage.session_ids()

    def session(self, session_id: str) -> TraceSession | None:
        row = self._storage.get_session(session_id)
        if row is None:
            return None
        return TraceSession(
            status=row.status,
            started_at=row.start_time,
            process_alive=row.pid is not None and pid_is_alive(row.pid),
            run_task_status=self._run_task_status(session_id),
        )

    def steps(self, session_id: str) -> list[HarvestStep]:
        trees: dict[str, Any] = {}
        records = self._storage.get_steps(session_id)
        return [self._step(session_id, record, trees) for record in records]

    def _step(self, session_id: str, record: StepRecord, trees: dict[str, Any]) -> HarvestStep:
        result = record.last_execution_result
        status = result.get("status") if isinstance(result, Mapping) else None
        acted = step_actions(record.action_taken, status)
        image = record.pre_image_name
        if image and image not in trees:
            stored = self._storage.get_image(image)
            trees[image] = stored.ui_tree if stored else None
        screen = _screen(record.extra_metadata, trees.get(image) if image else None)
        sample = StateSample(session_id, str(record.step_id), image)
        return HarvestStep(
            step_id=str(record.step_id),
            recorded_at=record.timestamp,
            actions=acted.actions,
            is_wait=acted.is_wait,
            sighting=Sighting(screen, sample) if screen else None,
        )

    def _run_task_status(self, session_id: str) -> str | None:
        path = self._traces_dir / session_id / RUN_OUTCOME_FILE
        try:
            status = json.loads(path.read_text(encoding="utf-8")).get("task_status")
        except (OSError, ValueError, AttributeError):
            return None
        return status if isinstance(status, str) else None


def _screen(extra: Mapping[str, Any], tree: Any) -> ScreenObservation | None:
    package = extra.get("foreground_app")
    if not isinstance(package, str) or not package or not isinstance(tree, list) or not tree:
        return None
    version = extra.get("version_code")
    width, height = extra.get("width"), extra.get("height")
    return ScreenObservation(
        package=package,
        activity=extra.get("activity"),
        version_code=version if isinstance(version, int) else UNKNOWN_VERSION_CODE,
        elements=tuple(element for element in tree if isinstance(element, Mapping)),
        dhash=extra.get("pre_image_dhash"),
        screen_size=(width, height) if isinstance(width, int) and isinstance(height, int) else None,
    )
