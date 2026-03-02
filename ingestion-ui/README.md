# ingestion-ui

## 목적

`ingestion-ui`는 브라우저에서 문서 업로드와 ingestion 실행을 빠르게 검증하기 위한 Streamlit UI

## 핵심 역할

ingestion 파이프라인의 운영 콘솔이자 테스트 UI

- PDF 파일을 로컬 디스크/SQLite에 저장
- `ingestion-api`에 ingestion 실행 요청 전송
- Weaviate 상태/요약 확인
- 필요 시 vector chunk + 로컬 파일/메타데이터 삭제

## 동작 구조

1. 사용자 PDF 선택
2. `Save to Local DB` 클릭
3. 파일은 `ingestion-ui/data/uploads/`에 저장
4. 메타데이터는 `ingestion-ui/data/ingestion_ui.db`의 `uploaded_files` 테이블에 저장
5. `Run Ingestion` 클릭 시 `ingestion-api`의 `/run` 호출
6. `ingestion-api`가 SQLite 정보를 읽어 embedding + Weaviate 적재 수행
7. UI에서 상태/응답/오류 확인

## 구성

- 엔트리 포인트: `ingestion-ui/app.py`
- 로컬 업로드 파일 경로: `ingestion-ui/data/uploads/`
- 로컬 메타데이터 DB: `ingestion-ui/data/ingestion_ui.db`

## 실행 방법

1. 권장 환경 변수 설정

```bash
export INGESTION_API_URL=http://localhost:8000
export WEAVIATE_URL=http://localhost:8080
```

2. UI 실행

```bash
pipenv run streamlit run ingestion-ui/app.py
```

3. 브라우저 접속

