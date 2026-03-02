"""Shared Neo4j summary helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import GraphDatabase


@dataclass
class Neo4jSummaryStats:
    label: str
    doc_count: int
    chunk_count: int
    entity_count: int
    relation_count: int


def get_neo4j_summary(
    *,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str,
    default_label: str,
    logger: Any,
    label: str | None = None,
) -> Neo4jSummaryStats:
    effective_label = label or default_label
    driver = GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password),
    )
    try:
        with driver.session(database=neo4j_database) as session:
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
            return Neo4jSummaryStats(
                label=effective_label,
                doc_count=int(doc_count),
                chunk_count=int(chunk_count),
                entity_count=int(entity_count),
                relation_count=int(relation_count),
            )
    finally:
        driver.close()
