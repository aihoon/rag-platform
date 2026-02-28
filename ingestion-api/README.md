# ingestion-api

## 목적

`ingestion-api`는 문서를 vector DB(Weaviate)에 적재하는 backend API 서비스입니다.

핵심 책임:

- `ingestion-ui`가 저장한 업로드 메타데이터(SQLite) 조회
- PDF text 추출 및 chunk 생성
- OpenAI Embedding 생성
- Weaviate class 생성/적재
- 동일 파일 재실행 시 기존 chunk 삭제 후 재적재(중복 방지)

## 구성

주요 파일:

- 엔트리포인트: `ingestion-api/src/ingestion_api/main.py`
- 설정: `ingestion-api/src/ingestion_api/config/settings.py`
- 라우터: `ingestion-api/src/ingestion_api/api/routers/health.py`
- 라우터: `ingestion-api/src/ingestion_api/api/routers/ingestion.py`
- 서비스: `ingestion-api/src/ingestion_api/services/ingestion_service.py`
- 서비스: `ingestion-api/src/ingestion_api/services/vector_delete_service.py`
- 공유 스키마: `shared/schemas/ingestion.py`

## 동작 흐름

1. `POST /run` 요청 수신
2. SQLite에서 `file_upload_id` 대상 행 조회
3. PDF 추출 (`pdfplumber`)
###4. chunking (`INGESTION_CHUNK_SIZE`, `INGESTION_CHUNK_OVERLAP`)
4. chunking (`EMBEDDING_CHUNK_SIZE`, `EMBEDDING_CHUNK_OVERLAP`)
5. OpenAI Embedding 생성
6. Weaviate class(`C{company_id}`) 확인/생성
7. 동일 파일 기존 chunk 삭제 후 새 chunk 적재
8. `pipeline_id`, `chunk_count` 반환

## API 엔드포인트

## Health

- `GET /health`
- `GET /health/sqlite-live`
- `GET /health/weaviate-live`

## Ingestion

- `POST /run`
  - body: `company_id`, `machine_cat`, `machine_id`, `file_upload_id`, `file_name`
  - response: `status`, `pipeline_id`, `class_name`, `chunk_count`

- `DELETE /chunks`
  - body: `company_id`, `machine_cat`, `machine_id`, `file_upload_id`, `file_name`, `class_name?`
  - response: `status`, `class_name`, `deleted_count`, `deleted_ids`

## 에러 코드 정책

- `401`: OpenAI API key 인증 실패
- `422`: 요청값/데이터 검증 실패
- `429`: OpenAI quota/rate limit 초과
- `500`: 그 외 내부 오류

## 환경 변수

핵심:

- `INGESTION_API_URL` (예: `http://localhost:8001`)
- `INGESTION_API_DOTENV_PATH` (기본: `../../../.env`)
- `INGESTION_UI_DB_PATH` (비우면 기본 SQLite 경로 사용)
- `WEAVIATE_URL` (예: `http://localhost:8080`)
- `OPENAI_API_KEY`

chunk/embedding:

###- `INGESTION_EMBEDDING_MODEL` (기본: `text-embedding-3-small`)
###- `INGESTION_CHUNK_SIZE` (기본: `1200`)
###- `INGESTION_CHUNK_OVERLAP` (기본: `200`)
###- `INGESTION_REQUEST_TIMEOUT_SEC` (기본: `30`)
###- `INGESTION_WEAVIATE_CLASS_PREFIX` (기본: `C`)
- `EMBEDDING_MODEL` (기본: `text-embedding-3-small`)
- `EMBEDDING_CHUNK_SIZE` (기본: `1200`)
- `EMBEDDING_CHUNK_OVERLAP` (기본: `200`)
- `EMBEDDING_REQUEST_TIMEOUT_SEC` (기본: `30`)
- `WEAVIATE_CLASS_PREFIX` (기본: `C`)

로그:

- `INGESTION_API_LOG_PATH`
- `INGESTION_API_LOG_LEVEL`
- `INGESTION_API_LOG_NAME`

## 실행 방법

모든 명령은 repo root 기준:

```bash
cd /Users/hoonpaek/Workspace/MachineGPT/rag-platform
```

권장(모듈 실행):

```bash
export INGESTION_API_URL=http://localhost:8001
export INGESTION_API_DOTENV_PATH=../../../.env
PYTHONPATH=ingestion-api/src pipenv run python -m ingestion_api.main
```

대안(uvicorn 직접 실행):

```bash
export INGESTION_API_URL=http://localhost:8001
export INGESTION_API_DOTENV_PATH=../../../.env
PYTHONPATH=ingestion-api/src pipenv run uvicorn ingestion_api.main:app --host 0.0.0.0 --port 8001
```

참고:

- 서비스는 `INGESTION_API_URL`에서 host/port를 파싱해 바인딩합니다.
- `INGESTION_API_URL`의 path는 `root_path`로 사용됩니다(리버스 프록시 환경용).

## 동작 확인 (Quick Check)

```bash
curl http://localhost:8001/health
curl http://localhost:8001/health/sqlite-live
curl http://localhost:8001/health/weaviate-live
```

ingestion 실행 예시:

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "manual.pdf",
    "file_upload_id": 1,
    "company_id": 1,
    "machine_cat": "general",
    "machine_id": 1,
    "user_id": "cli-user"
  }'
```

## PyCharm 실행 설정

1. `Run | Edit Configurations...`
2. `+` -> `Python`
3. `Module name`: `ingestion_api.main`
4. `Working directory`: `/Users/hoonpaek/Workspace/MachineGPT/rag-platform`
5. `Environment variables`:
   - `PYTHONPATH=ingestion-api/src`
   - `INGESTION_API_URL=http://localhost:8001`
   - `INGESTION_API_DOTENV_PATH=../../../.env`
6. Interpreter: root `pipenv` interpreter

## 트러블슈팅

1. `Connection refused`
- 포트 충돌 확인 (`rag-api`와 같은 포트 사용 여부)
- `INGESTION_API_URL` host/port 확인

2. `SQLite schema mismatch`
- `ingestion-ui` DB 스키마 확인
- 필요 시 `ingestion-ui/data/ingestion_ui.db` 리셋

3. `401 invalid_api_key`
- `OPENAI_API_KEY` 확인 후 서버 재시작

4. `429 insufficient_quota`
- OpenAI billing/quota 확인

5. Weaviate 연결 실패
- `WEAVIATE_URL` 확인
- `GET /health/weaviate-live`로 즉시 점검

## HISTORY

- LANGSMITH tracing 구현 (26-02-19)
  * .env / main.py / ingeestion_service.py
- 
