# Open WebUI to rag-api Test Setup

## Goal

Use Open WebUI as the replacement for `rag-ui` with these user-configurable inputs:

- `ragType`
- `className`
- `companyId`
- `machineCat`
- `machineId`

Out of scope for this phase:

- rendering `sources`
- rendering `meta`
- rendering `externalSources`

## Topology

```text
User
  -> Open WebUI
  -> Open WebUI Pipe
  -> Nginx Load Balancer
  -> rag-api (single instance, stateful)
```

The `rag-api` instance remains single-instance for now because chat state is still stored in process memory for the legacy `/chat` path. The OpenAI-compatible adapter path already reconstructs context from `messages[]`, but the backend is still not ready for multi-instance stateful deployment.

## Sources Used

This setup follows Open WebUI's current documentation:

- OpenAI-compatible providers: https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
- Pipes: https://docs.openwebui.com/features/pipelines/pipes/
- Valves and UserValves: https://docs.openwebui.com/features/plugin/valves/

Open WebUI's docs indicate:

- OpenAI-compatible backends should implement `/v1/models` and `/v1/chat/completions`
- Pipes can act as external models
- UserValves create user-editable GUI fields in chat sessions

## What Was Added

### 1. Open WebUI Pipe

File:

- `/deploy/openwebui/functions/rag_api_pipe.py`

Behavior:

- exposes a single external model named `RAG API Chat`
- provides `UserValves` for:
  - `rag_type`
  - `class_name`
  - `company_id`
  - `machine_cat`
  - `machine_id`
- calls `rag-api` through the load balancer using:
  - `POST /v1/chat/completions`

### 2. OpenAI-compatible endpoint contract

Current `rag-api` compatibility layer accepts:

- `model`
- `messages`
- `stream`
- `ragType`
- `className`
- `companyId`
- `machineCat`
- `machineId`
- `dashboardId`
- `modelId`

The key files are:

- `/rag-api/src/rag_api/api/routers/openai_compat.py`
- `/rag-api/src/rag_api/api/schemas/openai_compat.py`

### 3. Local test compose

File:

- `/deploy/docker-compose.openwebui-rag.yml`

Services:

- `open-webui`
- `rag-api-lb`

The compose file intentionally does not start `rag-api` itself. Run `rag-api` from the host first.

## Run Order

### 1. Start rag-api on the host

```bash
cd /Users/hoonpaek/Workspace/MachineGPT/rag-platform
PYTHONPATH=rag-api/src pipenv run uvicorn rag_api.main:app --host 0.0.0.0 --port 8000
```

### 2. Start Open WebUI and the load balancer

```bash
cd /Users/hoonpaek/Workspace/MachineGPT/rag-platform
docker compose -f deploy/docker-compose.openwebui-rag.yml up -d
```

### 3. Verify rag-api through the load balancer

```bash
curl http://localhost:4592/v1/models ###
```

```bash
curl -X POST http://localhost:4592/v1/chat/completions \ ###
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-conversational",
    "stream": false,
    "messages": [
      {"role": "user", "content": "hello"}
    ],
    "ragType": "conversational",
    "className": "General",
    "companyId": 0,
    "machineCat": 0,
    "machineId": 0
  }'
```

### 4. Open Open WebUI

Go to:

- `http://localhost:3000`

Create the first admin account.

### 5. Import the Pipe

In Open WebUI:

1. Go to `Workspace` -> `Functions`
2. Choose import from file
3. Import:
   - `/Users/hoonpaek/Workspace/MachineGPT/rag-platform/deploy/openwebui/functions/rag_api_pipe.py`
4. Enable the function

After enabling it, the pipe appears as an external model.

### 6. Configure admin valves if needed

Default admin valves:

- `RAG_API_BASE_URL=http://host.docker.internal:4592/v1` ###
- `RAG_API_KEY=dummy-key-not-used`
- `REQUEST_TIMEOUT_SEC=180`

These are configurable from the function settings UI.

### 7. Set per-user values from the chat session

In the chat session for the `RAG API Chat` model, Open WebUI should expose user-editable fields for:

- `rag_type`
- `class_name`
- `company_id`
- `machine_cat`
- `machine_id`

Use those as the replacement for the old `rag-ui` sidebar inputs.

## Important Constraints

### No source panels yet

This phase only returns assistant text to Open WebUI.

It does not render:

- sources
- meta
- external sources

### Streaming disabled

The current `rag-api` OpenAI-compatible adapter rejects `stream=true`.

The pipe forces:

- `stream: false`

### Single rag-api instance only

Do not scale `rag-api` yet.

This is still a validation phase before the stateless migration.

## Next Step

After this is validated:

```text
Open WebUI -> Load Balancer -> rag-api x N -> Redis/Postgres
```

That future phase should remove in-memory chat state and add shared persistence.
