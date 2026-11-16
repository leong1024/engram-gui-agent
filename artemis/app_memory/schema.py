import re
from enum import StrEnum

from artemis.app_memory.models import (
    DescriptionStatus,
    EmbeddingModel,
    ObservationStatus,
)


def _enum_check(column: str, enum: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum)
    return f"CHECK ({column} IN ({values}))"


TABLES: tuple[str, ...] = (
    """CREATE TABLE IF NOT EXISTS app_versions (
        package TEXT NOT NULL,
        version_code INTEGER NOT NULL,
        version_name TEXT,
        first_seen_at REAL NOT NULL,
        last_seen_at REAL NOT NULL,
        PRIMARY KEY (package, version_code))""",
    f"""CREATE TABLE IF NOT EXISTS states (
        state_id TEXT PRIMARY KEY,
        package TEXT NOT NULL,
        version_code INTEGER NOT NULL,
        activity TEXT,
        coarse_key TEXT NOT NULL,
        skeleton JSON NOT NULL,
        static_tokens JSON NOT NULL,
        is_opaque BOOLEAN NOT NULL DEFAULT 0,
        dhash TEXT,
        title TEXT,
        purpose TEXT,
        affordances JSON,
        description_status TEXT NOT NULL DEFAULT 'pending'
            {_enum_check("description_status", DescriptionStatus)},
        sample_session_id TEXT,
        sample_step_id TEXT,
        sample_image_sha TEXT,
        visit_count INTEGER NOT NULL DEFAULT 1,
        first_seen_at REAL NOT NULL,
        last_seen_at REAL NOT NULL,
        is_virtual BOOLEAN NOT NULL DEFAULT 0)""",
    f"""CREATE TABLE IF NOT EXISTS edges (
        edge_id TEXT PRIMARY KEY,
        package TEXT NOT NULL,
        version_code INTEGER NOT NULL,
        src_state_id TEXT NOT NULL REFERENCES states (state_id),
        dst_state_id TEXT NOT NULL REFERENCES states (state_id),
        action_signature TEXT NOT NULL,
        actions JSON NOT NULL,
        description TEXT,
        description_status TEXT NOT NULL DEFAULT 'pending'
            {_enum_check("description_status", DescriptionStatus)},
        confirmed_n INTEGER NOT NULL DEFAULT 0,
        discounted_n INTEGER NOT NULL DEFAULT 0,
        provisional_n INTEGER NOT NULL DEFAULT 0,
        last_seen_at REAL NOT NULL,
        CHECK (src_state_id != dst_state_id))""",
    f"""CREATE TABLE IF NOT EXISTS observations (
        session_id TEXT NOT NULL,
        step_id TEXT NOT NULL,
        edge_id TEXT REFERENCES edges (edge_id),
        src_state_id TEXT NOT NULL REFERENCES states (state_id),
        action_signature TEXT NOT NULL,
        status TEXT NOT NULL {_enum_check("status", ObservationStatus)},
        recorded_at REAL NOT NULL,
        PRIMARY KEY (session_id, step_id))""",
    """CREATE TABLE IF NOT EXISTS harvested_sessions (
        session_id TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK (status IN ('live', 'finalized')),
        outcome TEXT CHECK (outcome IN
            ('completed', 'partial', 'blocked', 'failed', 'cancelled')),
        finalized_at REAL)""",
    """CREATE TABLE IF NOT EXISTS embedding_models (
        model_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        dim INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS embeddings (
        owner_kind TEXT NOT NULL CHECK (owner_kind IN ('state', 'edge')),
        owner_id TEXT NOT NULL,
        model_id TEXT NOT NULL REFERENCES embedding_models (model_id),
        text_hash TEXT NOT NULL,
        created_at REAL NOT NULL,
        PRIMARY KEY (owner_kind, owner_id, model_id))""",
    "CREATE INDEX IF NOT EXISTS idx_states_map ON states (package, version_code)",
    "CREATE INDEX IF NOT EXISTS idx_edges_src ON edges (src_state_id)",
    "CREATE INDEX IF NOT EXISTS idx_observations_edge ON observations (edge_id)",
)

REBUILD_COUNTS = """
UPDATE edges SET
    confirmed_n = (SELECT COUNT(*) FROM observations o
                   WHERE o.edge_id = edges.edge_id AND o.status = 'confirmed'),
    discounted_n = (SELECT COUNT(*) FROM observations o
                    WHERE o.edge_id = edges.edge_id AND o.status = 'discounted'),
    provisional_n = (SELECT COUNT(*) FROM observations o
                     WHERE o.edge_id = edges.edge_id AND o.status = 'provisional')
"""

_IDENTIFIER_CHARS = re.compile(r"[^a-z0-9]+")


def vector_table_name(model_id: str) -> str:
    return "vec_" + _IDENTIFIER_CHARS.sub("_", model_id.lower()).strip("_")


def vector_table_ddl(model: EmbeddingModel) -> str:
    return (
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {vector_table_name(model.model_id)} "
        "USING vec0(map_key TEXT PARTITION KEY, owner_kind TEXT, "
        f"+owner_id TEXT, embedding FLOAT[{int(model.dim)}])"
    )
