# Crossref 서비스

Crossref REST API 학술 메타데이터 **읽기** 래퍼 — 출판물(works)·저널(journals) 검색·단건 조회.
전부 GET·JSON. **무인증**(키 없음). polite pool용 연락 이메일은 **쿼리 파라미터**(`mailto`)다.

## 계약 출처 (공식 문서)
- REST API README(엔드포인트·쿼리 파라미터·rows/offset 제약·sort/order·etiquette): https://github.com/CrossRef/rest-api-doc/blob/master/README.md
- 응답 포맷(Work 오브젝트 필드): https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md
- 공식 안내(retrieve metadata · REST API): https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- 라이브 응답 확인: https://api.crossref.org/works · `/works/{doi}` · `/journals` · `/journals/{issn}`

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로 빌더·쿼리 제약·응답 모델).

## 인증 (없음 · polite pool만 선택)
Crossref는 **무인증**이다. `CrossrefSettings`(`CROSSREF_*`)가 선택 이메일을 로드한다.

| env | 쓰임 | 비고 |
|---|---|---|
| `CROSSREF_MAILTO` | 쿼리 `mailto=<이메일>` + User-Agent `(mailto:...)` | 선택. polite pool(안정적인 레이트리밋). 공식 etiquette 권장 |

- 이메일이 없어도 호출은 성공한다(public pool).
- base `https://api.crossref.org`. 페이지네이션/건수는 **응답 본문 `message`**(`total-results`·`items-per-page`·`items`)이므로 코어 `get_json`만 쓴다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 종류 | METHOD · PATH |
|------|------|
| works 검색/나열 | `GET /works?query=&filter=&sort=&order=&rows=&offset=` |
| work 단건 | `GET /works/{doi}` |
| journals 검색/나열 | `GET /journals?query=&rows=&offset=` |
| journal 단건 | `GET /journals/{issn}` |

Base: `https://api.crossref.org` · 인증: 없음(선택 `mailto`) · 스코프: 읽기 전용

> `rows`는 0–1000(기본 20). `offset`은 0–10000(그 이상은 cursor 딥페이지네이션 — 범위 밖). `order`는 `asc`/`desc`. `filter`는 `name:value`(콤마=AND, 예: `type:journal-article,from-pub-date:2020-01-01`). `sort`는 `is-referenced-by-count`·`published`·`relevance`·`score` 등.
> 응답 봉투: `{status, message-type, message-version, message:{...}}` — 리스트면 `message`에 `total-results`/`items`, 단건이면 `message`가 곧 엔티티. 에러(validation-failure)는 `message`가 **배열**(`[{message,...}]`)이다.

## 셋업
1. 키 발급 단계 없음(무인증).
2. `.env`(선택): `CROSSREF_MAILTO=you@example.com` — polite pool 식별용 연락 이메일.

> 무인증·선택 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth crossref` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `crossref_search_works(query?, filter?, sort?, order?, rows?, offset?)` | 출판물 검색/나열. `filter`=`name:value`(콤마=AND), `sort`=`is-referenced-by-count` 등, `order`=`asc`/`desc`. rows 기본 20·0..1000 |
| `crossref_get_work(doi)` | 단일 출판물 조회(DOI). DOI/연도/제목/타입/인용/저자/수록지/발행처 |
| `crossref_search_journals(query?, rows?, offset?)` | 저널 검색/나열. 제목·발행처·ISSN |
| `crossref_get_journal(issn)` | 단일 저널 조회(ISSN). 제목·발행처·ISSN·등록 DOI 수 |

## 범위 / 제약 (공식)
- **읽기만.** works/journals 검색·단건 조회만(MVP).
- 제외: members·funders·types·licenses 엔티티, cursor 딥페이지네이션, content negotiation(citation 포맷: BibTeX/RIS 등), `/journals/{issn}/works` 조합 경로, `sample`/`select`/`facet`.
- `rows` 0–1000(기본 20). `offset` 페이지네이션은 최대 **10,000**(이후 cursor 필요 — 범위 밖). 레이트리밋은 `X-Rate-Limit-Limit`/`X-Rate-Limit-Interval` 헤더로 동적 안내(polite pool 권장).

## UNVERIFIED / provenance 노트
- Work의 `author`·`published`는 중첩 스키마(`{given,family,ORCID,sequence}`·`{date-parts:[[Y,M,D]]}`)가 풍부해 `list[dict]`/`dict`로 느슨히 받는다(출력에서 저자명/연도만 사용). `contract.py`의 출처 주석 참고.
- 성공 봉투의 `message`는 object지만 **에러 봉투의 `message`는 array**다(`ErrorResponse`로 별도 모델링). 404(없는 DOI/ISSN)는 본문이 `text/plain` `Resource not found.`라 JSON 파싱하지 않고 깔끔한 메시지만 노출한다.

## 확장 포인트
- `cursor=*`(딥페이지네이션), `sample=`(랜덤 표본), `select=`(필드 선택), `facet=`(집계), `/journals/{issn}/works`(저널 내 works), 다른 엔티티(`/members`·`/funders`·`/types`)는 동일 패턴으로 경로 상수·도구 추가. citation 포맷은 content negotiation(`Accept` 헤더)이 필요 — 별도 코어 동사.
