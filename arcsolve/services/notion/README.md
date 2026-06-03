# Notion 서비스

Notion 워크스페이스 **읽기** 래퍼 — 검색(search)·페이지·블록 본문·데이터베이스·데이터 소스 조회/쿼리.
전부 읽기. 인증은 **필수** Bearer 토큰(Internal Integration Token 또는 PAT) + 버전 헤더.

> API 버전은 최신 **`2026-03-11`**로 고정한다. 이 버전부터 database는 **data source 컨테이너**이고
> (`archived`→`in_trash`), database 쿼리는 **data source 쿼리**로 옮겨졌다.

## 계약 출처 (공식 문서)
- API 레퍼런스 개요(base URL): https://developers.notion.com/reference/intro
- 버전 관리(Notion-Version, 최신 2026-03-11): https://developers.notion.com/reference/versioning
- 2025-09-03 업그레이드(data source 모델): https://developers.notion.com/docs/upgrade-guide-2025-09-03
- Search: https://developers.notion.com/reference/post-search
- Retrieve a page: https://developers.notion.com/reference/retrieve-a-page
- Retrieve block children: https://developers.notion.com/reference/get-block-children
- Retrieve a database: https://developers.notion.com/reference/retrieve-a-database
- Retrieve a data source: https://developers.notion.com/reference/retrieve-a-data-source
- Query a data source: https://developers.notion.com/reference/query-a-data-source
- Rich text(모든 항목에 plain_text): https://developers.notion.com/reference/rich-text
- 에러 봉투/상태코드: https://developers.notion.com/reference/status-codes

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로 빌더·헤더/본문 빌더·응답 모델·순수 헬퍼).

## 엔드포인트 (`<base><path>`)
| 종류 | METHOD · PATH |
|------|------|
| 검색 | `POST /search` (filter: page \| data_source) |
| 페이지 조회 | `GET /pages/{page_id}` |
| 블록 자식(본문) | `GET /blocks/{block_id}/children` |
| 데이터베이스 조회 | `GET /databases/{database_id}` (→ data_sources 목록) |
| 데이터 소스 조회 | `GET /data_sources/{data_source_id}` (→ properties 스키마) |
| 데이터 소스 쿼리 | `POST /data_sources/{data_source_id}/query` (→ 행) |

Base: `https://api.notion.com/v1` · 인증: `Authorization: Bearer <NOTION_TOKEN>` + `Notion-Version: 2026-03-11` · 스코프: 읽기

> 페이지네이션은 응답 본문 `next_cursor`/`has_more`(헤더 아님), `page_size` 1–100(기본 25). search/query는 본문 cursor, blocks children은 쿼리 파라미터.

## 셋업
1. [내 통합(integrations)](https://www.notion.so/my-integrations)에서 Internal Integration Token 또는 PAT 발급.
2. **읽을 페이지/데이터베이스를 통합과 공유**(연결 추가)해야 한다 — 공유 안 하면 404(`object_not_found`).
3. `.env`: `NOTION_TOKEN=<토큰>`

> 사전발급 토큰 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth notion` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `notion_search(query?, filter_type?, page_size?, start_cursor?)` | page/data source를 제목으로 검색. `filter_type`=page\|data_source |
| `notion_get_page(page_id)` | 페이지 메타(제목·URL·수정시각·휴지통) |
| `notion_get_block_children(block_id, page_size?, start_cursor?)` | 블록/페이지 본문 블록 나열(평문 추출). page 본문은 block_id에 page_id |
| `notion_get_database(database_id)` | 데이터베이스 → 자식 data source 목록(id·name) |
| `notion_get_data_source(data_source_id)` | data source 프로퍼티 스키마(name:type) |
| `notion_query_data_source(data_source_id, filter?, sorts?, page_size?, start_cursor?)` | data source 행 쿼리. `filter`/`sorts`는 Notion DSL 그대로 |

**DB 읽기 흐름**: `notion_get_database`(→data_sources) → `notion_get_data_source`(→스키마) → `notion_query_data_source`(→행).

## 범위 / 제약
- **읽기만**(MVP). 페이지/블록/DB/data source 검색·조회·쿼리.
- 제외: 일체의 write(page/block 생성·수정), rich_text 복합 서식(멘션·수식·중첩 토글)은 **평문만 추출**, 코멘트, 유저 목록.
- `page_size` 1–100(기본 25). 통합과 공유된 콘텐츠만 접근 가능.

## UNVERIFIED / provenance 노트
- Retrieve-database 응답의 `data_sources[]` 항목 필드(`id`/`name`)는 [2025-09-03 업그레이드 가이드](https://developers.notion.com/docs/upgrade-guide-2025-09-03) 기준 — 레퍼런스 산문 명시가 약해 `list[dict]`로 느슨히 받는다(`contract.py`의 `TODO(provenance)` 참고).
- `filter`/`sorts`(query)는 Notion 필터/정렬 DSL이 방대해 MVP는 모델링하지 않고 **dict/list pass-through**한다(kakao가 text 템플릿만 모델링한 것과 동일한 스코프 결정).

## 확장 포인트
- 쓰기(`POST /pages`·`PATCH /blocks/{id}/children`·`PATCH /pages/{id}`)는 평문→`paragraph`/`title` 변환을 더해 동일 패턴으로 추가.
- 코멘트(`/comments`), 유저(`/users`), 필터 DSL 모델링, cursor 자동 페이지네이션.
