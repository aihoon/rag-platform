# rag-api services

## 목적

`rag-api`의 서비스 레이어는 RAG 파이프라인의 핵심 로직을 담당합니다.  
현재는 `standard_rag_service.py`와 `conversational_rag_service.py` 두 가지가 있으며,
rag-ui 의 `ragType`에 따라 분기됩니다.

## Standard RAG

**정의**
- 현재 질문을 그대로 검색 쿼리로 사용하여 벡터 검색 후 답변을 생성하는 기본 RAG

**흐름**
1. `user_input` 임베딩 생성 (OpenAI Embeddings 호출) ###
2. Weaviate에서 유사도 검색 (`nearVector`, `top_k`) ###
3. 검색 결과를 컨텍스트로 구성 ###
4. 컨텍스트 + 히스토리(있으면) 기반 답변 생성 (LLM 호출) ###

**특징**
- 단일 질의 중심
- 후속 질문(지시어/대화 맥락 의존)에 약함
- 구현 단순, 응답 예측 가능

**구현 기능** ###
- `user_input` 임베딩 생성 ### ###
- Weaviate `nearVector` 검색 ### ###
- 검색 결과 컨텍스트 구성 ### ###
- 히스토리 포맷 후 답변 생성 ### ###

**핵심 모듈**
- `standard_rag_service.py`
- `rag_service_utils.py` (공통 유틸: retrieval, context build, generate 등)

**Standard RAG TODO**

아래 항목은 단계적 개선을 위한 후속 작업입니다.

1. 컨텍스트 길이 제어를 토큰 기준으로 전환 ###
- `rag_max_context_chars` 대신 토큰 기반 절단으로 모델 한도 안정화 ###

2. 검색 결과 없음 처리 개선 ###
- `chunks`가 비어 있으면 LLM 호출 스킵 및 명시적 응답 ###

3. Weaviate 필터 타입 정합성 ###
- `machine_id` 타입에 맞는 `valueInt`/`valueText` 사용 및 escape 처리 ###

4. Retrieval 품질 개선 ###
- Hybrid/BM25, MMR, rerank 도입 옵션화 ###

5. LLM/Embedding 클라이언트 재사용 ###
- 요청마다 생성하지 않도록 캐시/싱글턴 적용 ###

6. 네트워크 안정성 ###
- Weaviate/OpenAI 호출 재시도 및 백오프 정책 ###

7. 컨텍스트 포맷 개선 ###
- citation 포맷 표준화 (예: `[S1]`) 및 source 매핑 ###

8. 거리 필터 기준 명확화 ###
- `rag_min_score_distance` 의미 정리 및 설정명 개선 검토 ###

9. 히스토리 포맷 안전성 ###
- `role`/`content` 누락 및 오염 데이터 방어 로직 ###

10. 중복/유령 파일 정리 ###
- `rag_service.pyy` 중복 파일 제거 또는 통합 ###
 
## Conversational RAG

**정의**
- 대화 히스토리를 기반으로 **standalone 질문을 생성**한 뒤 검색/응답을 수행하는 RAG

**흐름**
1. `user_input` + 히스토리 기반 **standalone 질문 생성** (LLM 호출)
2. standalone 질문 임베딩 생성 (OpenAI Embeddings 호출)
3. Weaviate에서 유사도 검색
4. 컨텍스트 + 히스토리 기반 답변 생성 (LLM 호출)

**특징**
- 후속 질문 처리에 강함
- 대화 흐름 유지 가능
- 단계가 늘어나 성능 튜닝 포인트가 많음

**핵심 모듈**
- `conversational_rag_service.py`
- `rag_service_utils.py` (공통 유틸)

**구현 기능** ###
- standalone 질문 생성 ### ###
- standalone 질문 임베딩 생성 ### ###
- Weaviate 검색 ### ###
- 히스토리 포함 답변 생성 ### ###

**Conversational RAG TODO**

아래 항목은 성능 개선을 위한 후속 작업입니다.

1. Query rewrite 품질 강화
- 프롬프트 개선, 출력 길이 제한, "불필요하면 원문 유지" 규칙 추가

2. Retrieval 최적화
- 히스토리 기반 필터링(최근 turn 중심), `top_k` 동적 조정

3. 답변 스타일 분기
- 대화형 톤/요약/확인 질문 등 대화 UX 제어

