# rag-api

## 목적

`rag-api`는 RAG 플랫폼의 질의 처리(standard / conversational / corrective / adaptive / self_rag / fusion / hyde / graph RAG)를 담당하는 FastAPI 서비스입니다. ### ###

## RAG 계층 구조 (상위/하위)

이 저장소에서의 정의:
- **하위 레이어 (전략/기법)**: 하나의 질문 처리 흐름을 규정하는 RAG 전략. 예: Standard, Conversational, Corrective, Self-RAG, HyDE, Fusion, GraphRAG.
- **상위 레이어 (오케스트레이션)**: 어떤 전략을 선택/조합할지 결정하는 라우팅/제어 레이어. 예: Adaptive RAG, Agentic RAG.

즉, **Adaptive/Agentic은 여러 하위 전략을 “선택하거나 조합”하는 상위 레이어**이고, Standard/Conversational/Corrective/Self-RAG/HyDE/Fusion/GraphRAG는 **각각 독립적인 하위 전략**입니다.

 하위 레이어 설명 (전략별)

1. Standard RAG
- 기본 벡터 검색 + 컨텍스트 답변 생성. 가장 단순한 하위 전략.

2. Conversational RAG
- 대화 히스토리를 고려해 standalone 질문을 만들고 검색/응답. 하위 전략.

3. Corrective RAG
- 검색 결과를 LLM으로 self-grading하고 부족하면 쿼리 재작성/재검색. 하위 전략.
 - `TAVILY_API_KEY`가 설정되면 부족한 경우 외부 검색 결과를 추가로 합성. ### ###
 - 외부 검색 결과는 `externalSources` 필드와 `meta.externalSources`로 함께 제공. ### ###

4. Self-RAG
- LLM이 자신의 답변을 평가/수정하며 근거 부족 시 재검색. 하위 전략.

5. HyDE
- 가상의 답변(가설 문서)을 먼저 생성하고 그 임베딩으로 검색하는 전략. 하위 전략.

6. Fusion RAG
- 다중 쿼리/다중 검색 결과를 결합(fusion)해 최종 컨텍스트를 구성. 하위 전략.

7. GraphRAG
- 그래프(엔티티/관계) 기반 검색/추론을 이용하는 전략. 하위 전략.

 상위 레이어 설명 (오케스트레이션)

1. Adaptive RAG
- 질문 특성/대화 여부/휴리스틱/라우팅 LLM 등을 이용해 **하위 전략 중 하나를 선택**.
- 예: 히스토리 있으면 Conversational, 모호하면 Corrective, 단순하면 Standard.

2. Agentic RAG
- 목표 달성을 위해 **여러 하위 전략을 순차/병렬로 실행**하고 결과를 비교/합성하는 상위 레이어.
- 예: Corrective → Self-RAG → Fusion 순으로 시도하거나, HyDE + Standard를 병렬 실행 후 통합.

 상위 ↔ 하위 관계 예시

- Adaptive RAG (상위)
  - Standard RAG (하위)
  - Conversational RAG (하위)
  - Corrective RAG (하위)
  - (추가 시) Self-RAG / HyDE / Fusion / GraphRAG

- Agentic RAG (상위)
  - Corrective RAG (하위)
  - Self-RAG (하위)
  - HyDE (하위)
  - Fusion RAG (하위)
  - GraphRAG (하위)

정리하면, **Adaptive/Agentic은 “여러 하위 RAG를 고르는/조합하는 상위 제어 레이어”**이고, 나머지 전략들은 “하위 실행 플로우”입니다.

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
- `CRAG_MIN_RELEVANT_DOCS` (default: `1`)
- `CRAG_MIN_RELEVANCE_RATIO` (default: `0.4`)
- `CRAG_MAX_RETRIES` (default: `1`)
- `CRAG_FALLBACK_TOP_K` (default: `8`)
- `CRAG_GRADER_MAX_CHARS` (default: `1200`) ###
 - `TAVILY_API_KEY` (default: empty) ### ###
 - `TAVILY_SEARCH_DEPTH` (default: `basic`) ### ###
 - `TAVILY_MAX_RESULTS` (default: `5`) ### ###
 - `TAVILY_INCLUDE_ANSWER` (default: `true`) ### ###
 - `TAVILY_INCLUDE_RAW_CONTENT` (default: `false`) ### ###
 - `TAVILY_REQUEST_TIMEOUT_SEC` (default: `30`) ### ###
 - `TAVILY_MAX_RETRIES` (default: `2`) ### ###
 - `TAVILY_RETRY_BACKOFF_SEC` (default: `1.0`) ### ###
 - `TAVILY_RESULT_MAX_CHARS` (default: `800`) ### ###
 - `TAVILY_EXTERNAL_LOG_PATH` (default: `./logs/tavily_external_sources.csv`) ### ###
 - `TAVILY_SUMMARY_MAX_TOKENS` (default: `160`) ### ###
 - `TAVILY_SUMMARY_TEMPERATURE` (default: `0.0`) ### ###
