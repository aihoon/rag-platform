# LibreChat Ingestion UI Migration

## Conclusion

`ingestion-ui` cannot be replaced 1:1 by LibreChat.

Reason:

- Current `ingestion-ui` is an operations console for upload tracking, ingestion triggering, health checks, and deletion.
- LibreChat is a multi-user chat UI. Its built-in RAG API integration is designed for chat file indexing and retrieval, not for operating a custom ingestion dashboard.

Recommended direction:

- Keep LibreChat as the user-facing chat UI.
- Move `ingestion-ui` logic into backend APIs and, if needed, expose them as MCP tools for LibreChat.
- Treat ingestion management and chat as separate concerns.

## Current `ingestion-ui` Responsibilities

Current Streamlit app handles all of the following:

- Persist uploaded files on local disk
- Persist upload metadata in SQLite
- Trigger `POST /run` on `ingestion-api`
- Poll and render Weaviate/Neo4j ingestion status
- Delete remote Weaviate and Neo4j data
- Delete local file and local DB row
- Run health and summary checks

This is not a chat-only UI. It is an admin/operator console.

## What LibreChat Can Cover

LibreChat can cover:

- Multi-user authentication and chat sessions
- File upload in conversations
- File search / RAG usage in conversations
- MCP-based tool invocation from the chat UI

LibreChat does not natively replace:

- Custom uploaded file inventory UI
- SQLite-backed ingestion job dashboard
- Per-row operational actions like "Ingest to Weaviate", "Delete Neo4j Data", "Delete File"

## Recommended Migration Shape

### Phase 1: Remove UI-specific state from ingestion flow

Move the source of truth from Streamlit local state and SQLite coupling into backend services.

Target split:

- `ingestion-api`
  - becomes the authoritative ingestion control plane
- metadata store
  - Postgres preferred
- object/file storage
  - S3/MinIO preferred
- LibreChat
  - user-facing chat UI
- optional admin UI
  - only if operators still need a table/grid workflow

### Phase 2: Define ingestion management APIs

Add explicit APIs for ingestion management instead of relying on Streamlit local DB behavior.

Recommended endpoints:

- `POST /uploads`
  - upload file and create metadata row
- `GET /uploads`
  - list uploaded files with status
- `GET /uploads/{id}`
  - retrieve one upload
- `POST /uploads/{id}/ingest`
  - trigger Weaviate and/or Neo4j ingestion
- `DELETE /uploads/{id}/weaviate`
  - delete vector data
- `DELETE /uploads/{id}/neo4j`
  - delete graph data
- `DELETE /uploads/{id}`
  - delete file metadata and storage object
- `GET /uploads/{id}/status`
  - fetch ingestion state

### Phase 3: Choose the LibreChat integration mode

Two realistic options:

#### Option A: LibreChat for chat, separate admin UI for ingestion

Use LibreChat only for multi-user chat and file-based RAG.

Keep a small dedicated admin UI for:

- upload inventory
- ingestion control
- operational delete actions
- health dashboards

This is the lowest-risk migration.

#### Option B: LibreChat + MCP tools for ingestion operations

Expose ingestion actions through an MCP server.

Examples:

- `list_uploads`
- `trigger_ingestion`
- `get_ingestion_status`
- `delete_weaviate_data`
- `delete_neo4j_data`

This allows operators to use LibreChat as a conversational operations console, but it is not a table/grid replacement.

## Recommendation for This Repo

Start with Option A, not Option B.

Reason:

- current ingestion workflow is row-based and operational
- LibreChat chat UX is a poor fit for bulk file operations and status tables
- migration effort is much smaller if chat and ingestion admin are separated first

Proposed target:

- replace `rag-ui` with LibreChat for end-user chat
- keep `ingestion-ui` temporarily
- refactor `ingestion-ui` functionality behind APIs
- once APIs are stable, either:
  - rebuild a thin admin UI, or
  - add MCP tools for operator workflows

## Concrete Repo Changes to Start

### Step 1

Stop treating `ingestion-ui/data/ingestion_ui.db` as the authoritative store.

Current code couples both UI and API to the same SQLite file:

- `ingestion-ui/app.py`
- `ingestion-api/services/ingestion_service.py`
- `ingestion-api/services/upload_status_service.py`

This blocks multi-user deployment and blocks LibreChat integration.

### Step 2

Create a backend upload repository abstraction.

Suggested module:

- `ingestion-api/src/ingestion_api/services/upload_repository.py`

Responsibilities:

- create upload
- list uploads
- get upload by id
- update statuses
- delete upload

### Step 3

Move file storage out of `ingestion-ui/data/uploads`.

Suggested first step:

- local shared storage path configurable from backend

Preferred target:

- S3 or MinIO

### Step 4

Add upload management endpoints to `ingestion-api`.

That lets any UI use the same backend:

- Streamlit
- LibreChat-adjacent admin UI
- MCP server

## Migration Order

1. Refactor backend so uploads and statuses are owned by `ingestion-api`, not `ingestion-ui`.
2. Keep current Streamlit app working against the new API.
3. Replace `rag-ui` with LibreChat for chat.
4. Decide whether ingestion operations remain in a small admin UI or move into MCP tools.

## Why Not Start by Embedding LibreChat into `ingestion-ui`

Because that would mix two unrelated interaction models:

- operator dashboard
- end-user chat

It would also preserve the current architectural problem:

- local SQLite and local disk are tied to one UI process

That is the first thing that should be removed.
