# Wikipedia 서비스

위키백과(Wikipedia) **읽기** 래퍼 — 검색·요약·본문·링크. 전부 GET·읽기. **무인증**으로 전체
읽기가 동작하지만, Wikimedia는 식별용 **`User-Agent` 헤더를 요구**한다(없거나 약하면 403/스로틀).
(선택) Bearer 토큰을 주면 레이트리밋이 완화된다.

## 계약 출처 (공식 문서)
- per-wiki REST(검색) 레퍼런스: https://www.mediawiki.org/wiki/API:REST_API/Reference
- Wikimedia REST API(rest_v1 summary): https://www.mediawiki.org/wiki/Wikimedia_REST_API (per-wiki 명세: https://en.wikipedia.org/api/rest_v1/)
- TextExtracts(`prop=extracts`·`exintro`·`explaintext`·`exchars`): https://www.mediawiki.org/wiki/Extension:TextExtracts
- Action API Query(`prop=links|categories`·`formatversion=2`·`redirects`): https://www.mediawiki.org/wiki/API:Query
- 라이브 응답 확인: `/w/rest.php/v1/search/page` · `/api/rest_v1/page/summary/{title}` · `/w/api.php?action=query&prop=extracts` · `/w/api.php?action=query&prop=links|categories`

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(호스트/경로 빌더·언어·limit 검증·제목 인코더·HTML 스트립·부분 응답 모델).

## 인증 (없음 · User-Agent 필수 · 토큰 선택)
무인증으로 전체 읽기가 동작한다. 다만 Wikimedia는 식별용 **`User-Agent` 헤더를 요구**하므로 기본
식별 문자열(`contract.DEFAULT_USER_AGENT`)을 항상 보내며, 연락처를 넣고 싶으면
`WIKIPEDIA_USER_AGENT`로 덮어쓴다. (선택) `WIKIPEDIA_API_TOKEN`을 주면 `Authorization: Bearer`를
UA와 함께 보내 레이트리밋이 완화된다(토큰 없이도 읽기는 전부 동작).

| env | 쓰임 | 비고 |
|---|---|---|
| `WIKIPEDIA_USER_AGENT` | `User-Agent: <값>` | 선택. 미설정 시 기본 식별 문자열. 공식 권장은 연락처 포함(예: `(myapp.com, you@example.com)`) |
| `WIKIPEDIA_API_TOKEN` | `Authorization: Bearer <값>` | 선택. 있으면 레이트리밋 완화. 없어도 전체 읽기 동작 |

- 헤더는 코어 `get_json(headers=...)`로 주입한다(서비스 폴더에서 httpx 직접 생성 금지 — AGENTS 규칙).
- 언어판마다 호스트가 다르다: base `https://{lang}.wikipedia.org`.

## 엔드포인트 (전부 GET · `https://{lang}.wikipedia.org<path>`)
| 종류 | METHOD · PATH |
|------|------|
| 검색(클린 REST) | `GET /w/rest.php/v1/search/page?q=&limit=` |
| 요약(rest_v1) | `GET /api/rest_v1/page/summary/{title}` |
| 본문(TextExtracts) | `GET /w/api.php?action=query&prop=extracts&explaintext=1&formatversion=2` |
| 링크·분류 | `GET /w/api.php?action=query&prop=links\|categories&formatversion=2` |

Base: `https://{lang}.wikipedia.org` · 인증: 없음(User-Agent 필수, Bearer 선택) · 스코프: 읽기 전용

> 세 종류 엔드포인트를 섞어 쓴다: ① per-wiki REST 검색, ② rest_v1 요약, ③ Action API 본문/링크.
> ⚠️ `api.wikimedia.org/core/v1/*`(통합 REST)는 2026-07 deprecation 예정·후속 없음 → 사용하지 않는다.
> ⚠️ Action API는 잘못된 파라미터에 **HTTP 200 + `{"error":{"code","info"}}`**를 줄 수 있다(4xx가 아님) → 본문을 보고 매핑한다.
> Action API는 `formatversion=2`로 `query.pages`를 **깨끗한 배열**로 받는다(pageid-keyed 객체 아님). `redirects=1`로 리다이렉트를 추적한다.

