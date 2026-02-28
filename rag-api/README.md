# rag-api

## 목적

`rag-api`는 RAG 플랫폼의 질의 처리(standard RAG)를 담당하는 FastAPI 서비스입니다.

## 실행

```bash
pipenv run uvicorn rag_api.main:app --host 0.0.0.0 --port 8000
```

## 주요 엔드포인트

- `POST /chat`
- `GET /health`
- `GET /health/weaviate-live`

## 환경 변수

- `RAG_API_URL` (default: `http://0.0.0.0:8000`)
- `RAG_API_ROOT_PATH` (default: ``)
- `RAG_API_LOG_PATH` (default: `./logs/rag-api.log`)
- `RAG_API_LOG_LEVEL` (default: `INFO`)
- `RAG_API_LOG_NAME` (default: `rag-api`)
- `EMBEDDING_MODEL` (default: `text-embedding-3-small`)
- `RAG_TEMPERATURE` (default: `0.2`)
- `RAG_MAX_TOKENS` (default: `800`)
- `RAG_RETRIEVAL_TOP_K` (default: `4`)
- `RAG_MAX_CONTEXT_CHARS` (default: `4000`)
- `RAG_MAX_HISTORY_TURNS` (default: `6`)
- `RAG_MIN_SCORE_DISTANCE` (default: `-1`, disabled)
- `RAG_SYSTEM_PROMPT` (default: built-in)
- `WEAVIATE_URL` (default: `http://localhost:8080`)
- `WEAVIATE_LOG_PATH` (default: `./logs/weaviate-db.log`)
- `EMBEDDING_REQUEST_TIMEOUT_SEC` (default: `30`)
- `WEAVIATE_CLASS_PREFIX` (default: `C`)
- `RAG_CHAT_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_API_KEY` (required)

## 요청/응답 예시

```json
POST /chat
{
  "userInput": "질문을 입력하세요",
  "chatId": null,
  "userId": "tester",
  "service": {
    "ragType": "standard",
    "companyId": 1,
    "machineId": 10,
    "machineCat": "A",
    "dashboardId": 123,
    "modelId": 5
  }
}
```

```json
{
  "message": "응답 텍스트",
  "intent": "standard_rag",
  "streaming": false,
  "sources": [
    {
      "content": "...",
      "source": "manual.pdf",
      "page_number": 3,
      "machine_id": "10",
      "file_upload_id": "12",
      "machine_cat": "A",
      "distance": 0.23
    }
  ],
  "meta": {
    "chatId": "...",
    "companyId": 1,
    "machineId": 10,
    "machineCat": "A",
    "ragType": "standard",
    "dashboardId": 123,
    "modelId": 5
  }
}
```
