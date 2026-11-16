from artemis.app_memory.documents import OwnerKind

OWNER_TABLES: dict[OwnerKind, tuple[str, str]] = {
    OwnerKind.STATE: ("states", "state_id"),
    OwnerKind.EDGE: ("edges", "edge_id"),
}

SELECT_PENDING_STATES = """
SELECT state_id, package, activity, skeleton, static_tokens, sample_image_sha
FROM states WHERE description_status = 'pending' AND is_virtual = 0
ORDER BY first_seen_at, state_id LIMIT ?
"""

SELECT_PENDING_EDGES = """
SELECT e.edge_id, s.title, s.is_virtual, d.title, d.is_virtual, e.actions
FROM edges e
JOIN states s ON s.state_id = e.src_state_id
JOIN states d ON d.state_id = e.dst_state_id
WHERE e.description_status = 'pending'
    AND (s.is_virtual = 1 OR s.description_status != 'pending')
    AND (d.is_virtual = 1 OR d.description_status != 'pending')
ORDER BY e.last_seen_at, e.edge_id LIMIT ?
"""

DESCRIBE_STATE = """
UPDATE states SET title = ?, purpose = ?, affordances = ?, description_status = 'ready'
WHERE state_id = ?
"""

DESCRIBE_EDGE = "UPDATE edges SET description = ?, description_status = 'ready' WHERE edge_id = ?"


def mark_failed(kind: OwnerKind) -> str:
    table, key = OWNER_TABLES[kind]
    return (
        f"UPDATE {table} SET description_status = 'failed' "
        f"WHERE {key} = ? AND description_status = 'pending'"
    )


SELECT_READY_STATES = """
SELECT s.state_id, s.package, s.version_code, s.title, s.purpose, s.affordances,
       s.static_tokens, m.text_hash
FROM states s
LEFT JOIN embeddings m
    ON m.owner_kind = 'state' AND m.owner_id = s.state_id AND m.model_id = ?
WHERE s.description_status = 'ready'
ORDER BY s.state_id
"""

SELECT_READY_EDGES = """
SELECT e.edge_id, e.package, e.version_code, e.description,
       s.title, s.is_virtual, d.title, d.is_virtual, m.text_hash
FROM edges e
JOIN states s ON s.state_id = e.src_state_id
JOIN states d ON d.state_id = e.dst_state_id
LEFT JOIN embeddings m
    ON m.owner_kind = 'edge' AND m.owner_id = e.edge_id AND m.model_id = ?
WHERE e.description_status = 'ready'
ORDER BY e.edge_id
"""

INSERT_MODEL = """
INSERT INTO embedding_models (model_id, provider, model, dim) VALUES (?, ?, ?, ?)
ON CONFLICT (model_id) DO NOTHING
"""

SELECT_MODEL = """
SELECT model_id, provider, model, dim FROM embedding_models
WHERE provider = ? AND model = ? AND (? IS NULL OR dim = ?)
ORDER BY rowid DESC LIMIT 1
"""

UPSERT_EMBEDDING = """
INSERT INTO embeddings (owner_kind, owner_id, model_id, text_hash, created_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (owner_kind, owner_id, model_id) DO UPDATE SET
    text_hash = excluded.text_hash,
    created_at = excluded.created_at
RETURNING rowid
"""