- `SELFRAG_RETRIEVAL_TOP_K` (default: `4`) ###
- `SELFRAG_MAX_RETRIES` (default: `1`) ###
- `SELFRAG_GRADER_MAX_CHARS` (default: `1200`) ###
- `SELFRAG_ROUTER_TEMPERATURE` (default: `0.0`) ###
- `SELFRAG_ROUTER_MAX_TOKENS` (default: `32`) ###
- `ADAPTIVE_ROUTER_TEMPERATURE` (default: `0.0`) ### ###
- `ADAPTIVE_ROUTER_MAX_TOKENS` (default: `32`) ### ###
- `ADAPTIVE_ROUTER_LOG_PATH` (default: `./logs/adaptive_router.csv`) ### ###
- `FUSION_QUERY_COUNT` (default: `4`) ### ###
- `FUSION_QUERY_TOP_K` (default: `4`) ### ###
- `FUSION_FINAL_TOP_K` (default: `6`) ### ###
- `FUSION_RRF_K` (default: `60`) ### ###
- `FUSION_QUERY_TEMPERATURE` (default: `0.2`) ### ###
- `FUSION_QUERY_MAX_TOKENS` (default: `120`) ### ###
- `HYDE_RETRIEVAL_TOP_K` (default: `4`) ### ###
- `HYDE_HYPOTHESIS_TEMPERATURE` (default: `0.2`) ### ###
- `HYDE_HYPOTHESIS_MAX_TOKENS` (default: `200`) ### ###
- `GRAPH_RETRIEVAL_TOP_K` (default: `6`) ### ###
- `GRAPH_EXTRACT_MAX_CHARS` (default: `4000`) ### ###
- `GRAPH_EXTRACT_MAX_TOKENS` (default: `300`) ### ###
- `GRAPH_MAX_TRIPLES` (default: `60`) ### ###
- `GRAPH_USE_SECOND_RETRIEVAL` (default: `true`) ### ###
- `GRAPH_SECOND_RETRIEVAL_TOP_K` (default: `4`) ### ###
- `AGENTIC_CANDIDATES` (default: `standard,corrective,self_rag,fusion,hyde,graph`) ### ###
- `AGENTIC_MAX_CANDIDATES` (default: `3`) ### ###
- `AGENTIC_JUDGE_TEMPERATURE` (default: `0.0`) ### ###
- `AGENTIC_JUDGE_MAX_TOKENS` (default: `32`) ### ###
- `WEAVIATE_URL` (default: `http://localhost:8080`)
- `WEAVIATE_LOG_PATH` (default: `./logs/weaviate-db.log`)
- `EMBEDDING_REQUEST_TIMEOUT_SEC` (default: `30`)
### - `WEAVIATE_CLASS_NAME` (default: `RagDocumentChunk`) ### ###
###   - 단일 class 사용, `company_id`는 필터로 동작 ### ###
###   - cross-company 검색은 `companyId`를 생략 ### ###
 - `WEAVIATE_GENERAL_CLASS_NAME` (default: `General`) ### ###
 - `WEAVIATE_MACHINE_CLASS_NAME` (default: `Machine`) ### ###
- `RAG_CHAT_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_API_KEY` (required)

## 요청/응답 예시

### 필터 기본값 ###
- `companyId`, `machineCat`, `machineId` 기본값은 `0` ###
- `machineCat`는 `integer` 타입 ###

```json
POST /chat
{
  "userInput": "질문을 입력하세요",
  "chatId": null,
  "userId": "tester",
  "service": {
    "ragType": "standard",
###     "companyId": 1,
###     "machineId": 10,
###     "machineCat": "A",
    "companyId": 0,
    "machineId": 0,
    "machineCat": 0,
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
###       "machine_id": "10",
      "machine_id": 0,
      "file_upload_id": "12",
###       "machine_cat": "A",
      "machine_cat": 0,
      "distance": 0.23
    }
  ],
  "meta": {
    "chatId": "...",
###     "companyId": 1,
###     "machineId": 10,
###     "machineCat": "A",
    "companyId": 0,
    "machineId": 0,
    "machineCat": 0,
    "ragType": "standard",
    "dashboardId": 123,
    "modelId": 5
  }
}
```