- Streamlit 기본 주소: [http://localhost:8501](http://localhost:8501)

## 사전 실행 조건

1. `ingestion-api`가 먼저 떠 있어야 함
2. Weaviate가 떠 있어야 함 (`WEAVIATE_URL`)
3. `ingestion-api`가 `INGESTION_UI_DB_PATH`로 동일 SQLite를 읽을 수 있어야 함
   - 미지정 시 기본 경로(`ingestion-ui/data/ingestion_ui.db`) 사용

## 화면별 기능 상세

## 1) Sidebar: Backend

- `Ingestion API URL`: `/run`, `/chunks`, `/health*` 호출 대상
- `API Timeout`: API 요청 타임아웃
- `Delete vector data on file delete`:
  - 켜짐: Delete 시 `/chunks` 먼저 호출 후 로컬 삭제
  - 꺼짐: 로컬 파일/DB만 삭제

## 2) Sidebar: Vector DB

- `Weaviate URL`: summary 조회 대상
### - `RAG Class Name`: summary 조회 target class (예: `C1`)
 - `RAG Class Name`: summary 조회 target class (`General`/`Machine`) ### ###

## 3) Sidebar: Live Checks

- `API Health Check` -> `GET /health`
- `SQLite DB Live Check` -> `GET /health/sqlite-live`
- `Weaviate Live Check` -> `GET /health/weaviate-live`

연결 문제를 ingestion 전에 바로 확인할 수 있습니다.

## 4) Upload PDF 섹션

- 입력값:
  - `company_id` (default: `0`) ### ###
  - `machine_cat` (integer, default: `0`) ### ###
  - `machine_id` (default: `0`) ### ###
  - PDF 파일
- `Save to Local DB` 동작:
  - SHA-256 중복 체크
  - 파일 저장 + DB row 생성
  - 초기 상태: `UPLOADED`

## 5) Uploaded Files 섹션

업로드된 각 row에 대해:

- `Run Ingestion`
  - `POST {INGESTION_API_URL}/run`
  - 성공 시 상태 `INGEST_REQUESTED`
  - 실패 시 상태 `FAILED` 및 오류 메시지 저장
- `Mark Ingested`
  - 수동으로 상태를 `INGESTED`로 변경
- `Delete`
  - 옵션에 따라 vector 삭제 포함 가능
  - 로컬 파일 + SQLite row 삭제

표시되는 주요 상태:

- `UPLOADED`
- `INGEST_REQUESTED`
- `INGESTED`
- `FAILED`

## 6) Weaviate Summary 섹션

- `Refresh Weaviate Summary` 클릭 시:
  - 전체 class 목록
  - target class object count
  - sampled rows count
  - source 통계

주의:
- target class 이름이 실제 적재 class와 다르면 `sampled_rows`가 0으로 보일 수 있습니다.

## API 연동 스키마

`POST /run` 요청 필드:

- `company_id` (default: `0`) ### ###
- `machine_cat` (integer, default: `0`) ### ###
- `machine_id` (default: `0`) ### ###
- `file_upload_id`
- `file_name`

`DELETE /chunks` 요청 필드:

- `company_id` (default: `0`) ### ###
- `machine_cat` (integer, default: `0`) ### ###
- `machine_id` (default: `0`) ### ###
- `file_upload_id`
- `file_name`
- `class_name` (optional)

## 환경 변수

- `INGESTION_API_URL` (기본값: `http://localhost:8000`)
### - `INGESTION_DEFAULT_COMPANY_ID` (기본값: `1`)
### - `INGESTION_DEFAULT_MACHINE_CAT` (기본값: `general`)
### - `INGESTION_DEFAULT_MACHINE_ID` (기본값: `1`)
- `WEAVIATE_URL` (기본값: `http://localhost:8080`)
### - `RAG_CLASS_NAME` (기본값: `RagDocumentChunk`)
 - `WEAVIATE_GENERAL_CLASS_NAME` (기본값: `General`) ### ###
 - `WEAVIATE_MACHINE_CLASS_NAME` (기본값: `Machine`) ### ###

## 레거시 DB 정책

- `company_id`가 없으면 앱 시작 시 Fail Fast
### - `machine_cat`/`machine_id`가 없으면 앱 시작 시 자동으로 컬럼 추가
 - `machine_cat`는 integer 컬럼이며 기본값 `0` ### ###

수동 리셋 방법:

1. `ingestion-ui/data/ingestion_ui.db` 백업(선택)
2. 기존 DB 삭제
3. 앱 재시작

## SQLite 마이그레이션 (machine_cat: string -> int) ### ###

스크립트: [ingestion-ui/scripts/migrate_sqlite_machine_cat_int.py](scripts/migrate_sqlite_machine_cat_int.py) ### ###

예시:

```bash
python ingestion-ui/scripts/migrate_sqlite_machine_cat_int.py \
  --db-path ingestion-ui/data/ingestion_ui.db \
  --drop-old
```

## 트러블슈팅

1. `Connection refused`:
- `INGESTION_API_URL` 포트/호스트 확인
- `ingestion-api` 실행 여부 확인

2. `HTTP 401` (OpenAI key):
- `OPENAI_API_KEY` 확인 후 API 재시작

3. `HTTP 429` (quota):
- OpenAI billing/quota 확인

4. `sampled_rows=0`:
- `RAG Class Name`이 실제 class와 일치하는지 확인
- summary 쿼리 필드와 class schema 일치 여부 확인

## TODO (기능 개선 항목)

1. File format 확장
- PDF 외 CSV/DOCX/XLSX/PPTX/TXT ingestion UI 지원

2. Batch operation
- 여러 row 선택 후 일괄 Run/Delete
- 진행률(progress bar) 표시

3. 재시도/복구 기능
- 실패 row 자동 재시도 정책
- 오류 타입별 가이드 메시지 강화

4. 검색/필터 UX
- uploaded list에 company/machine/status 필터 추가
- 정렬 및 pagination 지원

5. 운영 가시성 강화
- ingestion 단계별 로그/latency 표시
- 최근 실패 이력 대시보드

6. 데이터 정합성 기능
- class 불일치 탐지/경고
- row 상태와 Weaviate 실제 count 자동 비교
