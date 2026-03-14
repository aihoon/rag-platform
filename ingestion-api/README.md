# ingestion-api

## 목적

`ingestion-api`는 `ingestion-ui`가 관리하는 업로드 메타데이터(SQLite)를 기준으로 PDF를 처리하고,
Weaviate(벡터) + Neo4j(그래프) 적재/삭제/상태확인을 제공하는 FastAPI Backend

## 핵심 기능

- `POST /run`으로 파일 단위 ingestion 비동기 실행(즉시 accepted 응답)
- SQLite `uploaded_files` 상태 전이 관리(`REQUESTED` -> `RUNNING` -> `INGESTED`/`FAILED`)
- Weaviate text chunk 적재 및 삭제
- Neo4j 문서/청크/엔티티/관계 적재 및 삭제
- PDF 테이블 추출/품질평가/테이블 chunk 적재
- PDF 이미지 추출/요약(옵션)/이미지 chunk 적재
- API/SQLite/Weaviate/Neo4j health 및 summary 조회

## 아키텍처 개요

1. `ingestion-ui`가 `/run` 요청 (`file_upload_id`, `file_name`, 메타 필드 포함)
2. API가 즉시 `accepted` 응답 반환 후 백그라운드 작업 시작
3. SQLite에서 대상 row 조회 및 요청값(`company_id`, `machine_cat`, `machine_id`) 정합성 검증
4. PDF 텍스트 추출 -> 청크 생성 (`EMBEDDING_CHUNK_SIZE`, `EMBEDDING_CHUNK_OVERLAP`)
5. Weaviate enabled 시 텍스트/테이블/이미지 청크 적재
6. Neo4j enabled 시 문서/청크/트리플(옵션) 적재
7. 완료/실패 결과를 SQLite 상태와 응답 로그에 반영

## 실행 방법

repo root 기준:

```bash
cd /Users/hoonpaek/Workspace/MachineGPT/rag-platform
export INGESTION_API_URL=http://localhost:4590
export INGESTION_API_DOTENV_PATH=../../../.env
PYTHONPATH=ingestion-api/src pipenv run python -m ingestion_api.main
```

