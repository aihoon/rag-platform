# `ingestion-api services`

## 이 문서의 목적

이 README는 `ingestion-api/src/ingestion_api/services/` 폴더 내 코드 파일들에 대한 다음과 같은 사항을 다룹니다.  

    - 기능
    - 상위 레이어와의 관계 
    - 동작 개선 사항
    - 성능 개선 사항 
    - 연구 기반 구조 개선 방향 
    - Retrieval 춤질과의 정량적 연결 
본 문서는 단순 사용 설명이 아니라, 전문적인 RAG 시스템에서의 ingestion 전략 명세 문서이다.


## 대상 파일:
    - `ingestion_service.py`
    - `vector_delete_service.py`
    - `__init__.py`

## 코드 구성의 원칙 

1. Service interface 표준화  
   - 기능
   - 입력/출력 contract를 파일 간 일관되게 맞추기
   - 예외 타입 분류(`validation`, `external_api`, `infra`) 명확화

2. 책임 분리 강화
- Ingestion 은 다음 단계로 명확히 분리된다.  
  Load 
  → Layout Analysis
  → Cleaning
  → Structuring
  → Chunking
  → Embedding
  → Vector Upsert
  → Metadata Indexing
- parser/chunker/embedding/upsert 단계를 별도 module로 분리
- service 함수는 orchestration 중심으로 단순화
- 각 단계는 독립 테스트 가능해야 함

3. Observability 개선
- 구조화 로그 필드 통일 (`pipeline_id`, `company_id`, `machine_id`, `file_upload_id`, `ingestion_version`)
- stage 별 latency metric 수집
-  embedding 호출 latency / batch size 기록
- 실패 원인 코드 표준화
- ingestion 단계별 token count, chunk count 기록

4. Idempotency 정책 명문화
- 동일 파일 재실행 시 "Deterministic Chunk ID 기반 Upsert" 정책을 사용  
  chunk_id = has(file_upload_id + section_id + chunk_index)
- delete 없이 upsert
- 실패 시 데이터 유실 방지
- version metadata로 전략 비교 가능

5. Ingestion Strategy Versioning
- 각 ingestion 방식은 version으로 관리한다.
- 예: v1_page_split, v2_semantic_split, v3_structure_aware

## `ingestion_service.py`

### 기능 
	•	파일 로드
	•	Layout 분석
	•	구조화
	•	chunk 생성
	•	embedding 생성
	•	Weaviate batch upsert 수행
	•	ingestion_version 기반 전략 실행
	•	재실행 시 중복 누적 방지

### TODO (Research + Performance Driven)

#### 1. File format 확장
    - 현재는 PDF 중심 (25-02-19)
    - CSV
    - XLSX
    - DOCX
    - PPTX
    - TXT/Markdown
    - 이미지 기반 문서(스캔 PDF)

##### 구현 방향  
	•	DocumentParser abstraction 도입
	•	MIME type + extension 기반 parser registry
	•	parser 출력은 공통 DocumentChunk 스키마로 정규화
	•	Streaming parser 지원 (대형 파일 대응)

#### 2. Layout-Aware Ingestion
- 전문 분야 문서의 특성상 layout 정보는 핵심 신호이다. 
  ###### 지원 대상   
      •	heading
      •	section boundary
      •	table
      •	figure + caption
      •	diagram region
      •	page region bbox
      •	일반 문서 / 그림 중심 문서 / 도면 문서 / diagram 문서 / table 문서
      •	page region bbox
      •	page region bbox
  ###### 구현 방향 
      •	layout-aware extraction (heading/section/table/caption)
      •	figure-caption 연결
      •	table 별도 object 처리
      •	metadata에 bbox, page_region, anchor 포함
      •	OCR fallback 경로 추가 
      • multimodal metadata 확장 (anchor, bbox, page region 등)
    
#### 3. Text Chunking 품질 개선
##### 3.1. Page based Chunking
    - page 기반 단순 text chunking 은 다음 리스크가 존재 
        • 의미 및 문맥 단절
        • table 파손
        • page 경계 의존 
	    • chunk 내 irrelevant context 증가
	    • precision 저하
    - 전환 방향 
	    • page는 metadata로 유지 
        • split 기준은 semantic/structure 기반
  