4. 히스토리 요약(메모리 압축)
- 긴 대화에서 히스토리를 요약해 context 길이 관리

5. Guardrail
- 컨텍스트 부족 시 "모른다"를 명시하도록 강제

## Corrective RAG ###

**정의** ###
- 검색 결과를 LLM으로 relevance self-grading 한 뒤, 부족하면 쿼리를 재작성해 재검색하는 RAG ###

**흐름** ###
1. `user_input` 임베딩 생성 및 1차 검색 (OpenAI Embeddings 호출) ###
2. 검색 결과 relevance self-grading (LLM 호출) ###
3. 기준 미달 시 쿼리 재작성 후 재검색 (LLM 호출 + OpenAI Embeddings 호출) ###
4. 최종 컨텍스트로 답변 생성 (LLM 호출) ###

**핵심 모듈** ###
- `corrective_rag_service.py` ###
- `rag_service_utils.py` (공통 유틸) ###

**구현 기능** ### ###
- 1차 검색 후 relevance self-grading ### ###
- 기준 미달 시 쿼리 재작성/재검색 ### ###
- 최종 컨텍스트로 답변 생성 ### ###

**Corrective RAG TODO** ###

아래 항목은 성능 개선 및 프로덕션 안정화를 위한 후속 작업입니다. ###

1. Relevance grader 효율화 ###
- 배치 판정 또는 소형 모델로 교체해 비용/지연 감소 ###

2. 판정 기준 정교화 ###
- yes/no 대신 score 반환, threshold 동적 조정 ###

3. Fallback 전략 다양화 ###
- 쿼리 재작성 외에 BM25/Hybrid/Multi-query 추가 ###

4. Retry/Fail-safe 강화 ###
- 재시도 횟수별 전략 분기, 타임아웃 시 degrade 응답 ###

5. Observability ###
- `usedFallback`, `relevanceRatio` 등 메타 지표 로그/트레이싱 ###

6. 캐시 도입 ###
- 동일 query에 대한 grading/답변 캐시 ###

7. 안전장치 ###
- 컨텍스트 부족 시 명시적 거절/추가 질문 ###

8. 평가/벤치마크 ###
- 표준 질문 세트로 CRAG vs Standard 비교 지표 확보 ###

## Adaptive RAG ###

**정의** ###
- 질문 특성과 대화 맥락에 따라 적절한 RAG 전략을 동적으로 선택하는 RAG ###

**흐름** ###
1. 히스토리 존재 여부 확인 ###
- 히스토리가 있으면 conversational 경로로 고정 ###

2. 히스토리가 없으면 라우팅 수행 ### ###
- 간단 휴리스틱(키워드)로 1차 분기 후, 필요 시 라우팅 LLM 호출 ### ###
- 입력 질문을 기준으로 `standard` vs `corrective` vs `self_rag` vs `fusion` 분기 ### ###

3. 선택된 경로 실행 ###
- `standard`: 임베딩 생성(OpenAI Embeddings) → 벡터 검색 → 컨텍스트 구성 → 답변 생성(LLM 호출) ###
- `conversational`: standalone 질문 생성(LLM 호출) → 임베딩 생성(OpenAI Embeddings) → 벡터 검색 → 답변 생성(LLM 호출) ###
- `corrective`: 1차 임베딩/검색 → relevance self-grading(LLM 호출) → 필요 시 쿼리 재작성(LLM 호출) 후 재검색 → 답변 생성(LLM 호출) ###
- `self_rag`: retrieval 필요 여부 판단(LLM 호출) → 필요 시 임베딩/검색 → 답변 생성(LLM 호출) → 근거 self-grading(LLM 호출) → 필요 시 재검색 ### ###
- `fusion`: 다중 쿼리 생성(LLM 호출) → 다중 임베딩/검색 → RRF 결합 → 답변 생성(LLM 호출) ### ###
- `hyde`: 가설 답변 생성(LLM 호출) → 가설 임베딩/검색 → 답변 생성(LLM 호출) ### ###
- `graph`: 초기 검색 → 관계/트리플 추출(LLM 호출) → 그래프 컨텍스트 기반 답변(LLM 호출) ### ###

**핵심 모듈** ###
- `adaptive_rag_service.py` ###
- `standard_rag_service.py` ###
- `conversational_rag_service.py` ###
- `corrective_rag_service.py` ###
- `self_rag_service.py` ### ###
- `fusion_rag_service.py` ### ###
- `hyde_rag_service.py` ### ###
- `graph_rag_service.py` ### ###

