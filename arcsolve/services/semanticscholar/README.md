# Semantic Scholar 서비스

Semantic Scholar Academic Graph API **읽기** 래퍼 — 논문(papers)·저자(authors) 검색·단건 조회.
전부 GET·JSON. **인증은 선택**(키 없이 공유 풀로 동작), 키는 **`x-api-key` 헤더**다. 반환 필드는
**`fields` 파라미터**(콤마 구분)로 선택한다.

## 계약 출처 (공식 문서)
- OpenAPI(Swagger) 스펙(엔드포인트·쿼리 파라미터·limit/offset 제약·fields·응답 스키마): https://api.semanticscholar.org/api-docs/graph
  - 원본 JSON: https://api.semanticscholar.org/graph/v1/swagger.json
- 공식 튜토리얼(base URL·fields·rate limit·x-api-key): https://www.semanticscholar.org/product/api/tutorial
- 라이브 응답 확인: `GET /paper/search` · `/paper/{id}` · `/author/search` · `/author/{id}`

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로 빌더·쿼리 제약·응답 모델).

## 인증 (선택 · x-api-key 헤더)
`SemanticScholarSettings`(`SEMANTICSCHOLAR_*`)가 (선택) API 키를 로드한다. **쿼리 파라미터가 아니라 헤더**다.

| env | 쓰임 | 비고 |
|---|---|---|
| `SEMANTICSCHOLAR_API_KEY` | `x-api-key: <키>` 헤더 | 선택. 있으면 전용 풀(1 RPS). 없으면 공유 풀(무인증) |

- 키가 없어도 호출은 성공한다(공유 풀). 다만 공유 풀이 혼잡하면 429가 잦을 수 있다.
- base `https://api.semanticscholar.org/graph/v1`. 페이지네이션/건수는 **응답 본문**(`total`·`offset`·`next`)이므로 코어 `get_json`만 쓴다.

## 레이트리밋 (공식)
- **키 없음**: 모든 비인증 사용자가 **공유 풀**을 함께 쓴다 — 트래픽에 따라 느려지고 429가 잦다.
- **키 있음**: 전 엔드포인트 합산 **1 request/second**(검토 후 상향 가능). 키는 [API 키 폼](https://www.semanticscholar.org/product/api#api-key-form)에서 신청한다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 도구 | METHOD · PATH |
|------|------|
| papers 검색 | `GET /paper/search?query=&fields=&limit=&offset=&year=` |
| paper 단건 | `GET /paper/{id}` (S2 paperId 또는 `DOI:`·`ARXIV:`·`CorpusId:` 등) |
| authors 검색 | `GET /author/search?query=&fields=&limit=&offset=` |
| author 단건 | `GET /author/{id}` (S2 authorId) |

> **`fields`**(콤마 구분)로 반환 필드를 선택한다(중첩은 `.`, 예: `authors.name`). 미지정 시 상류 기본 최소 필드(`paperId,title` / `authorId,name`)만 온다.
> `limit`: paper search 기본 10·**최대 100**, author search 기본 10·**최대 1000**. `paper/search`는 **relevance** 검색이라 `offset+limit < 1000` 제약이 추가된다(이상은 bulk/Datasets API — 범위 밖).
> 검색 응답 봉투: `{total, offset, next?, data:[...]}` — `next`는 다음 offset(더 없으면 생략). 단건은 entity 오브젝트가 곧 최상위.

## 셋업
1. (선택) [API 키 폼](https://www.semanticscholar.org/product/api#api-key-form)에서 키 신청.
2. `.env`(선택): `SEMANTICSCHOLAR_API_KEY=<키>` — 전용 풀(1 RPS).

> 키는 선택 헤더 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth semanticscholar` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `s2_search_papers(query, fields?, limit?, offset?, year?)` | 논문 relevance 검색. `fields`로 반환 필드 선택. limit 기본 10·1..100, offset+limit<1000 |
| `s2_get_paper(id, fields?)` | 단일 논문 조회. id=paperId 또는 `DOI:`·`ARXIV:`·`CorpusId:` 등 |
| `s2_search_authors(query, fields?, limit?, offset?)` | 저자 검색. limit 기본 10·1..1000 |
| `s2_get_author(id, fields?)` | 단일 저자 조회. id=S2 authorId |

## 범위 / 제약 (공식)
- **읽기만.** papers/authors 검색·단건 조회만(MVP).
- 제외: bulk search(`/paper/search/bulk` cursor), citations/references 그래프 확장, recommendations·datasets API.
- `paper/search` relevance는 최대 1000건(offset+limit<1000, 이후 bulk 필요 — 범위 밖). 응답 최대 10MB.

## UNVERIFIED / provenance 노트
- `fields`로 어떤 필드든 빠질 수 있어 응답 모델은 paperId/authorId 외 전부 Optional(`extra="ignore"`). `externalIds`·`authors`는 중첩이 풍부해 `dict`/`list[dict]`로 느슨히 받는다(출력에서 DOI·첫 저자명만 사용).
- 에러 봉투는 JSON 두 형태: 검증 실패/404는 `{"error": "..."}`, 레이트리밋(공유 풀)은 `{"message": "...", "code": "429"}`. 둘 다 `ErrorResponse`로 느슨히 받고 텍스트만 노출한다.
- swagger는 `/paper/search`의 `total`을 string으로 명시하나 라이브 응답은 integer였다 → `int|None`로 모델링(`extra="ignore"`).

## 확장 포인트
- `/paper/search/bulk`(cursor 1000+건), `/paper/{id}/citations`·`/references`(인용 그래프), `/paper/batch`·`/author/batch`(POST 배치), recommendations·datasets API는 동일 패턴으로 경로 상수·도구 추가. 배치는 POST(`post_json`)가 필요 — 코어에 이미 있음.
