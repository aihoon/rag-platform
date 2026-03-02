# rag-ui

## 목적

`rag-ui`는 브라우저에서 RAG `/chat` 요청과 응답을 빠르게 검증하기 위한 Streamlit UI

## 핵심 역할

RAG 파이프라인의 운영 콘솔이자 테스트 UI

- `rag-api`의 `/chat` 호출
- JSON 응답 및 streaming(SSE) 응답 모두 표시
- `chatId`를 유지하여 대화 컨텍스트 테스트
- `service` 필드 테스트(`type`, `dashboardId`, `modelId`, extra JSON)

## 동작 구조

1. 사용자 입력
2. `/chat` 요청 전송
3. 응답(JSON 또는 streaming)을 화면에 렌더링
4. `X-Chat-ID` 헤더를 읽어 다음 요청에 재사용

## 구성

- 엔트리 포인트: `rag-ui/app.py`

## 실행 방법

1. 권장 환경 변수 설정

```bash
export RAG_API_URL=http://localhost:8000/rag-api/chat
```

2. UI 실행

```bash
pipenv run streamlit run rag-ui/app.py
```

3. 브라우저 접속

- Streamlit 기본 주소: [http://localhost:8501](http://localhost:8501)

## 사전 실행 조건

1. `rag-api`가 먼저 떠 있어야 함
2. `rag-api`가 `RAG_API_URL`에 의해 접근 가능해야 함
3. (streaming 테스트 시) `rag-api`가 SSE 응답을 지원해야 함

## 화면별 기능 상세

## 1) Sidebar: Connection

- `RAG API Chat URL`
- `Timeout (sec)`

예: `http://localhost:8000/rag-api/chat`

기본값은 `RAG_API_URL`을 그대로 사용합니다.
`/health`, `/health/weaviate-live`, `/health/neo4j-live`, `/health/weaviate-summary`, `/health/neo4j-summary`는 이 URL을 기준으로 자동 계산됩니다.

## 2) Sidebar: Live Checks

- `API Health Check`
- `Weaviate Live Check`
- `Neo4j Live Check`

## 3) Sidebar: Request Fields

- `userId`
- `RAG Type`
- `Class Name` (`General`, `Machine`)
- `Company ID`, `Machine Category`, `Machine ID` (`Machine` 선택 시)
- `Dashboard ID`, `Model ID` (optional)
- `extra JSON` (optional)

`General` 선택 시에는 company/machine 필드를 사용하지 않습니다.

## 4) Sidebar: Summaries

- `Refresh Weaviate Summary`
- `Refresh Neo4j Summary`

현재 선택한 `Class Name`을 기준으로 summary를 조회합니다.

## 5) Conversation

- `Reset conversation`: `chatId`와 메시지 히스토리 초기화
- 메시지 입력 시 `/chat` 호출
- 응답 메시지 + 메타데이터(소스/streaming 여부 등) 표시

## API 연동 스키마

`POST /chat` 요청 필드:

- `userInput`
- `chatId` (optional)
- `userId` (optional)
- `service` (optional)
  - `ragType`
  - `className` (`General` 또는 `Machine`)
  - `companyId`, `machineCat`, `machineId` (`Machine`일 때)
  - `dashboardId`
  - `modelId`
  - extra JSON

응답 필드(예시):

- `message`
- `intent`
- `streaming`
- `sources`
- `meta`

## 환경 변수

- `RAG_API_URL` (기본값: 없음, 있으면 `RAG API Chat URL`의 기본값으로 사용)

## 트러블슈팅

1. `Connection refused`:
- `RAG_API_URL` 포트/호스트 확인
- `rag-api` 실행 여부 확인

2. `HTTP 401` (OpenAI key):
- `OPENAI_API_KEY` 확인 후 `rag-api` 재시작

3. `HTTP 429` (quota):
- OpenAI billing/quota 확인

4. 응답이 비어 있음:
- `rag-api` 로그 확인
- Weaviate에 검색 대상 데이터가 있는지 확인

## TODO (기능 개선 항목)

1. SSE 렌더링 개선
- 토큰 단위 출력 속도/레이아웃 개선

2. 응답 비교
- 동일 질문에 대한 different service type 비교

3. 디버그 패널
- request/response raw payload 토글

4. 히스토리 관리
- conversation export/import
- session 저장/복원
