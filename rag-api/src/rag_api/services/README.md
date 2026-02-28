# rag-api services

## 목적

`rag-api`의 서비스 레이어는 RAG 파이프라인의 핵심 로직을 담당합니다.  
현재는 `standard_rag_service.py`와 `conversational_rag_service.py` 두 가지가 있으며,
rag-ui 의 `ragType`에 따라 분기됩니다.

## Standard RAG

**정의**
- 현재 질문을 그대로 검색 쿼리로 사용하여 벡터 검색 후 답변을 생성하는 기본 RAG

**흐름**
1. `user_input` 임베딩 생성 (OpenAI Embeddings 호출) 
2. Weaviate에서 유사도 검색 (`nearVector`, `top_k`) 
3. 검색 결과를 컨텍스트로 구성 
4. 컨텍스트 + 히스토리(있으면) 기반 답변 생성 (LLM 호출)

**특징**
- 단일 질의 중심
- 후속 질문(지시어/대화 맥락 의존)에 약함
- 구현 단순, 응답 예측 가능

**핵심 모듈**
- `standard_rag_service.py`
- `rag_service_utils.py` (공통 유틸: retrieval, context build, generate 등)

**Standard RAG TODO**

아래 항목은 단계적 개선을 위한 후속 작업입니다.

1. 컨텍스트 길이 제어를 토큰 기준으로 전환
- `rag_max_context_chars` 대신 토큰 기반 절단으로 모델 한도 안정화

2. 검색 결과 없음 처리 개선
- `chunks`가 비어 있으면 LLM 호출 스킵 및 명시적 응답

3. Weaviate 필터 타입 정합성
- `machine_id` 타입에 맞는 `valueInt`/`valueText` 사용 및 escape 처리

4. Retrieval 품질 개선
- Hybrid/BM25, MMR, rerank 도입 옵션화

5. LLM/Embedding 클라이언트 재사용
- 요청마다 생성하지 않도록 캐시/싱글턴 적용

6. 네트워크 안정성
- Weaviate/OpenAI 호출 재시도 및 백오프 정책

7. 컨텍스트 포맷 개선
- citation 포맷 표준화 (예: `[S1]`) 및 source 매핑

8. 거리 필터 기준 명확화
- `rag_min_score_distance` 의미 정리 및 설정명 개선 검토

9. 히스토리 포맷 안전성
- `role`/`content` 누락 및 오염 데이터 방어 로직

10. 중복/유령 파일 정리
- `rag_service.pyy` 중복 파일 제거 또는 통합
 
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

## Corrective RAG

**정의**
- 검색 결과를 LLM으로 relevance self-grading 한 뒤, 부족하면 쿼리를 재작성해 재검색하는 RAG

**흐름**
1. `user_input` 임베딩 생성 및 1차 검색 (OpenAI Embeddings 호출)
2. 검색 결과 relevance self-grading (LLM 호출)
3. 기준 미달 시 쿼리 재작성 후 재검색 (LLM 호출 + OpenAI Embeddings 호출)
4. 최종 컨텍스트로 답변 생성 (LLM 호출)

**핵심 모듈**
- `corrective_rag_service.py`
- `rag_service_utils.py` (공통 유틸)

**Corrective RAG TODO**
###
아래 항목은 성능 개선 및 프로덕션 안정화를 위한 후속 작업입니다.
###
1. Relevance grader 효율화
- 배치 판정 또는 소형 모델로 교체해 비용/지연 감소
###
2. 판정 기준 정교화
- yes/no 대신 score 반환, threshold 동적 조정
###
3. Fallback 전략 다양화
- 쿼리 재작성 외에 BM25/Hybrid/Multi-query 추가
###
4. Retry/Fail-safe 강화
- 재시도 횟수별 전략 분기, 타임아웃 시 degrade 응답
###
5. Observability
- `usedFallback`, `relevanceRatio` 등 메타 지표 로그/트레이싱
###
6. 캐시 도입
- 동일 query에 대한 grading/답변 캐시
###
7. 안전장치
- 컨텍스트 부족 시 명시적 거절/추가 질문
###
8. 평가/벤치마크
- 표준 질문 세트로 CRAG vs Standard 비교 지표 확보
