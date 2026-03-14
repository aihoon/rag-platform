# ingestion-ui

## 목적

`ingestion-ui`는 브라우저에서 PDF 업로드 메타데이터를 로컬(SQLite)에 저장하고,
`ingestion-api`를 통해 **Weaviate + Neo4j** ingestion/삭제/상태확인까지 수행하는 Streamlit 운영 UI

## 핵심 기능

- PDF 파일 로컬 저장(`ingestion-ui/data/uploads/`) + SQLite 메타데이터 저장
- 클래스/설비 메타(`class_name`, `company_id`, `machine_cat`, `machine_id`) 관리
- 파일별 Weaviate ingestion 요청
- 파일별 Neo4j ingestion 요청
- Weaviate/Neo4j 개별 삭제 및 전체 파일 삭제 시 원격 삭제 연동
- Weaviate/Neo4j 상태 동기화(Sync) 버튼
- API/SQLite/Weaviate/Neo4j Live Health Check
- Weaviate Summary, Neo4j Summary 조회

## 아키텍처 개요

1. 사용자가 PDF를 선택하고 `Save to Local DB`를 실행
2. 파일은 디스크에 저장되고 메타데이터는 SQLite `uploaded_files`에 저장
3. 각 row에서 `Ingest` 버튼으로 `ingestion-api`의 `/run`을 호출
4. `weaviate_enabled` 또는 `neo4j_enabled` 플래그에 따라 적재 대상이 분기
5. 필요 시 `/chunks`(Weaviate), `/graph`(Neo4j)로 삭제를 수행

## 실행 방법

```bash
export INGESTION_API_URL=http://localhost:4590
export WEAVIATE_URL=http://localhost:8080
pipenv run streamlit run ingestion-ui/app.py --server.port 8501
```

브라우저: [http://localhost:8501](http://localhost:8501)

## 사전 실행 조건

- `ingestion-api` 실행
- Weaviate 실행
- Neo4j 실행(Neo4j 기능 사용 시)
- `ingestion-api`가 동일 SQLite 파일(`ingestion-ui/data/ingestion_ui.db`)을 참조 가능해야 함

## 주요 화면

### Sidebar

코드 기준 분류(`ingestion-ui/app.py`):

| Sidebar Item                                    | UI Type                  | 동작/의미                              | Backend Endpoint            |
|-------------------------------------------------|--------------------------|------------------------------------|-----------------------------|
| `Ingestion API URL`                             | Display (`st.caption`)   | `.env`에 설정된 API URL 표시(편집 불가)      | -                           |
| `API Timeout (sec)`                             | Control (`st.slider`)    | API 호출 timeout 제어                  | -                           |
| `Delete Weaviate and Neo4j data on file delete` | Checkbox (`st.checkbox`) | 파일 삭제 시 원격 데이터 삭제 포함 여부            | -                           |
| `Weaviate URL`                                  | Display (`st.caption`)   | `.env`에 설정된 Weaviate URL 표시(편집 불가) | -                           |
| `API Health Check`                              | Button (`st.button`)     | API liveness 확인                    | `GET /health`               |
| `SQLite DB Live Check`                          | Button (`st.button`)     | SQLite 연결 확인                       | `GET /health/sqlite-live`   |
| `Weaviate Live Check`                           | Button (`st.button`)     | Weaviate 연결 확인                     | `GET /health/weaviate-live` |
| `Neo4j Live Check`                              | Button (`st.button`)     | Neo4j 연결 확인                        | `GET /health/neo4j-live`    |

### Upload PDF

- `Class / Label` 선택 (`General`, `Machine`, `Physical_AI`, `EdgeCross_Policy`)
- `Machine` 클래스 선택 시 `company_id`, `machine_cat`, `machine_id` 입력
- `Save to Local DB` 실행 시 SHA-256 중복 검사 후 저장

### Uploaded Files

각 파일 row에서 아래 작업을 제공

- `Weaviate Ingest` 버튼
- `Neo4j Ingest` 버튼
- `Weaviate Delete` 버튼
- `Neo4j Delete` 버튼
- `File Delete` 버튼(옵션에 따라 원격 데이터 삭제 포함)
- `Sync Weaviate Status`, `Sync Neo4j Status` 버튼

### Summary

- `Refresh Weaviate Summary`
- 클래스 목록, target class count, 문서별 chunk 통계(문단/테이블/이미지 세부) 확인
- `Refresh Neo4j Summary`
- label 기준 문서/청크/엔티티/관계 통계 확인

## API 연동

- `POST /run` : ingestion 실행 (요청에 `weaviate_enabled`, `neo4j_enabled` 포함)
- `DELETE /chunks` : Weaviate chunk 삭제
- `DELETE /graph` : Neo4j graph 삭제
- `GET /health*` : 시스템/스토리지 상태 확인

## 트러블슈팅

1. `Connection refused`
   - `INGESTION_API_URL`/포트 확인
   - `ingestion-api` 실행 여부 확인

2. Neo4j 관련 실패
   - `NEO4J_URI`, 계정, DB 이름 확인
   - `Neo4j Live Check` 먼저 확인

3. Weaviate summary가 비어 보임
   - 선택한 `Class / Label`과 실제 적재 class 일치 여부 확인

4. OpenAI 관련 오류(`401`, `429`)
   - OpenAI 키/쿼터 상태 확인(실제 호출은 backend에서 수행)

## TO-DO

1. Batch 작업 고도화
   - 다중 row 선택 후 Weaviate/Neo4j 일괄 Ingest/Delete
   - 작업별 진행률(progress bar)과 성공/실패 건수 요약 표시

2. 실행 이력/감사 로그
   - row 단위 작업 이력(누가/언제/무엇을 실행) UI 표시
   - 실패 원인(last_error) 분류 및 재실행 가이드 제공

3. 재시도/복구 기능
   - 실패 건 자동 재시도(지수 백오프) 옵션
   - 중단된 요청(REQUESTED/RUNNING 장기 지속) 탐지 및 복구 액션

4. 상태 정합성 강화
   - SQLite 상태 vs Weaviate 실제 데이터 vs Neo4j 실제 데이터 불일치 탐지
   - Sync 결과를 파일별 리포트 형태로 표시

5. 검색/필터 UX 개선
   - 파일명, class, status, company_id, machine_cat, machine_id 필터
   - 정렬, 페이지네이션, 최근 변경순 기본 정렬

6. Summary 확장
   - Weaviate/Neo4j summary 비교 뷰(동일 class 기준)
   - 클래스별/문서별 시계열 변화(증감) 표시

7. 운영 안전장치
   - 삭제 전 확인 모달(Weaviate/Neo4j/File 각각)
   - 위험 작업에 대한 dry-run 모드 제공

8. 입력 포맷 확장
   - PDF 외 CSV/DOCX/XLSX/PPTX/TXT 업로드/검증 경로 추가
   - 포맷별 파싱 가능 여부 사전 점검(Preflight) 기능
