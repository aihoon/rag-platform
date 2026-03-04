# rag-platform

## 목적

`rag-platform`은 다양한 RAG를 구현한 reference code 저장소입니다.

이 저장소는 아래 4개 서비스로 구성됩니다.

- 메인 API 프로젝트
  - `ingestion-api`: 문서 ingestion 및 vector DB 적재
  - `rag-api`: 질의 처리 및 RAG 응답 생성
- 테스트/운영 UI 프로젝트
  - `ingestion-ui`: 업로드/적재/삭제/상태 확인 UI
  - `rag-ui`: chat 요청/응답 검증 UI

핵심 의도는 다음과 같습니다.

- ingestion 파이프라인과 RAG 응답 파이프라인을 분리
- 각 파이프라인을 UI로 빠르게 검증
- 실험/개발 시 단일 repo에서 end-to-end 동작 확인

## 구성

```text
rag-platform/
  ingestion-api/    # FastAPI, ingestion backend
  ingestion-ui/     # Streamlit, ingestion frontend
  rag-api/          # FastAPI, RAG backend
  rag-ui/           # Streamlit, RAG frontend
  shared/           # shared schema/utils/logger/services
  .env
  .gitignore
  Pipfile
  Pipfile.lock
  README.md
```

## 핵심 Infrastructure

이 프로젝트는 아래 3개 인프라를 기준으로 동작합니다.

- `SQLite`: 업로드 메타데이터 저장
- `Weaviate`: vector DB 저장/검색
- `OpenAI`: embedding 및 LLM 호출

### 1) SQLite

역할:

- `ingestion-ui`가 업로드 파일 메타데이터를 로컬 DB에 저장
- `ingestion-api`가 동일 DB를 읽어 ingestion 대상 파일을 조회

사용 방식:

- 별도 서버 실행 없이 파일 기반으로 동작
- 기본 경로: `ingestion-ui/data/ingestion_ui.db`
- `ingestion-ui` 실행 시 필요한 테이블/컬럼 자동 보정(정책 범위 내)

점검:

- `ingestion-ui` 사이드바의 `SQLite DB Live Check` 버튼
- 또는 `ingestion-api` 헬스 엔드포인트 `/health/sqlite-live`

### 2) Weaviate

역할:

- ingestion된 chunk vector와 메타데이터 저장
- RAG 검색 대상 vector index 제공

사용 방식:

- 로컬 Docker(또는 외부 Weaviate) 연결
- 기본 URL: `http://localhost:8080`
- 단일 class(`RagDocumentChunk`) 사용 + `company_id` 메타 필터

점검:

- 브라우저: [http://localhost:8080/v1/meta](http://localhost:8080/v1/meta)
- 브라우저: [http://localhost:8080/v1/schema](http://localhost:8080/v1/schema)
- `ingestion-ui`의 `Weaviate Live Check` / `Weaviate Summary`
- `shared/services/weaviate_summary_service.py`를 `ingestion-api`, `rag-api`가 공통 사용

### 3) Neo4j

역할:

- Graph RAG를 위한 엔티티/관계 그래프 저장
- Graph 기반 질의/탐색 및 관계 추론 지원

사용 방식:

- 로컬 Docker(또는 외부 Neo4j) 연결
- 기본 URL: `http://localhost:7474` (Browser UI)
- Bolt 포트: `7687` (드라이버 연결)
  - 기본 계정: `neo4j` / `<password> neo4j_password`

점검:

- 브라우저: `http://localhost:7474`
- Cypher 테스트: `RETURN 1;`
- `shared/services/neo4j_summary_service.py`를 `ingestion-api`, `rag-api`가 공통 사용

#### GraphRAG 스키마 (요약)
###
- `(:Document)` 문서 메타
- `(:Chunk)` 문서 chunk
- `(:Entity)` 엔티티
- `(:Document)-[:HAS_CHUNK]->(:Chunk)`
- `(:Chunk)-[:MENTIONS]->(:Entity)`
- `(:Entity)-[:RELATED {type}]->(:Entity)`
###
#### Neo4j 적재 흐름 (요약)
###
1. ingestion에서 chunk 생성
2. chunk에서 트리플 추출(LLM)
3. Document/Chunk/Entity 노드 upsert
4. HAS_CHUNK / MENTIONS / RELATED 관계 upsert

### 4) OpenAI

역할:

- `ingestion-api`: text chunk embedding 생성
- `rag-api`: 질의 분석/응답 생성 등 LLM 호출

사용 방식:

- `.env`에 `OPENAI_API_KEY` 설정
- quota/billing 상태가 정상이어야 함 (`401`, `429` 오류 주의)

점검:

- ingestion 실행 시 embedding 단계 에러 여부 확인
- `401`: invalid key
- `429`: insufficient quota/rate limit

### 5) Infrastructure 사용 흐름

1. `ingestion-ui`가 PDF와 메타데이터를 `SQLite`에 저장
2. `ingestion-api`가 `SQLite`에서 파일 정보를 읽음
3. `ingestion-api`가 `OpenAI`로 embedding 생성
4. 생성된 vector를 `Weaviate`에 적재
5. `rag-api`가 `Weaviate`를 조회하고 `OpenAI`로 최종 응답 생성

## Server and Port Configuration
| name                                    | port              | remark                                                |
|-----------------------------------------|-------------------|-------------------------------------------------------|
| ingestion-ui Streamlit client (host)    | `8501`            | Streamlit default `8501`                              |
| rag-ui Streamlit client (host)          | `8502`            | Default 는 `8501`이지만, `ingestion-ui`가 사용하고 있음          |
| rag-ui Open WebUI client (host)         | `8503`            | Custom port, container 내부에서는 `8080` 사용, `8503:8080`   |
| Nginx load balancer for Open WebUI      | `8504`            | Custom port, container 내부에서는 `80` 사용, `8504:80`       |
| ingestion-api FastAPI endpoint (host)   | `4590`            | Custom port, Uvicorn/FastAPI 기본 포트는 보통 `8000`         |
| rag-api FastAPI endpoint (host)         | `4591`            | Custom port                                           |
| Weaviate API (host)                     | `8080`            | Weaviate HTTP API 기본 포트, `8080:8080`                  |
| Weaviate gRPC (host)                    | `50051`           | Weaviate gRPC 포트, `50051:50051`                       |
| Neo4j Browser (host)                    | `7474`            | Neo4j Browser 기본 포트, `7474:7474`                      |
| Neo4j Bolt (host)                       | `7687`            | Neo4j Bolt 기본 포트, `7687:7687`                         |
| --------------------------------------- | ----------------- | ----------------------------------------------------- |
| Weaviate container internal ports       | `8080`, `50051`   | Docker 컨테이너 내부 포트                                     |
| Neo4j container internal ports          | `7474`, `7687`    | Docker 컨테이너 내부 포트                                     |
| Open WebUI container internal ports     | `8080`            | Docker 컨테이너 내부 포트                                     |
| Nginx internal ports                    | `80`              | Docker 컨테이너 내부 포트                                     |

### Open WebUI Test Path

```text
Browser -> localhost:3000 -> Open WebUI container:8080
### Open WebUI -> localhost:8081 -> Nginx LB container:8081
Open WebUI -> localhost:4592 -> Nginx LB container:4592
### Nginx LB -> host.docker.internal:8001 -> rag-api
Nginx LB -> host.docker.internal:4591 -> rag-api
```

주의: Docker container internal port는 container 내부에서만 의미가 있습니다.
호스트에서 중요한 것은 `ports:`로 publish한 host port이며, host port끼리만 충돌하지 않으면 됩니다.

## 사전 준비

### 1. Python / Pipenv

```bash
pipenv --python 3.11
pipenv install
```

### 2. Weaviate (로컬)

* 최초 1회(컨테이너 생성)

```bash
docker run -d --name weaviate \
  -p 8080:8080 \
  -p 50051:50051 \
  -e QUERY_DEFAULTS_LIMIT=25 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  -e DEFAULT_VECTORIZER_MODULE=none \
  semitechnologies/weaviate:1.34.4
```

* 다음부터(이미 생성된 컨테이너 재시작):
```bash
docker start weaviate
```

* 상태 확인:

```bash
docker ps
docker logs --tail 100 weaviate
```
### 3. neo4j (로컬)

* 디렉터리 준비
```bash
mkdir -p ./shared/neo4j/data ./shared/neo4j/logs ./shared/neo4j/import ./shared/neo4j/plugins
```
* 컨테이너 생성(최초 1회):
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -v $(pwd)/shared/neo4j/data:/data \
  -v $(pwd)/shared/neo4j/logs:/logs \
  -v $(pwd)/shared/neo4j/import:/import \
  -v $(pwd)/shared/neo4j/plugins:/plugins \
  -e NEO4J_AUTH=neo4j/neo4j_password \
  neo4j:5
```
* 종료
```bash
docker stop neo4j
```
* 재시작
```bash
docker start neo4j
```
* 상태 확인:
```bash
docker ps
docker logs --tail 100 neo4j
```
* 브라우저를 통한 접속 확인
  * http://localhost:7474
  * account: neo4j / neo4j_password
* Neo4j 런타임 데이터/로그 디렉터리는 `shared/neo4j`를 사용

### 4. openwebui 와 nginx load balancer (로컬)

#### Stop and restart

```bash
docker compose -f deploy/docker-compose.openwebui-rag.yml down
docker compose -f deploy/docker-compose.openwebui-rag.yml up -d
```

3. `.env` 기본 확인

- `OPENAI_API_KEY`
- `WEAVIATE_URL`
- `INGESTION_API_URL` (`http://localhost:8000/ingestion-api`)
- `RAG_API_URL` (`http://localhost:8000/rag-api`)

참고:
- `ingestion-api`와 `rag-api`를 동시에 띄우려면 포트 분리가 필요합니다.
### - 이 README는 `rag-api=8000`, `ingestion-api=8001` 기준으로 작성했습니다.
## 서비스 문서 링크

서비스별 상세 실행 방법/기능 설명/트러블슈팅은 각 README를 참고합니다.

- `ingestion-api`: [ingestion-api/README.md](ingestion-api/README.md)
- `ingestion-ui`: [ingestion-ui/README.md](ingestion-ui/README.md)
- `rag-ui`: [rag-ui/README.md](rag-ui/README.md)
- `rag-api`: [rag-api/](rag-api/)

## End-to-End 권장 순서 (문서 링크 기준)

1. Weaviate 실행
2. `ingestion-api` 실행: [ingestion-api/README.md](ingestion-api/README.md)
3. `ingestion-ui` 실행/적재: [ingestion-ui/README.md](ingestion-ui/README.md)
4. `rag-api` 실행: `rag-api` 문서 참고
5. `rag-ui` 실행/검증: [rag-ui/README.md](rag-ui/README.md)

## 공통 메모

- 현재는 root `Pipfile` 하나로 4개 서비스를 함께 관리합니다.
