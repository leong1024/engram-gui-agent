def select_cards(where: str) -> str:
    return f"""
SELECT s.state_id, s.title, s.purpose, s.affordances, s.activity, s.static_tokens,
       s.is_opaque, s.is_virtual,
       (SELECT COUNT(*) FROM edges e JOIN observations o ON o.edge_id = e.edge_id
        WHERE e.dst_state_id = s.state_id AND o.status IN ('confirmed', 'provisional'))
FROM states s WHERE {where}
ORDER BY s.state_id
"""


def placeholders(count: int) -> str:
    return ", ".join("?" * count)


SELECT_MAP_CARDS = select_cards("s.package = ? AND s.version_code = ?")

EDGE_COLUMNS = """
SELECT edge_id, src_state_id, dst_state_id, action_signature, actions, description, last_seen_at
FROM edges
"""

SELECT_MAP_EDGES = f"{EDGE_COLUMNS} WHERE package = ? AND version_code = ? ORDER BY edge_id"

SELECT_MAP_TALLIES = """
SELECT o.src_state_id, o.action_signature, o.edge_id, o.status, COUNT(*)
FROM observations o JOIN states s ON s.state_id = o.src_state_id
WHERE s.package = ? AND s.version_code = ?
GROUP BY o.src_state_id, o.action_signature, o.edge_id, o.status
ORDER BY o.src_state_id, o.action_signature, o.edge_id, o.status
"""

SELECT_MAPS = "SELECT package, version_code FROM app_versions ORDER BY package, version_code"