##### 3.2. Semantic Segmentation based Checking 
    - Sentence embedding 기반 dynamic split:
        1. 문장 단위 embedding
        2. cosine similarity 급격 감소 지점에서 split 
    - 연구 기반 
        • Text filing
        • Topic segmentation
        • "Lost in the Middle" 현상 대응 
    - TODO
        • sementic similarity threshold 실험
        • Recall@k 기반 threshold 튜닝 

##### 3.3. Adaptive Chunk Size 
    - 고정 chunk_size는 산업 문서에 부적합.
    - 전략:
	    • document_type 기반 chunk_size 변경
	    • 300 / 500 / 800 / 1200 token grid search
	    • retrieval precision vs recall tradeoff 분석

##### 3.4. Table-Aware Chunking
    - 산업 매뉴얼의 핵심 정보는 table에 존재.
    - 전략:
	    • table → structured JSON 변환
	    • 별도 embedding space 고려
	    • cell-level retrieval 실험
    - 연구 참고:
	    • TAPAS
	    • TaBERT
	    • LayoutLM 계열

#####  3.5. Boilerplate 제거
	    • footer/header 제거
	    • page number 제거
	    • 반복 문구 제거

#### 4. Embedding 전략 고도화
현재 embedding 모델 고정 사용은 위험.
##### 4-1. Embedding 모델 Benchmark
비교 대상:

    • text-embedding-3-large
	• bge-large
	• e5-large-v2

지표 

    • Recall@5
    • Recall@10
    • MRR
    • hit-rate

##### 4.2. Domain-Specific Fine-tuning 검토
산업 도메인 특화 embedding이 retrieval 10~20% 향상 가능.

    • contrastive learning 기반 fine-tune 검토
    • 산업 매뉴얼 QA pair 기반 학습

#### 5. Performance Optimization
##### 5-1. Embedding Batch 최적화
	•	batch size 실험
	•	async embedding
	•	exponential backoff
##### 5-2. Streaming Ingestion
    - 대형 PDF 대응:
	    • streaming chunk 생성
	    • backpressure 제어
##### 5-3. Memory Footprint 관리
	• 전체 파일 메모리 로드 금지
	• iterator 기반 pipeline

## `vector_delete_service.py`

### 기능 

- Weaviate에서 조건 기반 chunk 조회
- 조회된 object id 목록 삭제
- 삭제 결과 집계 반환
- dry-run 지원 가능 

### TODO

#### 삭제 정확도/안전성
- 현재 조건(`class + machine_id + file_upload_id + source`)의 정책 문서화
- 잘못된 대량 삭제 방지를 위한 dry-run 옵션 추가
- 삭제 대상 count 상한선(guard rail) 도입
- operator_id 기록
- audit log 저장 

#### 성능 개선
- 대량 object 삭제 시 batch/delete-by-filter 전략 검토
- API 호출 재시도 정책(backoff) 추가
- 대량 삭제 latency metric 기록 

### 2-3. 운영성 강화
- 삭제 요청 추적 id 추가(delete_request_id)
- 삭제 전/후 count 비교 로깅
- 실패 건 재시도 큐(선택) 검토 
## `__init__.py`

### 기능 
- 서비스 레이어 public export 정책 결정
- 외부 import 대상(안정 API)과 내부 구현(비공개) 구분

### 완료 기준 (Definition of Done)

- 최소 2개 신규 포맷 ingestion 지원
- 문서 유형(텍스트/그림/도면)별 처리 경로 존재
- 동일 파일 재실행 시 중복 누적 없음(정책 검증 포함)
- retrieval 품질 지표를 비교 가능한 baseline 리포트 존재
- 서비스 단계별 로그/오류코드/latency 추적 가능
- 최소 2개 신규 포맷 ingestion 지원
- layout-aware processing 존재
- semantic or structure 기반 chunking 지원
- ingestion_version 관리 체계 존재
- 동일 파일 재실행 시 중복 누적 없음
- embedding benchmark 리포트 존재
- hybrid retrieval 실험 결과 존재
- golden dataset 기반 retrieval baseline 리포트 존재
- 단계별 latency, error code, metric 추적 가능
- delete dry-run + guard rail 동작 검증 완료
- 