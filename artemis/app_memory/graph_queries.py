from typing import NamedTuple

from artemis.app_memory.queries import select_known


def select_cards(where: str) -> str:
    return f"""
SELECT s.state_id, s.title, s.purpose, s.affordances, s.activity, s.static_tokens,
       s.is_opaque, s.is_virtual,
       (SELECT COUNT(*) FROM edges e JOIN observations o ON o.edge_id = e.edge_id
        WHERE e.dst_state_id = s.state_id AND o.status IN ('confirmed', 'provisional'))
FROM states s WHERE {where}
ORDER BY s.state_id
"""


def select_tallies(where: str) -> str:
    return f"""
SELECT o.src_state_id, o.action_signature, o.edge_id, o.status, COUNT(*)
FROM observations o JOIN states s ON s.state_id = o.src_state_id
WHERE {where}
GROUP BY o.src_state_id, o.action_signature, o.edge_id, o.status
ORDER BY o.src_state_id, o.action_signature, o.edge_id, o.status
"""


def placeholders(count: int) -> str:
    return ", ".join("?" * count)


EDGE_COLUMNS = """
SELECT edge_id, src_state_id, dst_state_id, action_signature, actions, description, last_seen_at
FROM edges
"""

SELECT_MAPS = "SELECT package, version_code FROM app_versions ORDER BY package, version_code"


class GraphQueries(NamedTuple):
    """The four reads that make a MapGraph, over the same named parameters."""

    cards: str
    known: str
    edges: str
    tallies: str


IN_MAP = "s.package = :package AND s.version_code = :version"

WHOLE_MAP = GraphQueries(
    cards=select_cards(IN_MAP),
    known=select_known(IN_MAP),
    edges=f"{EDGE_COLUMNS} WHERE package = :package AND version_code = :version ORDER BY edge_id",
    tallies=select_tallies(IN_MAP),
)

SESSION_SOURCES = f"""
SELECT o.src_state_id FROM observations o JOIN states s ON s.state_id = o.src_state_id
WHERE o.session_id = :session AND {IN_MAP}
"""

TOUCHED_STATES = f"""
s.state_id IN ({SESSION_SOURCES}) OR s.state_id IN (
    SELECT dst_state_id FROM edges WHERE src_state_id IN ({SESSION_SOURCES}))
"""

SESSION_SLICE = GraphQueries(
    cards=select_cards(TOUCHED_STATES),
    known=select_known(TOUCHED_STATES),
    edges=f"{EDGE_COLUMNS} WHERE src_state_id IN ({SESSION_SOURCES}) ORDER BY edge_id",
    tallies=select_tallies(f"o.src_state_id IN ({SESSION_SOURCES})"),
)

SELECT_SESSION_MARKS = """
SELECT s.package, s.version_code, COUNT(*), SUM(o.status = 'provisional')
FROM observations o JOIN states s ON s.state_id = o.src_state_id
WHERE o.session_id = ?
GROUP BY s.package, s.version_code
"""
