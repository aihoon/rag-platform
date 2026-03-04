# LibreChat to rag-api Test Setup

## Goal

Replace `rag-ui` with LibreChat for chat testing while keeping:

- `ingestion-ui` as Streamlit
- `rag-api` stateful for now
- a load balancer in front of `rag-api`

Initial topology:

```text
LibreChat -> Nginx Load Balancer -> rag-api (single instance)
```

This is intentionally a single-instance backend test.

Reason:

- current `rag-api` stores chat history in process memory
- multiple `rag-api` instances would split conversation state
- stateless migration comes later

## What Was Added

### rag-api adapter endpoints

The repo now exposes OpenAI-compatible endpoints for LibreChat:

- `GET /v1/models`
- `POST /v1/chat/completions`

These endpoints adapt LibreChat/OpenAI-style `messages[]` payloads into the existing RAG execution flow.

Important limitation:

- streaming is not supported yet in the compatibility layer
- LibreChat must send `stream: false`

### Load balancer config

Added files:

- `/deploy/nginx/rag-api.single.conf`
- `/deploy/docker-compose.librechat-rag-lb.yml`

This Nginx config proxies requests from port `4592` to host `rag-api` on `4591`. ###

### LibreChat config template

Added file:

- `/deploy/librechat/librechat.rag-api.yaml.example`

Use the `endpoints.custom` section from that file in your LibreChat `librechat.yaml`.

## Run Order

### 1. Start rag-api on the host

```bash
cd /Users/hoonpaek/Workspace/MachineGPT/rag-platform
PYTHONPATH=rag-api/src pipenv run uvicorn rag_api.main:app --host 0.0.0.0 --port 8000
```

### 2. Start the Nginx load balancer

```bash
cd /Users/hoonpaek/Workspace/MachineGPT/rag-platform
docker compose -f deploy/docker-compose.librechat-rag-lb.yml up -d
```

### 3. Verify the adapter through the load balancer

Model list:

```bash
curl http://localhost:4592/v1/models ###
```

Chat completion:

```bash
curl -X POST http://localhost:4592/v1/chat/completions \ ###
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-conversational",
    "stream": false,
    "messages": [
      {"role": "user", "content": "What documents are available?"}
    ],
    "ragType": "conversational",
    "className": "General",
    "companyId": 0,
    "machineCat": 0,
    "machineId": 0
  }'
```

### 4. Point LibreChat to the load balancer

In LibreChat `librechat.yaml`, add a custom endpoint whose `baseURL` is:

```text
http://host.docker.internal:4592/v1 ###
```

If LibreChat is not running in Docker, use:

```text
http://localhost:4592/v1 ###
```

## Behavior Notes

### Current conversation handling

The OpenAI-compatible adapter reconstructs conversation history from the incoming `messages[]` array.

That means:

- LibreChat can already keep multi-turn context
- the adapter does not currently rely on `chat_id`
- this is good enough for the UI replacement test

### Why single rag-api first

The original `/chat` route still uses process memory for `chat_id` history.

So the safe first test is:

- one `rag-api`
- one load balancer
- LibreChat as the UI

## Next Step After This Test

Once this path is validated, move to:

```text
LibreChat -> Load Balancer -> rag-api x N -> Redis/Postgres
```

That requires:

- removing in-memory `chat_store`
- externalizing chat history
- adding per-conversation concurrency control
