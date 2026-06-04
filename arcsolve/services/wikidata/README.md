# Wikidata 서비스

Wikidata **읽기** 래퍼 — 엔티티 검색·단건 조회·statements·SPARQL. 전부 GET·읽기.
**무인증**(키 없음)이지만 Wikimedia는 **식별 가능한 `User-Agent`가 필수**다(없으면 403/스로틀,
WDQS가 특히 엄격). (선택) `WIKIDATA_API_TOKEN`이 있으면 Bearer로 보내 레이트리밋을 완화한다.

## 계약 출처 (공식 문서)
- Action API(`wbsearchentities` — base·파라미터·limit/type·응답 search[]): https://www.mediawiki.org/wiki/Wikibase/API
- Wikibase REST API v1(엔티티 단건·statements·labels/descriptions/aliases/sitelinks·value.content): https://www.wikidata.org/wiki/Wikidata:REST_API
- WDQS(SPARQL JSON 출력·60s 캡·동시 5쿼리·User-Agent 정책): https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual
- SPARQL JSON 결과 포맷(head.vars·results.bindings): https://www.w3.org/TR/sparql11-results-json/

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 상수·id/타입/limit 검증·응답 모델).

## 인증 (없음 · User-Agent 필수 · 토큰 선택)
`WikidataSettings`(`WIKIDATA_*`)가 (선택) User-Agent / API 토큰을 로드한다. **무인증**이지만
식별 가능한 User-Agent를 항상 보내며, 토큰이 있으면 Bearer로 레이트리밋을 완화한다.

| env | 쓰임 | 비고 |
|---|---|---|
| `WIKIDATA_USER_AGENT` | `User-Agent: <값>` | 선택. 미설정 시 기본 식별 문자열(`contract.DEFAULT_USER_AGENT`). 공식 권장은 연락처 포함 |
| `WIKIDATA_API_TOKEN` | `Authorization: Bearer <값>` | 선택. 있으면 레이트리밋 완화. 읽기는 토큰 없이도 동작 |

- 헤더는 코어 `get_json(headers=...)`로 주입한다(서비스 폴더에서 httpx 직접 생성 금지 — AGENTS 규칙).
- WDQS는 **식별 가능한 User-Agent를 엄격히 요구**한다(없으면 403/스로틀).

## 엔드포인트 (전부 GET)
| 종류 | METHOD · URL |
|------|------|
| 엔티티 검색 | `GET /w/api.php?action=wbsearchentities&search=&language=&type=&limit=&format=json` |
| 엔티티 단건 | `GET /w/rest.php/wikibase/v1/entities/items/{Qid}` (또는 `/entities/properties/{Pid}`) |
| statements | `GET /w/rest.php/wikibase/v1/entities/items/{Qid}/statements[?property={Pid}]` |
| SPARQL | `GET https://query.wikidata.org/sparql?query=&format=json` |

- Action API base: `https://www.wikidata.org/w/api.php` · REST base: `https://www.wikidata.org/w/rest.php/wikibase/v1` · WDQS: `https://query.wikidata.org/sparql`
- 인증: 없음(User-Agent 필수, 토큰 선택) · 스코프: 읽기 전용

> **세 종류 상류 혼용**: 검색은 Action API(`wbsearchentities`), 엔티티·statements는 Wikibase REST v1(2024-11 정식, 레거시 `wbgetentities`보다 안정적), SPARQL은 WDQS.
> **Action API는 HTTP 200으로 `{"error":{"code","info"}}` 봉투를 줄 수 있다** → 도구에서 본문 `error`를 우선 확인한다.
> **WDQS는 쿼리당 최대 60초** 허용 → 코어 기본 10초 대신 `timeout=60`을 넘긴다. 동시 5쿼리 제한.

## 셋업
1. 키 발급 단계 없음(무인증).
2. `.env`(선택): `WIKIDATA_USER_AGENT="(myapp.com, you@example.com)"` — 식별/연락용. `WIKIDATA_API_TOKEN=<토큰>` — 레이트리밋 완화.

> 무인증·필수 User-Agent 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth wikidata` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `wikidata_search(query, language="en", type="item", limit=7)` | 엔티티 검색(`wbsearchentities`). id·label·description. type∈{item,property,lexeme,form,sense}, limit 1..50 |
| `wikidata_entity(id, language="en")` | 엔티티 단건(REST v1). 라벨·설명·별칭·statement 수·영어 위키백과 sitelink. id=`Q42`/`P31` |
| `wikidata_statements(id, property=None)` | item statements(REST v1). 속성→값. property로 필터(`P31`). 값은 raw id/문자열 |
| `wikidata_sparql(query, limit=None)` | WDQS SPARQL(JSON). 변수 헤더 + 행. `limit`은 표시 행 수만 제한 |

## 범위 / 제약 (공식)
- **읽기만.** 검색·엔티티 단건·statements·SPARQL만(MVP).
- `wbsearchentities`: `type`∈{item,property,lexeme,form,sense}, `limit` 1..50(기본 7) — 위반은 상류 전에 차단.
- 엔티티 id는 item `Q\d+` / property `P\d+` — 그 외 형식은 HTTP 전에 차단. statements는 item(Q…)만.
- **P/Q 라벨은 raw id 그대로** 둔다(statements 출력은 추가 호출 없이 1콜 — 라벨 해석 안 함).
- WDQS: 쿼리당 최대 60초·동시 5쿼리. 출력 행은 최대 50행까지(초과 시 "(N행 중 50행 표시)").
- 제외: 엔티티 편집(쓰기), `wbgetentities`(레거시), lexeme/form/sense 단건 REST, sitelinks 전체 나열, qualifiers/references 상세, SPARQL CONSTRUCT/그래프 출력.

## UNVERIFIED / provenance 노트
- REST v1 statement `value.content`는 data_type별로 형태가 다르다: string→`str`, wikibase-item→`"Qxx"`, time→`{time,precision,calendarmodel}`, quantity→`{amount,unit}`, monolingualtext→`{language,text}`. 형태가 가변이라 `content`를 `Any`로 받고(`StatementValue`), 출력은 핵심 키만 compact 렌더링한다. **다른 data_type(globe-coordinate 등)은 dict를 `str()`로 폴백** — 라이브 교차검증 권장.
- Action API `wbsearchentities`는 잘못된 파라미터에도 **HTTP 200 + `{"error":{"code","info"}}`**를 줄 수 있어 본문 `error`를 우선 확인한다.
- WDQS 구문 오류(400)는 JSON이 아니라 **자바 예외/HTML 텍스트 본문**이라, 원문을 노출하지 않고 "SPARQL 구문 오류(400)"로만 매핑한다.
- 모든 응답 모델은 부분 모델(`extra="ignore"`)로 핵심 필드만 받는다. labels/descriptions/aliases는 다국어 dict라 출력에서 `language` 우선 선택 후 `en` 폴백.

## 확장 포인트
- lexeme/form/sense 단건(REST `/entities/lexemes/{Lid}` 등), property statements(`/entities/properties/{Pid}/statements`), sitelinks 전체(`/entities/items/{Qid}/sitelinks`), qualifiers/references 상세 렌더링, P/Q 라벨 해석(추가 배치 호출 또는 SPARQL `wikibase:label`)은 동일 패턴으로 경로 상수·도구 추가. SPARQL POST(긴 쿼리)는 `post_form`으로 확장 가능(코어에 이미 있음).
