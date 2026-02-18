# Streamlit UI

## Run

1. Start local backend (optional)

```bash
PYTHONPATH=src pipenv run python -m rag_api.main
```

2. Run Streamlit with `pipenv`

```bash
pipenv install streamlit requests
pipenv run streamlit run ui_streamlit/app.py
```

3. Run Streamlit with `venv`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install streamlit requests
streamlit run ui_streamlit/app.py
```

## Connection Defaults

- The UI reads `RAG_API_URL` from `.env` as the default target.
- Current example:
  - `RAG_API_URL=http://localhost:8000/rag-api`
- Parsed defaults in sidebar:
  - `Scheme`: `http`
  - `Host`: `localhost`
  - `Port`: `8000`
  - `API Base Path`: `/rag-api`
  - `Chat Path`: `/chat`
- If you use a reverse proxy, update these fields in the sidebar.

## Features

- Calls the `/chat` endpoint
- Automatically handles both JSON and streaming responses
- Keeps `chatId` across messages
- Supports `service` fields (`type`, `dashboardId`, `modelId`, extra JSON)
