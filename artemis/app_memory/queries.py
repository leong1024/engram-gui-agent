TOUCH_VERSION = """
INSERT INTO app_versions (package, version_code, first_seen_at, last_seen_at)
VALUES (?, ?, ?, ?)
ON CONFLICT (package, version_code) DO UPDATE SET
    last_seen_at = MAX(last_seen_at, excluded.last_seen_at)
"""

UPSERT_STATE = """
INSERT INTO states (state_id, package, version_code, activity, coarse_key, skeleton,
                    static_tokens, is_opaque, dhash, first_seen_at, last_seen_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (state_id) DO UPDATE SET last_seen_at = MAX(last_seen_at, excluded.last_seen_at)
"""

INSERT_OUTSIDE = """
INSERT INTO states (state_id, package, version_code, coarse_key, skeleton, static_tokens,
                    is_virtual, first_seen_at, last_seen_at)
VALUES (?, ?, ?, '@outside', '[]', '[]', 1, ?, ?)
ON CONFLICT (state_id) DO NOTHING
"""

SELECT_STATES = """
SELECT state_id, activity, coarse_key, skeleton, static_tokens, is_opaque, dhash
FROM states WHERE package = ? AND version_code = ? AND is_virtual = 0
ORDER BY state_id
"""

UPSERT_EDGE = """
INSERT INTO edges (edge_id, package, version_code, src_state_id, dst_state_id,
                   action_signature, actions, last_seen_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (edge_id) DO UPDATE SET last_seen_at = MAX(last_seen_at, excluded.last_seen_at)
"""

SELECT_OBSERVED_EDGE = "SELECT edge_id FROM observations WHERE session_id = ? AND step_id = ?"

UPSERT_OBSERVATION = """
INSERT INTO observations (session_id, step_id, edge_id, src_state_id, action_signature,
                          status, recorded_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (session_id, step_id) DO UPDATE SET
    edge_id = excluded.edge_id,
    src_state_id = excluded.src_state_id,
    action_signature = excluded.action_signature,
    status = excluded.status,
    recorded_at = excluded.recorded_at
"""

SELECT_COUNTS = "SELECT confirmed_n, discounted_n, provisional_n FROM edges WHERE edge_id = ?"

INSERT_MODEL = """
INSERT INTO embedding_models (model_id, provider, model, dim) VALUES (?, ?, ?, ?)
ON CONFLICT (model_id) DO NOTHING
"""
