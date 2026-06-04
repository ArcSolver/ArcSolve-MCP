# OpenAlex 서비스

OpenAlex 학술 그래프 **읽기** 래퍼 — 논문(works)·저자(authors) 검색·단건 조회. 전부 GET·JSON.
**인증은 선택**(키 없이도 무료 일일 크레딧으로 동작), 키·polite 이메일은 **쿼리 파라미터**다.

## 계약 출처 (공식 문서)
- API 개요(base URL): https://developers.openalex.org/how-to-use-the-api/api-overview
- 리스트/검색(search·filter·sort·per-page·page·cursor·meta 봉투): https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
- Work 오브젝트(필드): https://developers.openalex.org/api-entities/works/work-object
- Author 오브젝트(필드): https://developers.openalex.org/api-entities/authors/author-object
- 인증/요금(api_key·mailto·레이트리밋): https://developers.openalex.org/guides/authentication

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로 빌더·쿼리 제약·응답 모델).

## 인증 (선택)
`OpenAlexSettings`(`OPENALEX_*`)가 자격증명을 로드한다. **헤더가 아니라 쿼리 파라미터**다.

| env | 쿼리 파라미터 | 비고 |
|---|---|---|
| `OPENALEX_API_KEY` | `api_key=<키>` | 선택(권장). 없으면 무료 일일 크레딧으로 동작 |
| `OPENALEX_MAILTO` | `mailto=<이메일>` | 선택. polite pool(안정적인 레이트리밋) |

- 키/이메일 둘 다 없어도 호출은 성공한다.
- base `https://api.openalex.org`. 페이지네이션/건수는 **응답 본문 meta**(헤더 아님)이므로 코어 `get_json`만 쓴다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 도구 | METHOD · PATH |
|------|------|
| works 검색/나열 | `GET /works?search=&filter=&sort=&per-page=&page=` |
| work 단건 | `GET /works/{id}` (OpenAlex ID `W…` 또는 DOI) |
| authors 검색/나열 | `GET /authors?search=&per-page=&page=` |
| author 단건 | `GET /authors/{id}` (OpenAlex ID `A…` 또는 ORCID URL) |

> **쿼리 파라미터명은 `per-page`(하이픈)**, 응답 본문 필드는 `per_page`(언더스코어). `per-page`는 1–200. filter는 `attr:value`(콤마=AND, `|`=OR, `!`=NOT). 정렬은 `sort`(예: `cited_by_count:desc`).
> 리스트 응답 봉투: `{meta:{count,page,per_page,next_cursor?,cost_usd}, results:[...], group_by:[]}` — "총 N건 · page P"는 본문 `meta`에서 만든다.

## 셋업
1. (선택) [OpenAlex 인증 가이드](https://developers.openalex.org/guides/authentication)에서 API 키 발급.
2. `.env`(둘 다 선택):
   - `OPENALEX_API_KEY=<키>`
   - `OPENALEX_MAILTO=<이메일>`

> 키는 선택 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth openalex` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `openalex_search_works(query?, filter?, sort?, per_page?, page?)` | 논문 검색/나열. `filter`=`attr:value`(콤마=AND/`\|`=OR/`!`=NOT), `sort`=`cited_by_count:desc` 등. per_page 기본 25·1..200 |
| `openalex_get_work(work_id)` | 단일 논문 조회(OpenAlex ID `W…` 또는 DOI). id/year/type/인용/제목/저자 |
| `openalex_search_authors(query?, per_page?, page?)` | 저자 검색/나열. 논문 수·인용 수 |
| `openalex_get_author(author_id)` | 단일 저자 조회(OpenAlex ID `A…` 또는 ORCID). 논문 수·인용 수·ORCID |

## 범위 / 제약 (공식)
- **읽기만.** works/authors 검색·단건 조회만(MVP).
- 제외: sources·institutions·topics·publishers·funders, `group_by` 집계, cursor 딥페이지네이션, ngrams/autocomplete.
- `per-page` 1–200(기본 25). page 기반 페이지네이션은 최대 **10,000건**(이후 cursor 필요 — 범위 밖). 레이트리밋 100 req/s.

## UNVERIFIED / provenance 노트
- `meta.cost_usd`는 라이브 응답에서 관측했으나 공식 산문의 표준화 명시는 약하다 → `float|None`로 느슨히(`extra="ignore"`).
- Work의 `authorships`·`primary_location`·`open_access`는 중첩 스키마가 풍부해 `list[dict]`/`dict`로 느슨히 받는다(필요한 `author.display_name`/`author.id`만 출력에서 사용). `contract.py`의 출처 주석 참고.

## 확장 포인트
- `select=`(필드 선택), cursor 페이지네이션(`cursor=*`), `group_by=`(집계), 다른 엔티티(`/sources`·`/institutions`·`/topics` 등)는 동일 패턴으로 경로 상수·도구 추가.
