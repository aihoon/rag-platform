"""Neo4j summary helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import GraphDatabase

from ..config.settings import Settings


@dataclass
class GraphSummaryStats:
    doc_count: int
    chunk_count: int
    entity_count: int
    relation_count: int


def get_neo4j_summary(
    *,
    settings: Settings,
    logger: Any,
    label: str | None = None,
) -> GraphSummaryStats:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            effective_label = label or settings.neo4j_default_label
            doc_count = session.run(
                "MATCH (d:Document:" + effective_label + ") RETURN count(d) AS c"
            ).single()["c"]
            chunk_count = session.run(
                "MATCH (d:Document:" + effective_label + ")-[:HAS_CHUNK]->(c:Chunk) RETURN count(c) AS c"
            ).single()["c"]
            entity_count = session.run(
                "MATCH (d:Document:" + effective_label + ")-[:HAS_CHUNK]->(c:Chunk) "
                "OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity) "
                "RETURN count(distinct e) AS c"
            ).single()["c"]
            relation_count = session.run(
                "MATCH (d:Document:" + effective_label + ")-[:HAS_CHUNK]->(c:Chunk) "
                "OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)-[r:RELATED]->(:Entity) "
                "RETURN count(distinct r) AS c"
            ).single()["c"]
            logger.info(
                "neo4j_summary done|label=%s|docs=%s|chunks=%s|entities=%s|relations=%s",
                effective_label,
                doc_count,
                chunk_count,
                entity_count,
                relation_count,
            )
            return GraphSummaryStats(
                doc_count=int(doc_count),
                chunk_count=int(chunk_count),
                entity_count=int(entity_count),
                relation_count=int(relation_count),
            )
    finally:
        driver.close()