기본 접속: [http://localhost:4590](http://localhost:4590)

대안(uvicorn 직접 실행):

```bash
PYTHONPATH=ingestion-api/src pipenv run uvicorn ingestion_api.main:app --host 0.0.0.0 --port 4590
```

## 사전 실행 조건

- `OPENAI_API_KEY` 설정(임베딩/LLM 경로 사용 시)
- Weaviate 실행
- Neo4j 기능 사용 시 Neo4j 실행 및 접속 정보 설정
- `ingestion-ui/data/ingestion_ui.db` 접근 가능(또는 `INGESTION_UI_DB_PATH` 지정)

## 주요 엔드포인트

### Health

| Endpoint                                      | 설명                       |
|-----------------------------------------------|--------------------------|
| `GET /health`                                 | API liveness             |
| `GET /health/sqlite-live`                     | SQLite 연결/쿼리 확인          |
| `GET /health/weaviate-live`                   | Weaviate 연결 확인           |
| `GET /health/neo4j-live`                      | Neo4j 연결 확인              |
| `GET /health/weaviate-summary?class_name=...` | Weaviate 클래스/문서/chunk 요약 |
| `GET /health/neo4j-summary?label=...`         | Neo4j 라벨 기준 요약           |

### Ingestion/Delete

| Endpoint         | 설명                    |
|------------------|-----------------------|
| `POST /run`      | 비동기 ingestion 실행 요청   |
| `DELETE /chunks` | Weaviate 오브젝트 삭제      |
| `DELETE /graph`  | Neo4j 문서/청크/엔티티/관계 삭제 |

## 실행 예시

### Ingestion 요청

```bash
curl -X POST http://localhost:4590/run \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "manual.pdf",
    "file_upload_id": 1,
    "class_name": "General",
    "company_id": 0,
    "machine_cat": 0,
    "machine_id": 0,
    "weaviate_enabled": true,
    "neo4j_enabled": true
  }'
```

### Weaviate 삭제 요청

```bash
curl -X DELETE http://localhost:4590/chunks \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "manual.pdf",
    "file_upload_id": 1,
    "class_name": "General"
  }'
```

### Neo4j 삭제 요청

```bash
curl -X DELETE http://localhost:4590/graph \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "manual.pdf",
    "file_upload_id": 1
  }'
```

## 환경 변수

### Core

- `INGESTION_API_URL` (기본: `http://0.0.0.0:4590`)
- `INGESTION_API_DOTENV_PATH` (기본: `../../../.env`)
- `INGESTION_UI_DB_PATH` (미설정 시 `ingestion-ui/data/ingestion_ui.db`)
- `OPENAI_API_KEY`
- `DEBUG`

### Logging

- `INGESTION_API_LOG_PATH` (기본: `./logs/ingestion-api.log`)
- `INGESTION_API_LOG_LEVEL` (기본: `INFO`)
- `INGESTION_API_LOG_NAME` (기본: `ingestion-api`)

### Weaviate / Embedding

- `WEAVIATE_URL` (기본: `http://localhost:8080`)
- `WEAVIATE_REQUEST_TIMEOUT_SEC` (기본: `30`)
- `WEAVIATE_DEFAULT_CLASS` (기본: `General`)
- `WEAVIATE_MACHINE_CLASS_NAME` (기본: `Machine`)
- `EMBEDDING_MODEL` (기본: `text-embedding-3-small`)
- `EMBEDDING_CHUNK_SIZE` (기본: `800`)
- `EMBEDDING_CHUNK_OVERLAP` (기본: `200`)
- `EMBEDDING_REQUEST_TIMEOUT_SEC` (기본: `30`)

### Neo4j

- `NEO4J_ENABLED` (기본: `true`)
- `NEO4J_URI` (기본: `bolt://localhost:7687`)
- `NEO4J_USER` (기본: `neo4j`)
- `NEO4J_PASSWORD` (기본: `neo4j_password`)
- `NEO4J_DATABASE` (기본: `neo4j`)
- `NEO4J_DEFAULT_LABEL` (기본: `General`)
- `NEO4J_EXTRACT_TRIPLES` (기본: `true`)
- `NEO4J_EXTRACT_MAX_CHARS` (기본: `4000`)
- `NEO4J_TRIPLE_MODEL` (기본: `gpt-4o-mini`)
- `NEO4J_TRIPLE_MAX_TOKENS` (기본: `200`)
- `NEO4J_MAX_TRIPLES_PER_CHUNK` (기본: `20`)

### Table Pipeline

- `TABLE_ENABLED` (기본: `true`)
- `TABLE_FAIL_POLICY` (기본: `fail_open`)
- `TABLE_MIN_PARSER_CONFIDENCE` (기본: `0.75`)
- `TABLE_MAX_EMPTY_CELL_RATIO` (기본: `0.30`)
- `TABLE_MAX_HEADER_INCONSISTENCY` (기본: `0.20`)
- `TABLE_EMBEDDING_VERSION` (기본: `1`)

### Image Pipeline

- `IMAGE_ENABLED` (기본: `true`)
- `IMAGE_OCR_ENABLED` (기본: `true`)
- `IMAGE_FAIL_POLICY` (기본: `fail_open`)
- `IMAGE_SUMMARY_MODEL` (기본: `gpt-4o-mini`)
- `IMAGE_MIN_AREA_RATIO` (기본: `0.015`)
- `IMAGE_DECORATIVE_MAX_AREA_RATIO` (기본: `0.04`)
- `IMAGE_DECORATIVE_MAX_OCR_CHARS` (기본: `6`)
- `IMAGE_MAX_PER_PAGE` (기본: `8`)
- `IMAGE_EXTRACT_DIR` (기본: `./data/extracted_images`)
- `IMAGE_CONTEXT_WINDOW_CHARS` (기본: `800`)
- `IMAGE_MIN_OCR_CHARS` (기본: `10`)

## Troubleshooting

1. `Connection refused`
   - `INGESTION_API_URL` host/port 확인
   - 프로세스 기동 여부 확인

2. `SQLite schema mismatch` 또는 row 미조회
   - `ingestion-ui`가 같은 DB를 사용 중인지 확인
   - `uploaded_files` 컬럼(`company_id`, `machine_cat`, `machine_id`) 확인

3. `401` / `429` (OpenAI)
   - `OPENAI_API_KEY`, 사용량/쿼터 확인

4. Weaviate/Neo4j 연결 실패
   - 각 URL/계정/DB 설정 확인
   - `/health/weaviate-live`, `/health/neo4j-live` 먼저 점검

5. `/run`이 바로 완료되지 않고 `accepted`만 반환됨
   - 정상 동작입니다. 실제 ingestion은 백그라운드에서 진행됩니다.
   - 상태는 `ingestion-ui` 또는 SQLite `uploaded_files`의 상태 컬럼으로 확인하세요.

## TO-DO

1. 작업 실행 모델 고도화
   - FastAPI `BackgroundTasks` 기반 실행을 작업 큐(Celery/RQ/Arq) 기반으로 전환
   - 워커 수평 확장, 우선순위 큐, 재시도 정책(지수 백오프) 지원
   - 장시간 작업 heartbeat/lease 기반 stuck job 복구

2. 상태 모델/정합성 강화
   - SQLite 상태 전이(`REQUESTED/RUNNING/INGESTED/FAILED`)를 명시적 상태머신으로 관리
   - Weaviate/Neo4j 실제 상태와 SQLite 상태 비교용 reconciliation 배치 추가
   - partial success(예: Weaviate 성공, Neo4j 실패)에 대한 표준 상태/오류 코드 체계화

3. API 계약 안정화
   - OpenAPI 스키마 버저닝(`/v1`) 및 하위 호환 정책 문서화
   - idempotency key 지원으로 중복 `/run` 요청 안전 처리
   - 작업 조회/취소 API 추가 (`GET /jobs/{id}`, `POST /jobs/{id}/cancel`)

4. 성능 최적화
   - 대용량 PDF 스트리밍 처리 및 페이지 병렬 파이프라인 도입
   - 임베딩 배치 크기 자동 튜닝(모델/토큰/latency 기반)
   - Weaviate/Neo4j bulk upsert 경로 개선 및 네트워크 round-trip 최소화

5. 데이터 모델 개선
   - `uploaded_files` 스키마 migration 관리 체계(Alembic 또는 자체 migration table) 도입
   - chunk/table/image 공통 메타 스키마 표준화(`ingest_version`, `source_version`, `parser_version`)
   - 삭제 정책(soft delete / hard delete / TTL)과 감사 컬럼(`deleted_by`, `deleted_at`) 정의

6. 품질 게이트 고도화 (Table/Image)
   - 테이블 품질지표 정밀화(열 타입 일관성, 단위 정합성, 병합셀 처리 품질)
   - 이미지 분류/요약 정확도 평가셋 구축 및 임계치 기반 fail policy 자동화
   - 품질 실패 샘플 자동 수집 및 재처리 파이프라인 연결

7. Neo4j 그래프 품질 개선
   - 트리플 추출 프롬프트 버전 관리 및 회귀 테스트 세트 구축
   - 엔티티 정규화(동의어/표기 변형) 및 relation ontology 도입
   - 문서 재인제스트 시 orphan entity/relation 정리 전략 명확화

8. 관측성/운영성 강화
   - 구조화 로그(JSON) + trace_id/job_id 전 구간 전파
   - OpenTelemetry 기반 metrics/traces 통합(P95 latency, error rate, queue lag)
   - 운영 대시보드(ingest throughput, 실패율, 백로그, 백엔드별 성공률) 구성

9. 보안/거버넌스
   - API 인증(서비스 토큰/JWT) 및 권한 분리(조회/삭제/실행)
   - 민감정보 마스킹(로그/응답) 및 비밀키 관리(Secret Manager)
   - 문서/테넌트 단위 접근제어(tenant isolation, row-level guard) 도입

10. 장애 대응/복구
   - 외부 의존성(Weaviate/Neo4j/OpenAI) 장애 시 circuit breaker + graceful degradation
   - 작업 재실행(runbook) 자동화 및 실패 원인 분류 표준화
   - 백업/복구 시나리오(메타 DB, 인덱스 재구축) 정기 리허설

11. 테스트/검증 체계 강화
   - contract test(요청/응답 스키마), integration test(실DB/실스토어), load test 분리 운영
   - golden dataset 기반 인제스트 결과 회귀 테스트(텍스트/테이블/이미지/그래프)
   - CI에서 lint/type/test + smoke ingestion pipeline 자동 실행

12. 개발자 경험(DX) 개선
   - 로컬 one-command 실행(`make up`, `make test-ingestion`) 제공
   - 샘플 데이터셋/샘플 curl을 포함한 빠른 시작 가이드 확장
   - 장애 케이스별 디버깅 플레이북 문서화

13. 비용 최적화
   - 임베딩/LLM 호출 캐시 전략(문서 해시 기반) 도입
   - 모델 라우팅 정책(품질 기준 충족 시 저비용 모델 우선)
   - 처리량 대비 비용 리포트(문서/페이지/청크 단가) 제공

14. 멀티 포맷 확장
   - PDF 외 DOCX/XLSX/PPTX/CSV/TXT 파서 파이프라인 추가
   - 포맷별 preflight 검증 및 파싱 실패 사전 탐지
   - 포맷별 chunking/profile 템플릿 제공

## 관련 문서

- Weaviate `machine_cat` 타입 마이그레이션: [docs/weaviate_machine_cat_int.md](../docs/weaviate_machine_cat_int.md)
- 테이블 백필/재적재: [docs/table-migration-backfill.md](../docs/table-migration-backfill.md)
