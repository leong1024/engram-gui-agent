import functools
import sqlite3
from collections.abc import Callable
from typing import Concatenate, ParamSpec, Protocol, TypeVar

from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)


class Disableable(Protocol):
    disabled: bool


S = TypeVar("S", bound=Disableable)
P = ParamSpec("P")
R = TypeVar("R")


def guarded(method: Callable[Concatenate[S, P], R]) -> Callable[Concatenate[S, P], R | None]:
    """App memory never raises into the agent: log, and stop after a database error."""

    @functools.wraps(method)
    def run(self: S, *args: P.args, **kwargs: P.kwargs) -> R | None:
        if self.disabled:
            return None
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            logger.warning(f"App memory {method.__name__}{args} failed: {exc!r}", exc_info=True)
            if isinstance(exc, sqlite3.DatabaseError):
                self.disabled = True
                logger.warning("App memory is disabled for the rest of this run.")
            return None

    return run