**구현 기능** ### ###
- 히스토리 존재 시 conversational 고정 ### ###
- 휴리스틱/LLM 라우팅으로 전략 선택 ### ###
- 선택된 하위 전략 실행 및 결과 반환 ### ###
- 라우팅 메타/로그 기록 ### ###

**Adaptive RAG TODO** ###

1. 라우팅 프롬프트 개선 ###
- 오탐 최소화, category 세분화 ###

2. 라우팅 모델 분리 ###
- 저비용 모델로 교체 및 캐시 ###

3. 정책 기반 라우팅 ###
- 휴리스틱(길이, 키워드, 도메인) + LLM 혼합 ###

4. 실패 대비 ###
- 라우팅 실패 시 standard fallback ###

5. 평가 ###
- 라우팅 정확도 및 비용/지연 지표 수집 ###
###
**Adaptive RAG 메타 지표** ###
- `adaptiveRoute`, `adaptiveReason`, `adaptiveRouterSource`, `adaptiveRouterRaw` ###
###
**Adaptive RAG 라우팅 로그** ###
- `ADAPTIVE_ROUTER_LOG_PATH`에 CSV 적재 (timestamp, route, reason, source, raw, chat_history, input_len, company_id, machine_id, machine_cat) ###

## Self-RAG ###
###
**정의** ###
- LLM이 답변 생성 과정에서 “retrieval 필요 여부”와 “근거 충분성”을 스스로 평가하는 RAG ###
###
**흐름** ###
1. Retrieval 필요 여부를 LLM으로 판단 (retrieve-on-demand) ###
2. 필요 시 임베딩 생성(OpenAI Embeddings) → 벡터 검색 ###
3. 컨텍스트 기반 답변 생성 (LLM 호출) ###
4. 답변 근거 충분성 self-grading (LLM 호출) ###
5. 부족하면 쿼리 재작성(LLM 호출) 후 재검색/재답변 ###
###
**핵심 모듈** ###
- `self_rag_service.py` ###
- `rag_service_utils.py` (공통 유틸) ###
###
**구현 기능** ### ###
- retrieval 필요 여부 판단 ### ###
- 답변 근거 self-grading ### ###
- 재검색/재답변 루프 ### ###
###
**Self-RAG TODO** ###
###
1. Retriever/Grader 모델 분리 ###
- 경량 모델로 교체해 비용/지연 감소 ###
###
2. Grading 기준 강화 ###
- yes/no 대신 score 기반, threshold 동적 조정 ###
###
3. Multi-step 개선 ###
- 실패 이유별 다른 재검색 전략 ###
###
참고 ###
- 현재 구현은 Self-RAG 논문/공식 코드의 reflection token 기반 방식이 아닌, LLM 평가/라우팅으로 근사한 버전 ###

## Fusion RAG ### ###
###
**정의** ### ###
- 여러 개의 검색 쿼리를 생성하고, 각 검색 결과를 RRF(Reciprocal Rank Fusion)로 결합하는 RAG ### ###
###
**흐름** ### ###
1. LLM으로 다중 쿼리 생성 ### ###
2. 각 쿼리 임베딩 생성(OpenAI Embeddings) → 벡터 검색 ### ###
3. 검색 결과를 RRF로 결합/재정렬 ### ###
4. 결합된 컨텍스트로 답변 생성(LLM 호출) ### ###
###
**핵심 모듈** ### ###
- `fusion_rag_service.py` ### ###
- `rag_service_utils.py` (공통 유틸) ### ###
###
**구현 기능** ### ###
- 다중 쿼리 생성 ### ###
- 쿼리별 검색 ### ###
- RRF 결합 후 답변 생성 ### ###
###
**Fusion RAG TODO** ### ###
###
1. 쿼리 다양성 강화 ### ###
- 중복 제거 및 query clustering ### ###
###
2. RRF 파라미터 튜닝 ### ###
- `fusion_rrf_k`, top_k 조정 ### ###
###
3. Hybrid 검색 결합 ### ###
- BM25 + Vector 혼합 후 RRF ### ###
###
4. 쿼리 생성 비용 절감 ### ###
- 경량 모델 분리 또는 캐시 ### ###
###
5. 중복 문서 정규화 ### ###
- 문서 ID 기반 dedup 강화 ### ###
###
6. 컨텍스트 길이 최적화 ### ###
- 중복 제거/요약을 통한 context 압축 ### ###
###
7. 메타/평가 지표 확장 ### ###
- `fusionRetrievedTotal`, `fusionUniqueDocs`, `fusionRrfK` 등 추가 ### ###