## 셋업
1. 키 발급 단계 없음(무인증).
2. `.env`(선택): `WIKIPEDIA_USER_AGENT="(myapp.com, you@example.com)"` — 식별/연락용 User-Agent.
3. `.env`(선택): `WIKIPEDIA_API_TOKEN=...` — Bearer 토큰(레이트리밋 완화).

> 무인증·필수 User-Agent 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth wikipedia` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `wikipedia_search(query, lang="en", limit=10)` | 클린 REST 검색. 제목·요약·스니펫(HTML 태그 제거). `limit` 1–100 |
| `wikipedia_summary(title, lang="en")` | rest_v1 lead 요약. extract·문서 URL·**Wikidata Q-id**(있으면)·좌표(지리)·동음이의 안내 |
| `wikipedia_extract(title, lang="en", intro_only=True, max_chars=None)` | TextExtracts 평문 본문. 도입부/전체 선택, `max_chars` 1–1200 |
| `wikipedia_links(title, lang="en", limit=50)` | 나가는 문서 링크(ns 0) + 분류. `limit` 1–500 |

## 범위 / 제약 (공식)
- **읽기만.** 검색·요약·본문·링크/분류(MVP).
- `lang`은 소문자 언어 코드(`[a-z]`+하이픈 변형, 예: `en`·`ko`·`de`·`zh`·`simple`·`zh-yue`) — 형식 위반은 HTTP 전에 차단(호스트 오염 방지).
- 검색 `limit` **1–100**(기본 10), 링크/분류 `limit` **1–500**(기본 50), `max_chars`(exchars) **1–1200**.
- 요약 404 → "문서를 찾을 수 없습니다". 본문/링크는 `missing:true` 또는 빈 `pages` → 동일 안내.
- 무 User-Agent → 403, 스로틀 → 429(Retry-After 권장). Action API 잘못된 파라미터 → HTTP 200 + `{error}` → `error.info` 노출.
- 제외: 편집/쓰기, 미디어 업로드, 위키데이터 직접 조회(요약의 `wikibase_item`만 브리지로 노출), `api.wikimedia.org/core/v1/*`(deprecating), CirrusSearch 고급 구문, parse/렌더 HTML, 카테고리 멤버 역방향(`list=categorymembers`).

## UNVERIFIED / provenance 노트
- 모든 엔드포인트·응답 필드는 라이브(en.wikipedia.org)에서 확인했다: REST 검색(`pages[]`, total 없음), rest_v1 요약(`type`·`extract`·`content_urls.desktop.page`·`thumbnail.source`·`wikibase_item`·`coordinates`), TextExtracts(`formatversion=2` → `query.pages[]` 배열·`missing:true`), links/categories(`links[]`·`categories[]`·`redirects[]`).
- Action API의 **HTTP 200 + `{error}`** 봉투는 라이브에서 확인(`action=nonsense` → `badvalue`, `exchars=abc` → `badinteger`). REST 검색 응답에는 **total 필드가 없다**(라이브 확인).
- `WIKIPEDIA_API_TOKEN`(Bearer) 자체는 라이브에서 토큰 없이 검증할 수 없어 **헤더 조립만 단위 테스트로 확인**했다(토큰 유효성·완화 효과는 미검증).

## 확장 포인트
- 미디어(`/api/rest_v1/page/media-list/{title}`), 관련 문서(`/api/rest_v1/page/related/{title}`), 역링크(`list=backlinks`), 카테고리 멤버(`list=categorymembers`), 좌표 기반 근접 검색(`list=geosearch`)은 동일 패턴으로 경로 상수·도구 추가. 위키데이터 엔티티 상세는 별도 서비스(요약의 `wikibase_item`이 브리지).
