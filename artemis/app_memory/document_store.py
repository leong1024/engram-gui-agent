import json
import sqlite3
from collections.abc import Sequence
import sqlite_vec

from artemis.app_memory import document_queries as queries
from artemis.app_memory import schema
from artemis.app_memory.documents import (
    EmbeddingDoc,
    Owner,
    OwnerKind,
    PendingEdge,
    PendingState,
    edge_document,
    endpoint_title,
    loads_list,
    state_document,
    vector_map_key,
)
from artemis.app_memory.models import EmbeddingModel, MapId
from artemis.app_memory.transaction import transaction


class DocumentStore:
    """Descriptions and embeddings of states and edges, on the map store's connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def pending_states(self, limit: int) -> list[PendingState]:
        rows = self._conn.execute(queries.SELECT_PENDING_STATES, (limit,))
        return [
            PendingState(state_id, package, activity, loads_list(skel), loads_list(tokens), image)
            for state_id, package, activity, skel, tokens, image in rows
        ]

    def pending_edges(self, limit: int) -> list[PendingEdge]:
        rows = self._conn.execute(queries.SELECT_PENDING_EDGES, (limit,))
        return [
            PendingEdge(
                edge_id,
                endpoint_title(src_title, src_virtual),
                endpoint_title(dst_title, dst_virtual),
                loads_list(actions),
            )
            for edge_id, src_title, src_virtual, dst_title, dst_virtual, actions in rows
        ]

    def describe_state(
        self, state_id: str, title: str, purpose: str, affordances: Sequence[str]
    ) -> None:
        with transaction(self._conn) as conn:
            conn.execute(
                queries.DESCRIBE_STATE, (title, purpose, json.dumps(list(affordances)), state_id)
            )

    def describe_edge(self, edge_id: str, description: str) -> None:
        with transaction(self._conn) as conn:
            conn.execute(queries.DESCRIBE_EDGE, (description, edge_id))

    def mark_failed(self, owner: Owner) -> None:
        with transaction(self._conn) as conn:
            conn.execute(queries.mark_failed(owner.kind), (owner.owner_id,))

    def stale_documents(self, model_id: str | None) -> list[EmbeddingDoc]:
        """Ready documents with no vector under `model_id`, or one of an older text."""
        docs = [*self._state_documents(model_id), *self._edge_documents(model_id)]
        return [doc for doc, stored in docs if stored != doc.text_hash]

    def embedding_model(self, provider: str, model: str, dim: int | None) -> EmbeddingModel | None:
        row = self._conn.execute(queries.SELECT_MODEL, (provider, model, dim, dim)).fetchone()
        return EmbeddingModel(*row) if row else None

    def ensure_vector_table(self, model: EmbeddingModel) -> str:
        with transaction(self._conn) as conn:
            _ensure_vector_table(conn, model)
        return schema.vector_table_name(model.model_id)

    def put_vectors(
        self,
        model: EmbeddingModel,
        docs: Sequence[EmbeddingDoc],
        vectors: Sequence[Sequence[float]],
        now: float,
    ) -> None:
        table = schema.vector_table_name(model.model_id)
        with transaction(self._conn) as conn:
            _ensure_vector_table(conn, model)
            for doc, vector in zip(docs, vectors, strict=True):
                kind, owner_id = doc.owner.kind.value, doc.owner.owner_id
                params = (kind, owner_id, model.model_id, doc.text_hash, now)
                rowid = conn.execute(queries.UPSERT_EMBEDDING, params).fetchone()[0]
                conn.execute(f"DELETE FROM {table} WHERE rowid = ?", (rowid,))
                conn.execute(
                    f"INSERT INTO {table} (rowid, map_key, owner_kind, owner_id, embedding) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (rowid, doc.map_key, kind, owner_id, sqlite_vec.serialize_float32(vector)),
                )

    def _state_documents(self, model_id: str | None) -> list[tuple[EmbeddingDoc, str | None]]:
        documents = []
        for row in self._conn.execute(queries.SELECT_READY_STATES, (model_id,)):
            state_id, package, version, title, purpose, affordances, labels, stored = row
            text = state_document(title, purpose, loads_list(affordances), loads_list(labels))
            owner = Owner(OwnerKind.STATE, state_id)
            documents.append(
                (EmbeddingDoc(owner, vector_map_key(MapId(package, version)), text), stored)
            )
        return documents

    def _edge_documents(self, model_id: str | None) -> list[tuple[EmbeddingDoc, str | None]]:
        documents = []
        for row in self._conn.execute(queries.SELECT_READY_EDGES, (model_id,)):
            edge_id, package, version, description, src, src_virtual, dst, dst_virtual, stored = row
            src_title, dst_title = (
                endpoint_title(src, src_virtual),
                endpoint_title(dst, dst_virtual),
            )
            text = edge_document(description, src_title, dst_title)
            owner = Owner(OwnerKind.EDGE, edge_id)
            documents.append(
                (EmbeddingDoc(owner, vector_map_key(MapId(package, version)), text), stored)
            )
        return documents


def _ensure_vector_table(conn: sqlite3.Connection, model: EmbeddingModel) -> None:
    conn.execute(queries.INSERT_MODEL, (model.model_id, model.provider, model.model, model.dim))
    conn.execute(schema.vector_table_ddl(model))