## HyDE RAG ### ###
###
**정의** ### ###
- 가설 답변(가상의 문서)을 생성해 그 임베딩으로 검색을 수행하는 RAG ### ###
###
**흐름** ### ###
1. LLM으로 가설 답변 생성 ### ###
2. 가설 답변 임베딩 생성(OpenAI Embeddings) → 벡터 검색 ### ###
3. 검색 결과 기반 답변 생성(LLM 호출) ### ###
###
**핵심 모듈** ### ###
- `hyde_rag_service.py` ### ###
- `rag_service_utils.py` (공통 유틸) ### ###
###
**구현 기능** ### ###
- 가설 답변 생성 ### ###
- 가설 임베딩 검색 ### ###
- 컨텍스트 기반 답변 생성 ### ###
###
**HyDE RAG TODO** ### ###
###
1. 가설 답변 품질 강화 ### ###
- 도메인 프롬프트/가설 길이 제한 튜닝 ### ###
###
2. 다중 가설 지원 ### ###
- 여러 가설 생성 후 RRF/합성 ### ###
###
3. HyDE + Fusion 결합 ### ###
- HyDE 쿼리를 Fusion 파이프라인에 연결 ### ###
###
4. 가설 생성 모델 분리 ### ###
- 경량 모델로 비용/지연 절감 ### ###
###
5. Self-Critique ### ###
- 가설 품질 점검 후 재작성 ### ###
###
6. 메타/평가 지표 ### ###
- `hydeHypothesisLen`, `hydeUsedHypothesis` 등 추가 ### ###

## Graph RAG ### ###
###
**정의** ### ###
- 검색된 문서에서 엔티티/관계 트리플을 추출해 그래프 컨텍스트로 답변하는 RAG ### ###
###
**흐름** ### ###
1. 1차 벡터 검색 ### ###
2. LLM으로 엔티티/관계 트리플 추출 ### ###
3. 그래프 컨텍스트 + 원문 컨텍스트로 답변 생성 ### ###
###
**핵심 모듈** ### ###
- `graph_rag_service.py` ### ###
- `rag_service_utils.py` (공통 유틸) ### ###
###
**구현 기능** ### ###
- 1차 검색 후 트리플 추출 ### ###
- 트리플 기반 2차 검색(옵션) ### ###
- 그래프 컨텍스트 포함 답변 생성 ### ###
###
**Graph RAG TODO** ### ###
###
1. 그래프 품질 향상 ### ###
- 트리플 정규화/중복 제거 ### ###
###
2. 그래프 기반 재검색 ### ###
- 트리플 중심으로 2차 검색 ### ###
###
3. 그래프 스토리지 연동 ### ###
- Neo4j 등 그래프 DB 연결 ### ###
###
**Graph RAG 메타 지표** ### ###
- `graphTriples`, `graphRetrievalTopK`, `graphSecondRetrieval` ### ###

## Agentic RAG ### ###
###
**정의** ### ###
- 여러 하위 RAG 전략을 실행한 뒤, LLM이 최적 답변을 선택하는 상위 오케스트레이션 ### ###
###
**흐름** ### ###
1. 후보 전략 목록 로딩 (`AGENTIC_CANDIDATES`) ### ###
2. 각 전략 실행 및 결과 수집 ### ###
3. LLM이 후보 답변 중 최적 선택 ### ###
4. 선택된 답변 반환 ### ###
###
**핵심 모듈** ### ###
- `agentic_rag_service.py` ### ###
###
**구현 기능** ### ###
- 후보 전략 실행 ### ###
- LLM 선택으로 최적 답변 결정 ### ###
- 선택 결과 메타 기록 ### ###
###
**Agentic RAG TODO** ### ###
###
1. 비용 제어 ### ###
- 후보 수/모델 분리 ### ###
###
2. 후보 결과 합성 ### ###
- 단일 선택 대신 합성/교차검증 ### ###
###
3. 평가 지표 ### ###
- 후보별 점수/선택 로그 ### ###
