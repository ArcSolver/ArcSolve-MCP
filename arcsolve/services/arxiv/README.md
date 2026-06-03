# arXiv 서비스

arXiv API 학술 프리프린트 **읽기** 래퍼 — 검색(`search_query`)·id 조회(`id_list`).
전부 GET·**무인증**(키 없음). arXiv는 JSON이 아니라 **Atom 1.0 XML**을 반환하므로 코어
`get_text`(raw str)로 받고 **표준 라이브러리 `xml.etree.ElementTree`**로 파싱한다(외부 의존 없음).

## 계약 출처 (공식 문서)
- API User Manual(쿼리 인터페이스·파라미터·제약·Atom 응답 구조·error feed·etiquette): https://info.arxiv.org/help/api/user-manual.html
- API 개요(공개 API 안내): https://info.arxiv.org/help/api/index.html

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 상수·쿼리 제약·XML→pydantic 파싱·error-entry 감지).

## 인증 (없음)
arXiv API는 **무인증**이다. 키·토큰·env 설정이 필요 없다(식별용 User-Agent만 보낸다).

> ⚠️ **etiquette**: 공식 문서는 연속 호출 시 **요청 간 3초 지연**을 권장한다("we encourage you to play nice and incorporate a 3 second delay in your code"). 큰 결과셋(1000건 초과)은 쿼리를 좁히거나 슬라이스로 나눠 받기를 권한다. *코드 차원의 지연/재시도는 이 MVP의 비목표다 — 호출자가 빈도를 조절한다.*

## 엔드포인트 (전부 GET · `https://export.arxiv.org/api/query`)
| 종류 | METHOD · PATH |
|------|------|
| 검색 | `GET /api/query?search_query=&start=&max_results=&sortBy=&sortOrder=` |
| id 조회 | `GET /api/query?id_list=` |

Base: `https://export.arxiv.org/api/query` · 인증: 없음 · 스코프: 읽기 전용(메타데이터만)

> `search_query`는 필드 prefix(`ti`/`au`/`abs`/`cat`/`all` 등) + 불리언 `AND`/`OR`/`ANDNOT`를 **문자열 그대로** 받는다(빌더는 스코프 밖). `id_list`는 콤마 구분(버전 접미사 `v1` 등 선택). `start`는 0-based, `max_results` 기본 10·**1회 ≤2000 권장·총 ≤30000**(초과 시 HTTP 400). `sortBy`=`relevance`/`lastUpdatedDate`/`submittedDate`, `sortOrder`=`ascending`/`descending`.

### 응답 (Atom 1.0 XML)
- 네임스페이스: atom `http://www.w3.org/2005/Atom` · opensearch `http://a9.com/-/spec/opensearch/1.1/` · arxiv `http://arxiv.org/schemas/atom`.
- 피드 메타(OpenSearch): `opensearch:totalResults`·`startIndex`·`itemsPerPage`(본문 → 헤더 동사 불필요).
- entry 필드: `id`(abs URL)·`title`·`summary`(초록)·`author/name`(+`arxiv:affiliation`)·`published`·`updated`·`category`(term/scheme)·`arxiv:primary_category`·`link`(abstract `rel=alternate`/pdf `title=pdf`/doi `title=doi` 최대 3)·`arxiv:comment`·`arxiv:journal_ref`·`arxiv:doi`.
- ⚠️ **에러는 HTTP 200**: malformed id 등 잘못된 입력은 4xx가 아니라 **HTTP 200 + 단일 `<entry>` title="Error"** 피드로 온다(`<id>`는 `http://arxiv.org/api/errors#...`, `<summary>`가 메시지). 파서가 `is_error_feed`로 감지해 `ArxivErrorEntry`로 매핑한다. `max_results>30000`만 HTTP 400.

## 셋업
1. 키 발급 단계 없음(무인증). `.env` 변경 불필요.

> 무인증이므로 `arcsolve-mcp auth arxiv` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `arxiv_search(query, start?, max_results?, sort_by?, sort_order?)` | 프리프린트 검색. `query`=`search_query` 문자열(prefix `ti`/`au`/`abs`/`cat`/`all` + `AND`/`OR`/`ANDNOT`). max_results 기본 10·0..30000 |
| `arxiv_get(id_list)` | arXiv id로 조회(콤마 구분). 단건이면 상세(저자·초록·분류·날짜·PDF·코멘트·저널·DOI), 다건이면 한 줄 요약 목록 |

## 범위 / 제약 (공식)
- **읽기만 · 메타데이터만.** API는 full-text를 제공하지 않는다(검색·메타 조회만).
- 제외: boolean 빌더(쿼리 문자열은 그대로 전달), full-text 본문, figures, content negotiation.
- `max_results` 기본 10·**1회 ≤2000 권장·총 ≤30000**(초과 HTTP 400). `start` 0-based. etiquette 3초 지연 권장(코드 지연/재시도는 비목표).

## UNVERIFIED / provenance 노트
- arXiv는 잘못된 입력에 **HTTP 200 + error-entry**(title='Error')를 준다. `is_error_feed`는 (entry 1개) ∧ (title='Error') ∧ (id가 `/api/errors` 포함)를 함께 확인해, 제목이 우연히 'Error'인 정상 논문을 오탐하지 않는다.
- `title`·`summary`는 arXiv가 줄바꿈해 넣으므로 파서가 연속 공백을 한 칸으로 정규화한다(`_normalize_ws`).
- `author`/`link`/`category`는 중첩·반복 요소라 각각 모델 리스트로 받는다(출력에선 저자명/연도/PDF 등만 사용).

## 확장 포인트
- boolean 쿼리 빌더, 카테고리 자동완성, RSS/OAI-PMH(증분 수집), full-text(S3 벌크 — API 밖)는 동일 패턴으로 확장. 페이지네이션은 `start`/`max_results`로 충분(딥 페이징은 2000 단위 슬라이스).
