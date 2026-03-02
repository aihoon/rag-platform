"""Neo4j graph delete helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import GraphDatabase

from ..config.settings import Settings


@dataclass
class GraphDeleteStats:
    doc_count: int
    chunk_count: int
    entity_count: int
    relation_count: int

def delete_from_neo4j(
    *,
    settings: Settings,
    logger: Any,
    file_upload_id: int,
) -> GraphDeleteStats:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            doc_count = session.run(
                "MATCH (d:Document {file_upload_id: $file_upload_id}) RETURN count(d) AS c",
                {"file_upload_id": file_upload_id},
            ).single()["c"]
            chunk_count = session.run(
                "MATCH (d:Document {file_upload_id: $file_upload_id})-[:HAS_CHUNK]->(c:Chunk) "
                "RETURN count(c) AS c",
                {"file_upload_id": file_upload_id},
            ).single()["c"]
            rel_count = session.run(
                "MATCH (d:Document {file_upload_id: $file_upload_id})-[:HAS_CHUNK]->(c:Chunk) "
                "OPTIONAL MATCH (c)-[m:MENTIONS]->(:Entity) "
                "RETURN count(m) AS c",
                {"file_upload_id": file_upload_id},
            ).single()["c"]
            entity_count = session.run(
                "MATCH (d:Document {file_upload_id: $file_upload_id})-[:HAS_CHUNK]->(c:Chunk) "
                "OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity) "
                "RETURN count(distinct e) AS c",
                {"file_upload_id": file_upload_id},
            ).single()["c"]

            session.run(
                "MATCH (d:Document {file_upload_id: $file_upload_id}) "
                "OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk) "
                "DETACH DELETE c, d",
                {"file_upload_id": file_upload_id},
            )
            session.run(
                "MATCH (e:Entity) WHERE NOT (e)<-[:MENTIONS]-(:Chunk) DETACH DELETE e"
            )
            logger.info(
                "neo4j_delete done|file_upload_id=%s|docs=%s|chunks=%s|entities=%s|relations=%s",
                file_upload_id,
                doc_count,
                chunk_count,
                entity_count,
                rel_count,
            )
            return GraphDeleteStats(
                doc_count=doc_count,
                chunk_count=chunk_count,
                entity_count=entity_count,
                relation_count=rel_count,
            )
    finally:
        driver.close()
