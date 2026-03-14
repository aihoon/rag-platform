"""Neo4j graph ingestion helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, TYPE_CHECKING

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from neo4j import GraphDatabase
from shared.schemas.rag_class import DEFAULT_CLASS_NAME

from ..config.settings import Settings

if TYPE_CHECKING:
    from .ingestion_service import TextChunk


@dataclass
class GraphIngestionStats:
    chunk_count: int
    entity_count: int
    relation_count: int


def _parse_triples(raw: str, max_triples: int) -> list[tuple[str, str, str]]:
    triples: list[tuple[str, str, str]] = []
    for line in raw.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            continue
        head, rel, tail = parts
        if not head or not rel or not tail:
            continue
        triples.append((head, rel.upper(), tail))
        if len(triples) >= max_triples:
            break
    return triples


def _extract_triples(
    settings: Settings, logger: Any, text: str
) -> list[tuple[str, str, str]]:
    snippet = text[: settings.neo4j_extract_max_chars]
    logger.info(
        "llm_call start|component=neo4j_triple_extract|model=%s|input_chars=%s|max_chars=%s",
        settings.neo4j_triple_model,
        len(snippet),
        settings.neo4j_extract_max_chars,
    )
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.neo4j_triple_model,
        temperature=0.0,
        max_tokens=settings.neo4j_triple_max_tokens,
        timeout=settings.embedding_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Extract key entities and relations as triples in the form: ENTITY_A | RELATION | ENTITY_B. "
                "Return one triple per line. If none, return empty.",
            ),
            (
                "human",
                "Text:\n{text}\n\nTriples:",
            ),
        ]
    )
    messages = prompt.format_messages(text=snippet)
    try:
        response = llm.invoke(messages)
        raw = getattr(response, "content", "").strip()
        triples = _parse_triples(raw, settings.neo4j_max_triples_per_chunk)
        logger.info(
            "llm_call done|component=neo4j_triple_extract|model=%s|output_chars=%s|triples=%s",
            settings.neo4j_triple_model,
            len(raw),
            len(triples),
        )
        return triples
    except Exception as exc:
        logger.exception(
            "llm_call fail|component=neo4j_triple_extract|model=%s|detail=%s",
            settings.neo4j_triple_model,
            exc,
        )
        raise


def _ensure_schema(session) -> None:
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE"
    )
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE")
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE"
    )


def _normalize_label(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", raw or "")
    return cleaned or DEFAULT_CLASS_NAME


def _upsert_document(session, doc_props: dict[str, Any]) -> None:
    class_label = _normalize_label(str(doc_props.get("class_name", DEFAULT_CLASS_NAME)))
    session.run(
        f"MERGE (d:Document:{class_label} {{id: $id}}) "
        "SET d.file_name=$file_name, d.company_id=$company_id, d.machine_id=$machine_id, "
        "d.machine_cat=$machine_cat, d.file_upload_id=$file_upload_id, d.class_name=$class_name",
        doc_props,
    )


def _upsert_chunk(
    session, doc_id: str, chunk: TextChunk, class_label: str, class_name: str
) -> None:
    session.run(
        f"MERGE (c:Chunk:{class_label} {{id: $id}}) "
        "SET c.page_number=$page_number, c.start_char=$start_char, c.end_char=$end_char, c.text=$text, "
        "c.class_name=$class_name "
        "WITH c "
        "MATCH (d:Document {id: $doc_id}) "
        "MERGE (d)-[:HAS_CHUNK]->(c)",
        {
            "id": chunk.chunk_id,
            "page_number": chunk.page_number,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "text": chunk.text,
            "class_name": class_name,
            "doc_id": doc_id,
        },
    )


def _upsert_triples(
    session, chunk_id: str, triples: Iterable[tuple[str, str, str]]
) -> tuple[int, int]:
    entity_count = 0
    relation_count = 0
    for head, rel, tail in triples:
        session.run(
            "MERGE (h:Entity {name: $head}) "
            "MERGE (t:Entity {name: $tail}) "
            "MERGE (h)-[r:RELATED {type: $rel}]->(t) "
            "WITH h, t "
            "MATCH (c:Chunk {id: $chunk_id}) "
            "MERGE (c)-[:MENTIONS]->(h) "
            "MERGE (c)-[:MENTIONS]->(t)",
            {"head": head, "tail": tail, "rel": rel, "chunk_id": chunk_id},
        )
        entity_count += 2
        relation_count += 1
    return entity_count, relation_count


def ingest_to_neo4j(
    *,
    settings: Settings,
    logger: Any,
    doc_id: str,
    doc_props: dict[str, Any],
    chunks: list["TextChunk"],
) -> GraphIngestionStats:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    entity_total = 0
    relation_total = 0
    try:
        with driver.session(database=settings.neo4j_database) as session:
            _ensure_schema(session)
            _upsert_document(session, doc_props)
            class_label = _normalize_label(
                str(doc_props.get("class_name", DEFAULT_CLASS_NAME))
            )
            class_name = str(doc_props.get("class_name", DEFAULT_CLASS_NAME))
            logger.info(
                "neo4j_ingest start|doc_id=%s|chunks=%s|extract_triples=%s|label=%s",
                doc_id,
                len(chunks),
                settings.neo4j_extract_triples,
                class_label,
            )
            for index, chunk in enumerate(chunks, start=1):
                logger.info(
                    "neo4j_chunk start|doc_id=%s|chunk=%s/%s|chunk_id=%s|text_len=%s",
                    doc_id,
                    index,
                    len(chunks),
                    chunk.chunk_id,
                    len(chunk.text),
                )
                _upsert_chunk(session, doc_id, chunk, class_label, class_name)
                logger.info(
                    "neo4j_chunk upserted|doc_id=%s|chunk=%s/%s|chunk_id=%s",
                    doc_id,
                    index,
                    len(chunks),
                    chunk.chunk_id,
                )
                if settings.neo4j_extract_triples:
                    logger.info(
                        "neo4j_triples start|doc_id=%s|chunk=%s/%s|chunk_id=%s",
                        doc_id,
                        index,
                        len(chunks),
                        chunk.chunk_id,
                    )
                    triples = _extract_triples(settings, logger, chunk.text)
                    logger.info(
                        "neo4j_triples extracted|doc_id=%s|chunk=%s/%s|chunk_id=%s|triples=%s",
                        doc_id,
                        index,
                        len(chunks),
                        chunk.chunk_id,
                        len(triples),
                    )
                    entities, relations = _upsert_triples(
                        session, chunk.chunk_id, triples
                    )
                    entity_total += entities
                    relation_total += relations
                    logger.info(
                        "neo4j_triples upserted|doc_id=%s|chunk=%s/%s|chunk_id=%s|entities=%s|relations=%s",
                        doc_id,
                        index,
                        len(chunks),
                        chunk.chunk_id,
                        entities,
                        relations,
                    )
                logger.info(
                    "neo4j_chunk done|doc_id=%s|chunk=%s/%s|chunk_id=%s|entity_total=%s|relation_total=%s",
                    doc_id,
                    index,
                    len(chunks),
                    chunk.chunk_id,
                    entity_total,
                    relation_total,
                )
            logger.info(
                "neo4j_ingest done|doc_id=%s|chunks=%s|entities=%s|relations=%s",
                doc_id,
                len(chunks),
                entity_total,
                relation_total,
            )
    finally:
        driver.close()

    return GraphIngestionStats(
        chunk_count=len(chunks),
        entity_count=entity_total,
        relation_count=relation_total,
    )
