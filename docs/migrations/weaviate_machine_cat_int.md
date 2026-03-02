# Weaviate 스키마 마이그레이션 (machine_cat: string -> int)

Weaviate는 기존 property의 타입을 변경할 수 없습니다.
따라서 새 class를 생성하고 재적재하는 방식이 필요합니다.

## 시나리오

- 기존: `Machine` class에 `machine_cat: string`
- 변경: `Machine` class에 `machine_cat: int`

## 권장 절차

1. 서비스 중지
2. 새 class 생성 (예: `Machine_v2`)
3. ingestion 재실행(재적재)
4. rag/ingestion 설정에서 class를 `Machine_v2`로 전환
5. 기존 class 삭제(필요 시)

## 1) 새 class 생성

```bash
curl -X POST http://localhost:8080/v1/schema \
  -H "Content-Type: application/json" \
  -d '{
    "class": "Machine_v2",
    "vectorizer": "none",
    "properties": [
      {"name": "content", "dataType": ["text"]},
      {"name": "source", "dataType": ["string"]},
      {"name": "page_number", "dataType": ["int"]},
      {"name": "file_upload_id", "dataType": ["string"]},
      {"name": "machine_id", "dataType": ["string"]},
      {"name": "machine_cat", "dataType": ["int"]},
      {"name": "company_id", "dataType": ["int"]}
    ]
  }'
```

## 2) 재적재

- ingestion-ui에서 class를 `Machine_v2`로 선택
- 기존 파일들을 다시 `Run Ingestion`

## 3) 설정 반영

`.env`에 아래를 설정:

```bash
WEAVIATE_MACHINE_CLASS_NAME=Machine_v2
```

## 4) 기존 class 삭제 (선택)

```bash
curl -X DELETE http://localhost:8080/v1/schema/Machine
```
