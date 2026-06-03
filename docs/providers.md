# 구현 대상 매니페스트 (Providers)

구현할 MCP의 **단일 진실 목록**. 각 블록이 한 서비스이고, 그 안의 공식 문서 링크가 계약 구현의
근거가 된다. 병렬 작업 시 에이전트는 **자기 블록만 읽고**, 구현은 자기 `services/<name>/` 폴더에만 쓴다.

> 작성 규칙은 [AGENTS.md](../AGENTS.md). 새 대상은 아래 **블록 템플릿**을 복사해 추가한다.

**상태 범례**: `planned`(대상 확정) · `in-progress`(구현 중) · `done`(검증 완료)

---

## kakao — 카카오톡 메시지(나에게 보내기)
- 상태: `done`
- 인증: OAuth 2.0 (scope: `talk_message`)
- 공식 문서:
  - 메시지 REST API: https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api
  - 메시지 템플릿(text 등): https://developers.kakao.com/docs/latest/ko/message-template/common
  - 카카오 로그인(토큰): https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
- 도구:
  - `kakao_send_text_to_me` — 텍스트(≤200자) 나에게 전송
  - `kakao_send_link_to_me` — URL 스크랩(미리보기) 나에게 전송
- 스코프(MVP): 포함 = '나에게 보내기'(memo). 제외 = '친구에게'(권한 신청 + 소셜 API 필요 → v2)

---

## telegram — Telegram Bot 메시지 전송/편집/삭제 + 헬스체크
- 상태: `done`
- 인증: Bot 토큰 (URL 경로 `/bot<token>/METHOD` — Bearer 아님)
- 공식 문서:
  - Bot API 레퍼런스: https://core.telegram.org/bots/api
  - sendMessage / sendPhoto / sendDocument / editMessageText / deleteMessage / getMe (각 앵커)
  - 요청/응답 포맷: https://core.telegram.org/bots/api#making-requests
- 도구:
  - `telegram_send_message` — 텍스트(1–4096자) 전송. chat_id 미지정 시 `TELEGRAM_CHAT_ID`
  - `telegram_send_photo` / `telegram_send_document` — 사진·문서 전송(URL·file_id·**로컬 업로드**, caption ≤1024)
  - `telegram_edit_message_text` / `telegram_delete_message` — 메시지 편집(chat ⊕ inline)·삭제
  - `telegram_get_me` — 토큰/봇 신원 확인(헬스체크)
- 스코프: 포함 = 텍스트/사진/문서 전송·편집·삭제·getMe + **로컬 파일 multipart 업로드**(사진≤10MB·파일≤50MB) / 제외 = 인라인 키보드·미디어그룹·기타 미디어(sendVideo 등)

---

## discord — Discord 메시지 전송/편집/삭제(Webhook) + 채널 전송/조회(Bot)
- 상태: `done`
- 인증: Webhook URL(무인증) + (선택) Bot 토큰(`Authorization: Bot` — 채널 직접 전송/조회)
- 공식 문서:
  - Execute/Edit/Delete Webhook Message: https://discord.com/developers/docs/resources/webhook
  - Create / Get Channel Messages: https://discord.com/developers/docs/resources/message
  - Embed 오브젝트: https://discord.com/developers/docs/resources/message#embed-object
- 도구:
  - `discord_send_message` / `discord_send_embed` — content·리치 임베드 전송(Webhook)
  - `discord_edit_message` / `discord_delete_message` — 웹후크 메시지 편집·삭제
  - `discord_create_message` / `discord_list_messages` — Bot 토큰으로 채널 전송·조회
- 스코프: 포함 = Webhook 전송/임베드/편집/삭제 + Bot 채널 전송/조회 / 제외 = 반응·스레드·첨부파일·components

---

## line — LINE Messaging API 메시지 전송(push/reply/multicast/broadcast) + 프로필
- 상태: `done`
- 인증: 채널 액세스 토큰 (Bearer)
- 공식 문서:
  - Messaging API 레퍼런스: https://developers.line.biz/en/reference/messaging-api/
  - push / reply / multicast / broadcast / get-profile (각 앵커)
  - 채널 액세스 토큰: https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/
- 도구:
  - `line_send_text` — push 1건(≤5000자, UTF-16). to 미지정 시 `LINE_TO`
  - `line_reply_text` — replyToken으로 회신
  - `line_multicast_text` — 여러 userId(최대 500)에 동일 텍스트
  - `line_broadcast_text` — 모든 친구에게 전송
  - `line_get_profile` — userId로 프로필 조회
- 스코프: 포함 = 텍스트 push/reply/multicast/broadcast + 프로필 조회 / 제외 = Flex·template·sticker·image 등 비텍스트, rich menu, webhook 수신 서버

---

## zotero — Zotero 라이브러리 읽기 (Web API v3 + 로컬 데스크톱 API, 단일 서비스·백엔드 전환)
- 상태: `done`
- 구조: **한 서비스 = 두 백엔드.** 로컬 API는 Web API v3를 미러하므로 계약(경로·쿼리·응답 모델)이 거의 동일.
  `ZOTERO_SOURCE=web|local`(미지정 시 API 키 있으면 web, 없으면 local 자동)로 **base URL·인증만** 분기.
- 인증:
  - web: `Zotero-API-Key: <키>` 헤더(권장) · 공개 라이브러리 무인증 · base `https://api.zotero.org`
  - local: **무인증**(`/users/0/...`만) · base `http://localhost:23119/api`(pref `httpServer.localAPI.enabled` 활성 필요) · **읽기 전용**
  - 공통 요청 헤더 `Zotero-API-Version: 3`
- 공식 문서:
  - Web API v3 basics(엔드포인트/쿼리/페이지네이션/백오프): https://www.zotero.org/support/dev/web_api/v3/basics
  - 아이템 타입·필드: https://www.zotero.org/support/dev/web_api/v3/types_and_fields
  - 전문(Full-Text) 포맷: https://www.zotero.org/support/dev/web_api/v3/fulltext_content
  - 로컬 API 1차 출처(공식 레포 소스 주석 — 전용 산문 문서 없음): https://github.com/zotero/zotero/blob/main/chrome/content/zotero/xpcom/server/server_localAPI.js
- 도구(MVP, 전부 GET·읽기):
  - `zotero_search_items` — `/{prefix}/items?q=&qmode=&itemType=&tag=&sort=&limit=&start=` (qmode=everything → 전문 포함)
  - `zotero_get_item` / `zotero_get_item_children` — `/{prefix}/items/<key>`(+`/children`), `include=data,bib,citation`
  - `zotero_list_collections` / `zotero_get_collection_items` — `/{prefix}/collections`(+`/top`), `/collections/<key>/items`
  - `zotero_list_tags` — `/{prefix}/tags`
  - `zotero_get_fulltext` — `/{prefix}/items/<key>/fulltext`
  - `zotero_health` — `/api/`(로컬 활성/버전 확인) 또는 키 유효성
  - (`prefix` = `users/<id>` | `groups/<id>`; 로컬은 `users/0`)
- 제약(공식): limit 기본 25·최대 100, itemKey ≤50, bib ≤150, 동시요청 ≤4. 페이지네이션은 `Total-Results`/`Link: rel=next` **헤더**, 버전 `Last-Modified-Version`, 백오프 `Backoff`/`Retry-After`(429/503). → **코어에 응답 헤더 노출 추가 필요**(아래).
- 스코프(MVP): 포함 = 라이브러리 읽기(items/collections/tags/fulltext/검색) + 헬스 / 제외 = write(로컬 미지원·web v2), 파일 바이너리 다운로드, 비-JSON 포맷(bib/ris 등은 v2), groups 상세
- 코어 의존: `get_json` + (신규) **응답 헤더 노출 동사**(페이지네이션·버전). API-key/버전 헤더 주입은 기존 헤더 인자로 충분.

---

## openalex — OpenAlex 학술 그래프 읽기 (works/authors 검색·조회)
- 상태: `done`
- 인증: **API 키 선택(권장)** — env `OPENALEX_API_KEY` → 쿼리 `api_key=`. 키 없이도 동작(무료 일일 크레딧, 라이브 확인됨). polite pool은 `mailto=`(env `OPENALEX_MAILTO`, 선택). base `https://api.openalex.org`
- 공식 문서:
  - API 개요: https://developers.openalex.org/how-to-use-the-api/api-overview
  - 리스트/검색(search·filter·sort·per-page·page·cursor·select): https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
  - Work 오브젝트: https://developers.openalex.org/api-entities/works/work-object
  - 인증/요금: https://developers.openalex.org/guides/authentication
- 도구(MVP, 전부 GET·읽기):
  - `openalex_search_works(query?, filter?, sort?, per_page?, page?)` — `/works?search=&filter=`
  - `openalex_get_work(id)` — `/works/{id}` (OpenAlex ID `W…` 또는 DOI)
  - `openalex_search_authors(query?, per_page?, page?)` — `/authors?search=`
  - `openalex_get_author(id)` — `/authors/{id}` (OpenAlex ID `A…` 또는 ORCID)
- 응답: `{meta:{count,page,per_page,next_cursor?,cost_usd}, results:[...]}` — 페이지네이션·건수는 **본문 meta**(헤더 아님 → `get_json`으로 충분). **쿼리 파라미터는 `per-page`(하이픈)**, 응답 필드는 `per_page`. 에러는 `{error,message}`.
- 제약(라이브 확인): `per-page` **1–200**, page 기반은 최대 10,000건(이후 cursor), 무료 키 일일 크레딧($1). filter는 `attr:value`(콤마=AND, `|`=OR, `!`=NOT).
- 스코프(MVP): 포함 = works/authors 검색·단건 조회 / 제외 = sources·institutions·topics·publishers·funders, group_by 집계, cursor 딥페이지네이션, ngrams/autocomplete
- 코어 의존: `get_json`만으로 충분(키/mailto는 쿼리 파라미터, 페이지네이션은 본문). 새 코어 동사 불필요.

---

## crossref — Crossref 학술 메타데이터 읽기 (works/journals 검색·조회)
- 상태: `done`
- 인증: **무인증**(키 없음). polite pool은 연락 이메일 `mailto=`(env `CROSSREF_MAILTO`, 선택) — 쿼리 파라미터 + User-Agent에 명시(공식 etiquette). base `https://api.crossref.org`
- 공식 문서:
  - REST API README(엔드포인트·쿼리·rows/offset·sort/order·etiquette): https://github.com/CrossRef/rest-api-doc/blob/master/README.md
  - 응답 포맷(Work 오브젝트): https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md
  - 공식 안내(retrieve metadata): https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- 도구(MVP, 전부 GET·읽기):
  - `crossref_search_works(query?, filter?, sort?, order?, rows?, offset?)` — `/works?query=&filter=`
  - `crossref_get_work(doi)` — `/works/{doi}`
  - `crossref_search_journals(query?, rows?, offset?)` — `/journals?query=`
  - `crossref_get_journal(issn)` — `/journals/{issn}`
- 응답: `{status, message-type, message-version, message:{...}}` — 리스트면 `message`에 `total-results`/`items-per-page`/`items`(본문 → `get_json`으로 충분), 단건이면 `message`가 곧 엔티티. **에러(validation-failure) 봉투의 `message`는 배열**(`[{message,...}]`). Work 필드는 대문자/하이픈(`DOI`·`is-referenced-by-count`·`container-title`) → pydantic alias.
- 제약(라이브 확인): `rows` **0–1000**(기본 20), `offset` 0–10000(이후 cursor), `order`=asc/desc. 없는 DOI/ISSN은 404 + `text/plain` `Resource not found.`. filter는 `name:value`(콤마=AND).
- 스코프(MVP): 포함 = works/journals 검색·단건 조회 / 제외 = members·funders·types·licenses 엔티티, cursor 딥페이지네이션, content negotiation(citation 포맷), `/journals/{issn}/works`, sample·select·facet
- 코어 의존: `get_json`만으로 충분(mailto는 쿼리 파라미터+UA 헤더, 페이지네이션은 본문). 새 코어 동사 불필요.

---

## arxiv — arXiv 학술 프리프린트 읽기 (검색·id 조회, Atom XML)
- 상태: `done`
- 인증: **무인증**(키 없음·env 불필요). 식별용 User-Agent만 전송. base `https://export.arxiv.org/api/query`
- 특수성: arXiv는 JSON이 아니라 **Atom 1.0 XML**을 반환한다 → 코어에 **`get_text`**(raw str) 동사를 추가했고, 서비스는 **표준 라이브러리 `xml.etree.ElementTree`**로 파싱한다(feedparser/lxml 등 외부 의존 없음).
- 공식 문서:
  - API User Manual(쿼리 인터페이스·파라미터·제약·Atom 응답 구조·error feed·etiquette): https://info.arxiv.org/help/api/user-manual.html
  - API 개요(공개 API 안내): https://info.arxiv.org/help/api/index.html
- 도구(MVP, 전부 GET·읽기):
  - `arxiv_search(query, start?, max_results?, sort_by?, sort_order?)` — `/api/query?search_query=`(필드 prefix `ti`/`au`/`abs`/`cat`/`all` + `AND`/`OR`/`ANDNOT` 문자열 그대로)
  - `arxiv_get(id_list)` — `/api/query?id_list=`(콤마 구분, 단건 상세/다건 요약)
- 네임스페이스: atom `http://www.w3.org/2005/Atom` · opensearch `http://a9.com/-/spec/opensearch/1.1/` · arxiv `http://arxiv.org/schemas/atom`. 피드 건수/페이지네이션은 본문 `opensearch:totalResults`/`startIndex`/`itemsPerPage`. entry: id(abs URL)·title·summary(초록)·author/name(+arxiv:affiliation)·published·updated·category(term/scheme)·arxiv:primary_category·link(abstract/pdf/doi 최대 3)·arxiv:comment·arxiv:journal_ref·arxiv:doi.
- 제약(공식): `max_results` 기본 10·**1회 ≤2000 권장·총 ≤30000**(초과 HTTP 400), `start` 0-based, `sortBy`=relevance/lastUpdatedDate/submittedDate, `sortOrder`=ascending/descending. ⚠️ **에러는 HTTP 200**: malformed id 등은 4xx가 아니라 **HTTP 200 + 단일 `<entry>` title='Error'**(`<id>`=`/api/errors#...`)로 온다 → 파서가 `is_error_feed`로 감지해 `ArxivErrorEntry`로 매핑. etiquette는 연속 호출 시 3초 지연 권장(코드 지연/재시도는 비목표).
- 스코프(MVP): 포함 = search_query 검색·id_list 조회(메타데이터) / 제외 = boolean 빌더(쿼리는 문자열 그대로), full-text(API는 메타만), figures, RSS/OAI-PMH
- 코어 의존: **신규 `get_text`**(비-JSON raw str) + 표준 라이브러리 XML 파서. 무인증이라 헤더 주입 불필요.

---

## semanticscholar — Semantic Scholar 학술 그래프 읽기 (papers/authors 검색·조회)
- 상태: `done`
- 인증: **API 키 선택** — env `SEMANTICSCHOLAR_API_KEY` → `x-api-key` **헤더**(OpenAlex의 쿼리 파라미터와 달리 헤더). 키 없이도 동작(공유 풀, 라이브 확인됨). base `https://api.semanticscholar.org/graph/v1`
- 공식 문서:
  - OpenAPI(Swagger) 스펙(엔드포인트·쿼리·limit/offset·fields·응답 스키마): https://api.semanticscholar.org/api-docs/graph (원본 JSON: https://api.semanticscholar.org/graph/v1/swagger.json)
  - 공식 튜토리얼(base URL·fields·rate limit·x-api-key): https://www.semanticscholar.org/product/api/tutorial
- 도구(MVP, 전부 GET·읽기):
  - `s2_search_papers(query, fields?, limit?, offset?, year?)` — `/paper/search?query=&fields=`
  - `s2_get_paper(id, fields?)` — `/paper/{id}` (paperId 또는 `DOI:`·`ARXIV:`·`CorpusId:`·`MAG:`·`ACL:`·`PMID:`·`PMCID:`·`URL:`)
  - `s2_search_authors(query, fields?, limit?, offset?)` — `/author/search?query=`
  - `s2_get_author(id, fields?)` — `/author/{id}` (S2 authorId)
- 응답: 검색 봉투 `{total, offset, next?, data:[...]}`(본문 → `get_json`으로 충분), 단건은 entity가 곧 최상위. **`fields`**(콤마 구분, 중첩 `.`)로 반환 필드 선택 — 미지정 시 상류 기본 최소 필드(`paperId,title`/`authorId,name`). 에러는 `{error}`(검증/404) 또는 `{message,code}`(429).
- 제약(라이브 확인): paper search `limit` **1–100**(기본 10) + relevance **offset+limit<1000**(이상은 bulk/Datasets — 범위 밖), author search `limit` **1–1000**. 응답 ≤10MB. 없는 id는 404 `{error:"... not found"}`.
- 레이트리밋: 키 없으면 **공유 풀**(혼잡 시 429↑), 키 있으면 **전 엔드포인트 합산 1 RPS**(검토 후 상향 가능).
- 스코프(MVP): 포함 = papers/authors 검색·단건 조회 / 제외 = bulk search(`/paper/search/bulk` cursor), citations/references 그래프 확장, recommendations·datasets API
- 코어 의존: `get_json`만으로 충분(키는 `x-api-key` 헤더, 페이지네이션은 본문). 새 코어 동사 불필요.

---

## openmeteo — Open-Meteo 날씨·기후 읽기 (예보·지오코딩)
- 상태: `done`
- 인증: **무인증**(키 없음·env 불필요·`.env.example` 무변경). 식별용 User-Agent만 전송. `apikey`는 상업용 도메인 전용(범위 밖). base 예보 `https://api.open-meteo.com/v1`, 지오코딩 `https://geocoding-api.open-meteo.com/v1`
- 공식 문서:
  - 예보 API(엔드포인트·파라미터·`forecast_days` 0–16·hourly/daily/current·응답 구조·에러 봉투): https://open-meteo.com/en/docs
  - 지오코딩 API(엔드포인트·`name`/`count`/`language`/`countryCode`·`results` 필드): https://open-meteo.com/en/docs/geocoding-api
- 도구(MVP, 전부 GET·읽기):
  - `openmeteo_geocode(name, count?, language?)` — `geocoding-api/v1/search?name=`(좌표·국가·시간대 → 다른 도구 입력 보조)
  - `openmeteo_forecast(latitude, longitude, hourly?, daily?, current?, timezone?, forecast_days?)` — `api/v1/forecast`(hourly/daily/current는 콤마 구분 변수명 문자열, 예 `temperature_2m,precipitation`)
- 응답: 예보 `{latitude, longitude, elevation, timezone, hourly:{time:[],<변수>:[]}, hourly_units, daily:{...}, daily_units, current:{time, interval, <변수>:value}, current_units}`(본문 → `get_json`으로 충분). 지오코딩 `{results:[{id,name,latitude,longitude,country,country_code,timezone,admin1,...}]}`. **변수 카탈로그가 동적**이라 시계열/단위 블록은 dict로 수신(변수명 검증은 상류 위임).
- 제약(라이브 확인): `forecast_days` **0–16**(기본 7), `count` **1–100**(기본 10), `timezone`=IANA 또는 `auto`. ⚠️ 지오코딩 무매칭 시 `results` 키가 **아예 없다**(빈 배열 아님) → 기본값 `[]`로 안전 처리. 에러는 `{"error":true,"reason":"..."}`(HTTP 400).
- 스코프(MVP): 포함 = 예보 + 지오코딩 검색 / 제외 = air-quality·marine·flood 별도 엔드포인트, 상업용 도메인·`apikey`, `models` 수동선택, `past_days`·단위 파라미터·`timeformat`·Historical(ERA5) API
- 코어 의존: `get_json`만으로 충분(무인증·단발 조회). 새 코어 동사 불필요.
## nws — NWS(National Weather Service) 미국 날씨 읽기 (예보·시간별 예보·활성 기상특보)
- 상태: `done`
- 인증: **무인증**(키 없음). 단 **`User-Agent` 헤더 필수**(없으면 403, 라이브 확인) → 기본값 상수(`contract.DEFAULT_USER_AGENT`)를 항상 전송하고 `NWS_USER_AGENT`로 덮어쓴다(연락처 권장). base `https://api.weather.gov`. 응답 **GeoJSON**(`application/geo+json`).
- 공식 문서:
  - API 안내(base·User-Agent 필수·GeoJSON·엔드포인트·`area` 코드): https://www.weather.gov/documentation/services-web-api
  - OpenAPI 스펙: https://api.weather.gov/openapi.json
- 도구(MVP, 전부 GET·읽기):
  - `nws_forecast(latitude, longitude)` — **2단계**: `/points/{lat},{lon}`로 office/grid → `/gridpoints/{office}/{x},{y}/forecast`
  - `nws_hourly_forecast(latitude, longitude)` — 동일 2단계, `.../forecast/hourly`
  - `nws_alerts(area)` — `/alerts/active?area={2글자 주코드}`
- 특수성: 좌표→예보는 NWS 특유의 **2단계 조회**다. `/points` 응답의 `forecast` URL은 라이브에서 `:80` 포트가 섞여 와서, 그 URL을 직접 쓰지 않고 `gridId`·`gridX`·`gridY`로 경로를 재조립한다.
- 응답: 예보는 GeoJSON `Feature`(`properties.periods[]`: number·name·startTime/endTime·isDaytime·temperature/temperatureUnit·windSpeed/windDirection·shortForecast/detailedForecast). 특보는 `FeatureCollection`(`features[].properties`: event·severity·urgency·areaDesc·effective/expires·headline). 에러는 RFC 7807 problem+json(`{type,title,status,detail}`).
- 제약(라이브 확인): **미국(+속령) 좌표만 유효** — 해외 좌표는 `/points`에서 404(`problems/InvalidPoint`, title "Data Unavailable For Requested Point") → "미국 좌표만 지원" 안내로 매핑. `area`는 2글자 주/속령 코드(50주+DC+AS·GU·PR·VI·MP·PW·FM·MH, 라이브 enum 확인) — 그 외 코드는 상류 400 전에 차단. 무 User-Agent → 403.
- 스코프(MVP): 포함 = 예보·시간별 예보·활성 특보 / 제외 = 관측소 상세(`/stations`), 존별 예보(`/zones/.../forecast`), CAP XML, 원시 그리드 데이터(`forecastGridData`)
- 코어 의존: `get_json`만으로 충분(User-Agent는 `headers=`로 주입, 콘텐츠는 본문 `properties`/`features`). 새 코어 동사 불필요.
## usgs_quake — USGS 지진 정보 읽기 (FDSN Event API — 검색·건수, GeoJSON)
- 상태: `done`
- 인증: **무인증**(키 없음·env 불필요). 식별용 User-Agent만 전송. base `https://earthquake.usgs.gov/fdsnws/event/1`
- 특수성: 응답을 **`format=geojson`으로 고정**한다 → 검색은 GeoJSON FeatureCollection(JSON), 건수는 `{count,maxAllowed}`(JSON)라 코어 `get_json`만으로 충분(새 코어 동사 불필요).
- 공식 문서:
  - FDSN Event API 명세(엔드포인트·전체 쿼리 파라미터·기본/제약·orderby·format·시간형식·에러): https://earthquake.usgs.gov/fdsnws/event/1/
  - 실시간 피드(GeoJSON) 안내(`properties` 필드 의미 — mag/place/time/url): https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
- 도구(MVP, 전부 GET·읽기):
  - `usgs_search_earthquakes(starttime?, endtime?, minmagnitude?, maxmagnitude?, latitude?, longitude?, maxradiuskm?, limit?, orderby?)` — `/query?format=geojson&...`
  - `usgs_count_earthquakes(starttime?, endtime?, minmagnitude?, maxmagnitude?, latitude?, longitude?, maxradiuskm?)` — `/count?format=geojson&...`
- 응답: 검색 = `{type:"FeatureCollection", metadata:{...,count}, features:[{properties:{mag,place,time,url,...}, geometry:{coordinates:[lon,lat,depth]}, id},...]}` — `time`은 **밀리초 epoch**(→ UTC ISO8601 변환), `coordinates`는 **[경도, 위도, 깊이(km)]**(GeoJSON 규약, 출력은 위도·경도로 재배열). 건수 = `{"count":N, "maxAllowed":20000}`. 결과 없음은 **HTTP 200 + 빈 features**(geojson은 nodata 204 안 씀 — 라이브 확인). 에러 본문은 **text/plain**(`Error 400: Bad Request\n\n...`)이라 첫 의미 줄만 노출.
- 제약(라이브 확인): `limit` **1–20000**(기본 20·초과 시 400), `orderby`=time/time-asc/magnitude/magnitude-asc, 시간 **ISO8601**(미지정 시 NOW-30일~현재·UTC), 원형 위치 = `latitude`[-90,90]+`longitude`[-180,180]+`maxradiuskm`[0,20001.6](셋이 한 묶음).
- 스코프(MVP): 포함 = 지진 검색·건수 조회(geojson) / 제외 = QuakeML·CSV·KML·text·xml 포맷, 실시간 요약 피드 파일, 상세 detail product, `eventid` 단건, rectangle(min/max lat·lon) 위치, `offset`/`mindepth`/`maxdepth`/`reviewstatus` 부가 필터
- 코어 의존: `get_json`만으로 충분(무인증·geojson JSON·건수는 본문). 새 코어 동사 불필요.
## airkorea — 에어코리아(한국환경공단) 대기오염정보 읽기 (시도·측정소 실시간 + 예보)
- 상태: `done`
- 인증: **서비스키 필수**(data.go.kr 발급) — OAuth 아니라 **쿼리 파라미터 `serviceKey`**(헤더 아님). env `AIRKOREA_SERVICE_KEY`. base `http://apis.data.go.kr/B552584/ArpltnInforInqireSvc`
- ⚠️ data.go.kr 서비스키 함정: 키는 **Encoding/Decoding 2종** 발급 → httpx가 쿼리 파라미터를 자동 URL-인코딩하므로 params에 **Decoding 키(원문)**를 넣어 이중 인코딩을 피한다(잘못 넣으면 resultCode=30 미등록 키). `returnType=json` 항상 명시(기본 XML 회피).
- 공식 문서:
  - 대기오염정보 OpenAPI(ArpltnInforInqireSvc) 상세(엔드포인트·공통 파라미터·봉투·예보 필드): https://www.data.go.kr/data/15073861/openapi.do
- 도구(MVP, 전부 GET·읽기):
  - `airkorea_realtime_by_region(sidoName, ver?, numOfRows?, pageNo?)` — `/getCtprvnRltmMesureDnsty` 시도별(측정소별 PM10/PM2.5/O3/NO2/CO/SO2·통합지수 khai)
  - `airkorea_realtime_by_station(stationName, dataTerm?, ver?, numOfRows?, pageNo?)` — `/getMsrstnAcctoRltmMesureDnsty` 측정소별 시간대별
  - `airkorea_forecast(searchDate, informCode?, numOfRows?, pageNo?)` — `/getMinuDustFrcstDspth` 대기질 예보통보(권역별 등급·개황·원인·행동요령)
- 응답: 봉투 `{response:{header:{resultCode,resultMsg}, body:{items:[...], totalCount, pageNo, numOfRows}}}` — 본문 페이지네이션 → `get_json`으로 충분. **`resultCode != "00"`이면 에러**(HTTP 200이라도 봉투로 옴; 30=미등록 키, 22=트래픽 초과, 03=데이터 없음 등). 측정값(`pm10Value`·`khaiValue` 등)은 **문자열**·결측 `"-"` → 캐스팅 금지.
- 제약(공식): `sidoName`=전국·서울·…·세종(18), `dataTerm`=DAILY/MONTH/3MONTH, `ver` 기본 1.3(PM2.5 포함, 1.4=24시간 예측이동농도). 레이트리밋 **개발계정 500/일**.
- 스코프(MVP): 포함 = 시도/측정소 실시간 측정 + 예보통보 / 제외 = 측정소 목록(별도 `MsrstnInfoInqireSvc`), CAI 상세, 통계, 주간예보
- 코어 의존: `get_json`만으로 충분(키는 쿼리 파라미터, 페이지네이션은 본문). 새 코어 동사 불필요.
## pubmed — PubMed(NCBI E-utilities) 생의학 문헌 읽기 (검색·요약·abstract)
- 상태: `done`
- 인증: **API 키 선택** — env `NCBI_API_KEY` → `api_key` **쿼리 파라미터**(OpenAlex처럼 헤더 아님). 식별용 `tool`/`email`도 쿼리 파라미터(권장). 키 없이도 동작(초당 3건). base `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`, `db=pubmed`
- 공식 문서:
  - E-utilities Quick Start(개요·base URL·esearch/esummary/efetch 흐름): https://www.ncbi.nlm.nih.gov/books/NBK25500/
  - E-utilities In-Depth(전 파라미터·`retmode`·`sort`·`api_key`·JSON 출력 구조·efetch는 XML만): https://www.ncbi.nlm.nih.gov/books/NBK25499/
  - General Introduction(레이트리밋 3/s·10/s·`api_key`·`tool`/`email` 등록 요구): https://www.ncbi.nlm.nih.gov/books/NBK25497/
- 도구(MVP, 전부 GET·읽기):
  - `pubmed_search(query, retmax?=20, retstart?=0, sort?)` — `esearch.fcgi?db=pubmed&term=&retmode=json` → `{count, idlist:[PMID]}` (**get_json**)
  - `pubmed_get_summary(ids)` — `esummary.fcgi?db=pubmed&id=&retmode=json` → 제목·저자·저널·날짜·DOI (**get_json**)
  - `pubmed_fetch_abstract(ids)` — `efetch.fcgi?db=pubmed&id=&rettype=abstract&retmode=xml` → 초록 텍스트 (**get_text + xml.etree**)
- 응답: esearch JSON 봉투 `{esearchresult:{count, retmax, retstart, idlist:[...]}}`(count 등 라이브에선 문자열 → int 변환), esummary `{result:{uids:[...], "<uid>":{title, authors:[{name,authtype}], source, fulljournalname, pubdate, articleids:[{idtype,value}]}}}`(DOI는 `idtype='doi'`), efetch는 **XML만**(JSON 미지원) `PubmedArticleSet/PubmedArticle/.../Abstract/AbstractText`(구조화 초록 `Label` 속성).
- 제약(공식): esearch `retmax` 기본 20·**최대 10000**, `sort` ∈ relevance/pub_date/Author/JournalName, id 1회 **≤200개**(이상 POST 권장 — 범위 밖). 잘못된 검색식은 HTTP 200 + `{esearchresult:{ERROR}}`.
- 레이트리밋: 키 없으면 **초당 3건**(초과 429), 키 있으면 **초당 10건**.
- 스코프(MVP): 포함 = esearch(검색)·esummary(요약)·efetch(초록) / 제외 = WebEnv/history 체이닝(`usehistory`), pubmed 외 db, MeSH 상세, `elink`/`einfo`/`espell`
- 코어 의존: `get_json`(esearch/esummary) + `get_text`(efetch XML, arxiv가 추가) — 둘 다 기존 코어. 키·tool·email은 쿼리 파라미터. 새 코어 동사 불필요.
## egen — E-Gen(국립중앙의료원) 응급의료정보 읽기 (응급실 실시간 가용병상·중증질환 수용가능·기관 목록)
- 상태: `done`
- 인증: **서비스키 필수**(data.go.kr 발급) — OAuth 아니라 **쿼리 파라미터 `serviceKey`**(헤더 아님). env `EGEN_SERVICE_KEY`. base `http://apis.data.go.kr/B552657/ErmctInfoInqireService`
- ⚠️ data.go.kr 서비스키 함정(airkorea와 동일): 키는 **Encoding/Decoding 2종** 발급 → httpx가 쿼리 파라미터를 자동 URL-인코딩하므로 params에 **Decoding 키(원문)**를 넣어 이중 인코딩을 피한다(잘못 넣으면 resultCode=30 미등록 키). **응답은 XML**(상세 페이지·활용가이드 XML 기준, `_type=json` 공식 확인 불가) → `get_text`+`xml.etree`로 파싱(arxiv 패턴).
- 공식 문서:
  - 국립중앙의료원_전국 응급의료기관 정보 조회 서비스(ErmctInfoInqireService) 상세(base·오퍼레이션·STAGE1/STAGE2·응답 필드): https://www.data.go.kr/data/15000563/openapi.do
  - 중앙응급의료센터 Open API 안내: https://www.e-gen.or.kr/nemc/open_api.do
- 도구(MVP, 전부 GET·읽기):
  - `egen_realtime_beds(stage1, stage2?, numOfRows?, pageNo?)` — `/getEmrrmRltmUsefulSckbdInfoInqire` 응급실 실시간 가용병상(응급실·수술실·중환자실·입원실 가용수 + CT/MRI/조영촬영기/인공호흡기/구급차 가용여부)
  - `egen_severe_acceptance(stage1, stage2?, numOfRows?, pageNo?)` — `/getSrsillDissAceptncPosblInfoInqire` 중증질환자 수용가능(심근경색·뇌출혈·중증화상 등 MKioskTy 단말 표시 기준)
  - `egen_list(stage1, stage2?, numOfRows?, pageNo?)` — `/getEgytListInfoInqire` 응급의료기관 목록(기관명·주소·전화·분류·위경도)
- 응답: 봉투 XML `<response><header><resultCode/><resultMsg/></header><body><items><item/>…<totalCount/><pageNo/></body></response>` — 본문 페이지네이션. **`resultCode != "00"`이면 에러**(HTTP 200이라도 봉투로 옴; 게이트웨이 키 차단은 `<header>` 대신 `cmmMsgHeader/returnReasonCode`로 옴 → 30 등으로 매핑). 병상수(`hvec` 등)는 정수 문자열, 가용여부(`hvctayn` 등)는 `Y`/`N`이며 결측은 빈 값/`-`/`N` → 캐스팅 금지.
- 제약(공식): `STAGE1`(시도)·`STAGE2`(시군구)는 **한글 주소명**(STAGE1 필수, STAGE2 선택). 페이지네이션 `numOfRows`(기본 100)·`pageNo`(기본 1).
- 스코프(MVP): 포함 = 응급실 실시간 가용병상 + 중증질환 수용가능 + 응급의료기관 목록 / 제외 = 외상센터·기관 위치/기본정보·AED·약국 등 별도 오퍼레이션
- provenance 노트: 중증질환 수용가능 `MKioskTy1~28` 슬롯의 정확한 질환 항목명·개수는 상세 페이지의 다운로드 활용가이드(.hwp) 의존이라 인라인 확인 불가 → 개별 필드 고정 모델링 대신 `mkiosk` dict로 느슨히 수집(`contract.py`의 `TODO(provenance)`).
- 코어 의존: `get_text`(XML, arxiv가 추가) — 기존 코어. 키는 쿼리 파라미터, 페이지네이션은 본문. 새 코어 동사 불필요.

---

## seoul_transit — 서울 실시간 교통 읽기 (지하철 도착·따릉이)
- 상태: `done`
- 인증: **인증키 필수 · ⚠️ 2종 분리** — 인증키는 **URL path 첫 세그먼트**(쿼리/헤더 아님). 지하철 실시간은 **전용 '실시간 지하철 인증키'** env `SEOUL_SUBWAY_API_KEY`(호스트 `http://swopenAPI.seoul.go.kr/api/subway`), 따릉이 등 일반은 **'일반 인증키'** env `SEOUL_OPENDATA_API_KEY`(호스트 `http://openapi.seoul.go.kr:8088`). 각 도구가 해당 키 없으면 HTTP 전 안내문 반환.
- 공식 문서:
  - 지하철 실시간 도착(OA-12764): https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do (미러: https://www.data.go.kr/data/15058052/openapi.do)
  - 따릉이 실시간 대여(OA-15493): https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
  - 공통 결과코드(RESULT.CODE) 메세지표: https://data.gangnam.go.kr/openinf/openapiview.jsp?infId=OA-18724
- 도구(MVP, 전부 GET·읽기):
  - `seoul_subway_arrivals(station_name)` — `{KEY}/json/realtimeStationArrival/{START}/{END}/{역명}` (전 호선·상하행 도착)
  - `seoul_bike_status(start?=1, end?=1000, station_name?)` — `{KEY}/json/bikeList/{START}/{END}/` (대여소 현황, **1회 ≤1000건**)
- 응답: 지하철 `{errorMessage:{status,code,message,total}, realtimeArrivalList:[...]}` — code=INFO-000 정상(정상에도 errorMessage 존재). 따릉이 `{rentBikeStatus:{list_total_count, RESULT:{CODE,MESSAGE}, row:[...]}}` — 인증키/요청오류는 최상위 `RESULT`로도 옴(양쪽 검사). 항목 값은 전부 **문자열**(거치수·위경도·시각). 본문 기반 → `get_json`으로 충분(헤더 동사 불필요).
- 제약(공식): 따릉이 1회 **최대 1000건**(end−start+1≤1000, 초과 `ERROR-336` — HTTP 전 차단). 결과코드 매핑: INFO-100 인증키·INFO-200 데이터없음·ERROR-3xx 요청·ERROR-5xx/6xx 서버. 지하철 `recptnDt`(생성시각)는 **과거** → '현재로부터 N초 전' 보정 표시.
- 스코프(MVP): 포함 = 지하철 한 역 실시간 도착 + 따릉이 실시간 대여소 / 제외 = 버스(전국 TAGO 별도), 지하철 실시간 열차위치(OA-12601)·도착일괄(OA-15799), 따릉이 대여소 정적정보(OA-13252)·이용현황 통계
- 코어 의존: `get_json`만으로 충분(인증키·json·요청위치·역명은 path 세그먼트, 봉투는 본문). 새 코어 동사 불필요.

---

## tago_transit — TAGO 전국 대중교통 통합 읽기 (버스 도착·정류소·노선 + 고속/시외버스 + 열차)
- 상태: `done`
- 인증: **서비스키 필수** — 쿼리 파라미터 `serviceKey`(헤더 아님), env `TAGO_SERVICE_KEY`. ⚠️ **Decoding 키(원문)**(이중 인코딩 방지). 단일 키로 TAGO 네임스페이스 `1613000`의 6개 서비스 전부 커버. 키 없으면 HTTP 전 안내문 반환.
- 공식 문서(전부 data.go.kr · 네임스페이스 1613000):
  - 버스도착 ArvlInfoInqireService: https://www.data.go.kr/data/15098530/openapi.do (`getSttnAcctoArvlPrearngeInfoList`·`getCtyCodeList`)
  - 버스정류소 BusSttnInfoInqireService: https://www.data.go.kr/data/15098534/openapi.do (`getSttnNoList`)
  - 버스노선 BusRouteInfoInqireService: https://www.data.go.kr/data/15098529/openapi.do (`getRouteAcctoThrghSttnList`)
  - 고속버스 ExpBusInfoService: https://www.data.go.kr/data/15098522/openapi.do (`getStrtpntAlocFndExpbusInfo`·`getExpBusTrminlList`)
  - 시외버스 SuburbsBusInfoService: https://www.data.go.kr/data/15098541/openapi.do (`getStrtpntAlocFndSuberbsBusInfo`·`getSuberbsBusTrminlList`)
  - 열차 TrainInfoService: https://www.data.go.kr/data/15098552/openapi.do (`getCtyAcctoTrainList`)
  - 구 TAGO 13종 호출중지·대체 공지(이 6종이 현행 대체본): https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000002723
- 도구(MVP 7개, 전부 GET·읽기 · `http://apis.data.go.kr/1613000<service><op>`):
  - `tago_city_codes()` — `/ArvlInfoInqireService/getCtyCodeList` 도시코드 목록(버스 입력 `city_code` 보조)
  - `tago_search_bus_stops(city_code, node_name, numOfRows?, pageNo?)` — `/BusSttnInfoInqireService/getSttnNoList` 정류소명 검색→nodeId
  - `tago_bus_arrivals(city_code, node_id, numOfRows?, pageNo?)` ⭐ — `/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList` 정류소별 실시간 도착예정(노선번호·남은 정류장·도착예정 초→분)
  - `tago_bus_route(city_code, route_id, numOfRows?, pageNo?)` — `/BusRouteInfoInqireService/getRouteAcctoThrghSttnList` 노선 경유정류소
  - `tago_express_bus(dep_terminal_id, arr_terminal_id, dep_date, numOfRows?, pageNo?)` — `/ExpBusInfoService/getStrtpntAlocFndExpbusInfo` 고속버스 운행(등급·요금·출/도착)
  - `tago_intercity_bus(dep_terminal_id, arr_terminal_id, dep_date, numOfRows?, pageNo?)` — `/SuburbsBusInfoService/getStrtpntAlocFndSuberbsBusInfo` 시외버스 운행
  - `tago_train(dep_station_id, arr_station_id, dep_date, numOfRows?, pageNo?)` — `/TrainInfoService/getCtyAcctoTrainList` 도시간 열차(KTX/일반 — 등급·열차번호·요금)
- 응답: 봉투 `{response:{header:{resultCode,resultMsg}, body:{items:{item:[...]}, totalCount,pageNo,numOfRows}}}`. **`resultCode != "00"`이면 에러**(HTTP 200이라도 봉투로 옴; 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`로도 옴 → 30 등 매핑). ⚠️ data.go.kr JSON quirk: `body.items`는 한 단계 더(`{"item":…}`) 싸이고 1건이면 단일 객체·0건이면 빈 문자열 `""` → `normalize_items`가 흡수. 코드·요금·시각은 **문자열** 보존(캐스팅 금지).
- 코드 의존: 버스는 `city_code`+`node_id`/`route_id`, 고속/시외는 터미널ID, 열차는 역ID가 필요 → `tago_city_codes`·`tago_search_bus_stops`가 버스 입력을 자기완결하게 보조. 터미널/역 ID는 각 서비스의 *목록조회 오퍼레이션(MVP 외) 경로를 README에 안내.
- 스코프(MVP): 포함 = 버스 도착/정류소/노선 + 고속/시외버스 + 도시간 열차 / 제외 = 버스 실시간 위치(BusLcInfoService)·퍼스널모빌리티·터미널/역 코드 마스터 조회(입력 ID 확보 경로만 안내)·노선번호 목록.
- 코어 의존: `get_json`만으로 충분(서비스키·`_type=json`·코드는 쿼리, 봉투는 본문). 새 코어 동사 불필요.
- provenance 노트: 고속/시외/열차 서비스 경로의 `…Service` 접미사는 대체 공지·국토부 표기 기준(영문 상세는 축약형 `ExpBusInfo`/`TrainInfo` 표시 — 표시용 약어로 봄). 일부 응답 필드명(노선 경유정류소 `nodeord`/`updowncd`, 고속/시외 `gradeNm`/`charge`, 열차 `traingradename`/`adultcharge`)은 상세 페이지가 첫 오퍼레이션만 렌더해 동 네임스페이스 표준 표기 채택 → `extra="ignore"`로 흡수(`contract.py`의 `TODO(provenance)`). 라이브 키 없어 4종 경로 직접 검증은 보류.

---

## airport — 인천국제공항 여객편 운항현황 읽기 (실시간 출발·도착)
- 상태: `done`
- 인증: **서비스키 필수** — 쿼리 파라미터 `serviceKey`(헤더 아님), env `AIRPORT_SERVICE_KEY`. ⚠️ **Decoding 키(원문)**(이중 인코딩 방지). 인천국제공항공사 기관코드 `B551177`, 단일 키로 운항현황 상세조회 서비스 커버. 키 없으면 HTTP 전 안내문 반환. ⚠️ **개발계정 일 500건** 트래픽 제한.
- 공식 문서(data.go.kr · 인천국제공항공사 B551177):
  - 항공기 운항 현황 상세 조회(여객편 운항현황 상세조회): https://www.data.go.kr/data/15140153/openapi.do (`StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp`·`…/getPassengerDeparturesDeOdp`)
- 도구(MVP 2개, 전부 GET·읽기 · `http://apis.data.go.kr/B551177/StatusOfPassengerFlightsDeOdp<op>`):
  - `airport_arrivals(search_day?, from_time?, to_time?, airport_code?, flight_id?, lang?, numOfRows?, pageNo?)` ⭐ — `/getPassengerArrivalsDeOdp` 여객편 도착현황(편명·항공사·출발지·예정/변경시각·터미널·수하물수취대·출구·운항상태)
  - `airport_departures(search_day?, from_time?, to_time?, airport_code?, flight_id?, lang?, numOfRows?, pageNo?)` ⭐ — `/getPassengerDeparturesDeOdp` 여객편 출발현황(편명·항공사·목적지·예정/변경시각·터미널·체크인카운터·탑승구·운항상태)
- 요청: `searchday`(YYYYMMDD, 미지정 시 당일 · D-3~D+6)·`from_time`/`to_time`(HHMM, 기본 0000~2400)·`airport_code`/`flight_id`(선택 필터)·`lang`(K 국문/E 영문)·`numOfRows`/`pageNo`. ⚠️ 인천공항은 `_type`이 아니라 **`type=json`**(외부 구현 실호출 교차확인).
- 응답: 봉투 `{response:{header:{resultCode,resultMsg}, body:{items:[...], totalCount,pageNo,numOfRows}}}`. **`resultCode != "00"`이면 에러**(HTTP 200이라도 봉투로 옴; 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`로도 옴 → 30/22 등 매핑). ⚠️ items quirk: 인천공항은 `body.items`가 **곧장 리스트**(타 data.go.kr 서비스의 `items.item` 중첩과 다름), 1건이면 단일 객체·0건이면 빈 리스트/빈 문자열 → `normalize_items`가 흡수. 편명·시각·터미널·게이트는 **문자열** 보존(캐스팅 금지).
- 스코프(MVP): 포함 = 인천공항 여객편 실시간 출발·도착 운항현황 / 제외 = 화물편 운항현황·주차/혼잡도/면세/기상/교통 등 부가 서비스·KAC(김포/제주 등) 타 공항.
- 코어 의존: `get_json`만으로 충분(서비스키·`type=json`·필터는 쿼리, 봉투는 본문). 새 코어 동사 불필요.
- provenance 노트: 기관코드 `B551177`·서비스 `StatusOfPassengerFlightsDeOdp`·오퍼레이션 `getPassengerArrivalsDeOdp`/`getPassengerDeparturesDeOdp`·`type=json` 파라미터·요청 파라미터(`searchday`/`from_time`/`to_time`/`lang`)·응답 필드(`airline`/`flightId`/`airport`/`airportCode`/`scheduleDateTime`/`estimatedDateTime`/`terminalid`/`gatenumber`/`remark`/`fid`, 도착 `carousel`/`exitnumber`, 출발 `chkinrange`)는 data.go.kr 15140153 + 다수 외부 구현 실호출/실응답으로 교차확인. `codeshare`/`city` 등 일부 필드는 상세 페이지 JS 렌더로 정적 스키마 미확인 → 확인된 필드만 모델에 두고 `extra="ignore"`로 흡수(`contract.py`의 `TODO(provenance)`). 라이브 키 없어 라이브 호출 검증은 보류.
## ev_charger — 전기차 충전소(한국환경공단) 정보·실시간 상태 읽기 (충전소 정보 + 충전기 실시간 상태)
- 상태: `done`
- 인증: **서비스키 필수**(data.go.kr 발급) — OAuth 아니라 **쿼리 파라미터 `serviceKey`**(헤더 아님). env `EV_CHARGER_SERVICE_KEY`. base `http://apis.data.go.kr/B552584/EvCharger`(airkorea와 같은 기관 B552584).
- ⚠️ data.go.kr 서비스키 함정(airkorea·egen과 동일): 키는 **Encoding/Decoding 2종** 발급 → httpx가 쿼리 파라미터를 자동 URL-인코딩하므로 params에 **Decoding 키(원문)**를 넣어 이중 인코딩을 피한다(잘못 넣으면 resultCode=30 미등록 키). **응답은 XML**(상세 페이지·활용가이드 v1.23 XML 기준, `_type=json` 공식 확인 불가) → `get_text`+`xml.etree`로 파싱(egen/arxiv 패턴).
- 공식 문서:
  - 한국환경공단_전기자동차 충전소 정보 OpenAPI(EvCharger) 상세(base·오퍼레이션·serviceKey/pageNo/numOfRows/period/zcode·getChargerStatus 응답 필드·stat 코드·실시간 5분 갱신): https://www.data.go.kr/data/15076352/openapi.do
  - 전국전기차충전소표준데이터(정보 필드 한글 라벨 교차참조): https://www.data.go.kr/data/15013115/standard.do
- 도구(MVP, 전부 GET·읽기):
  - `evcharger_status(zcode?, zscode?, period?, numOfRows?, pageNo?)` ⭐ — `/getChargerStatus` 충전기 실시간 상태(충전중/충전대기/통신이상/운영중지/점검중/상태미확인 + 상태갱신일시). 지역코드 필터.
  - `evcharger_info(zcode?, zscode?, numOfRows?, pageNo?)` — `/getChargerInfo` 충전소 정보(충전기 타입 코드·주소·위경도·운영기관·이용가능시간). 지역코드 필터.
- 응답: 봉투 XML `<response><header><resultCode/><resultMsg/></header><body><items><item/>…<totalCount/><pageNo/></body></response>` — 본문 페이지네이션. **`resultCode != "00"`이면 에러**(HTTP 200이라도 봉투로 옴; 게이트웨이 키 차단은 `<header>` 대신 `cmmMsgHeader/returnReasonCode`로 옴 → 30 등 매핑). 상태(`stat`)·타입(`chgerType`)·위경도·플래그(`*Yn`)는 **문자열**·결측 빈 값 → 캐스팅 금지. `stat` 코드: 1통신이상·2충전대기·3충전중·4운영중지·5점검중·9상태미확인(한글 표시).
- 제약(공식): `zcode`(시도)·`zscode`(시군구)는 **행정구역 지역코드**(zcode=앞 2자리, 선택). `period`(분, status 전용) 기본 5·[1,10] 클램프. `numOfRows` 기본 100·**[10,9999]** 클램프·`pageNo` 기본 1.
- ⚠️ 실시간 지연: `getChargerStatus`는 "실시간"이지만 상류가 **약 5분 주기** 갱신 → 결과는 수 분 지연된 캐시 스냅샷(`statUpdDt`로 갱신시각 확인). 도구 출력 헤더에 "약 5분 지연(캐시 스냅샷)" 명시.
- 스코프(MVP): 포함 = 충전기 실시간 상태 + 충전소 정보 / 제외 = 전국전기차충전소표준데이터(정적 표준데이터)·급속충전 별도 서비스·충전량/통계.
- provenance 노트: `getChargerStatus`만 상세 페이지에 인라인 렌더(busiId·statId·chgerId·stat·statUpdDt + stat 코드 의미 확인). `getChargerInfo` 응답 필드 전체 표와 `chgerType` 코드표는 다운로드 활용가이드(.docx v1.23)에만 있어, 정보 필드는 표준데이터(15013115) 한글 라벨로 교차확인·`extra="ignore"`로 느슨히 받고 미상 chgerType 코드는 원본 보존(`contract.py`의 `TODO(provenance)`). zcode/zscode 전체 코드↔지역명 표는 미제공(가이드 의존) → 코드 문자열 그대로 전달.
- 코어 의존: `get_text`(XML, arxiv가 추가) — 기존 코어. 키는 쿼리 파라미터, 페이지네이션은 본문. 새 코어 동사 불필요.
## parking — 한국교통안전공단 전국 주차장 정보 읽기 (시설·운영 + 실시간 잔여면 ⭐ 연동 주차장 한정)
- 상태: `done`
- 인증: data.go.kr 서비스키 (쿼리 파라미터 `serviceKey` — **Decoding 키**, 이중 인코딩 방지). OAuth 아님.
- 공식 문서:
  - 한국교통안전공단 주차정보 제공 API: https://www.data.go.kr/data/15099883/openapi.do
    - `PrkSttusInfo`(주차장 시설정보 — 주차장명·도로명주소·위경도·총 주차구획 수, PK `prk_center_id`)
    - `PrkOprInfo`(주차장 운영정보 — 운영시간·요금)
    - `PrkRealtimeInfo`(주차장 실시간 정보 — 현재 주차가능 구획 수 ⭐ 연동 주차장 한정)
- 도구(MVP 3개, 전부 GET·읽기 · `http://apis.data.go.kr/B553881/Parking/<op>`):
  - `parking_search(numOfRows?, pageNo?)` — `/PrkSttusInfo` 전국 주차장 시설정보(주차장명·도로명주소·위경도·총 주차구획 수·PK)
  - `parking_operation(numOfRows?, pageNo?)` — `/PrkOprInfo` 운영정보(운영시간·기본/추가 요금·무료회차)
  - `parking_realtime(numOfRows?, pageNo?)` ⭐ — `/PrkRealtimeInfo` 실시간 잔여 주차면(현재/총 주차가능 구획 수)
- 응답: 봉투 quirk(**B553881 고유 — tago/airkorea와 다름**) — 최상위 `{resultCode, resultMsg, totalCount, pageNo, numOfRows, <오퍼레이션명>: [항목...]}`. 즉 항목 배열이 **오퍼레이션명 키 바로 아래**에 실린다(표준 `response.body.items.item` 아님). **`resultCode != "00"`이면 에러**(HTTP 200이라도 봉투로 옴; 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`로도 옴 → 30 등 매핑). 1건이면 단일 객체·0건이면 키 누락 → `normalize_items`가 흡수. 모든 응답은 **주차장관리번호 `prk_center_id`를 PK**로 공유. 좌표·요금·시각·면수는 **문자열** 보존(캐스팅 금지, 잔여 0면도 보존). 인증 `format=2`(JSON, 1=XML) 명시.
- 스코프(MVP): 포함 = 시설정보 + 운영정보 + 실시간 잔여면(연동 주차장) / 제외 = 서울 공영주차장(별도 데이터셋)·주정차금지구역 등 표준데이터(정적)·개별 주차장관리번호 단건 조회(상류 미제공).
- ⚠️ **실시간 잔여면 커버리지 한계**: 공식 안내상 운영·실시간 정보는 시설정보보다 데이터 수가 훨씬 적다 — **시스템에 연동된 일부 주차장만** 실시간 잔여면 제공, 대다수는 정적 시설정보 전용. 도구 설명·README에 명시(과장 금지).
- 코어 의존: `get_json`만으로 충분(서비스키·`format`·페이지는 쿼리, 봉투는 본문). 새 코어 동사 불필요.
- provenance 노트: base·시설정보(PrkSttusInfo 경로·`serviceKey`/`pageNo`/`numOfRows`/`format`·`prk_center_id`/`prk_plce_nm`/`prk_plce_adres`/`prk_plce_entrc_la,lo`/`prk_cmprt_co`·PK)는 data.go.kr 상세에서 직접 확인. 운영(PrkOprInfo)·실시간(PrkRealtimeInfo) 경로 및 필드(`opertn_*`/`parking_chrge_*`, 실시간 `pkfc_ParkingLots_total`/`pkfc_Available_ParkingLots_total`)는 상세 페이지가 필드 정의를 내려받기 기술문서(.docx)에 둬 인라인 미확인 → **둘 이상의 독립 외부 구현(실제 API 호출 코드·사용 문서)으로 교차확인**해 채택. 봉투 형태(오퍼레이션명 키 아래 항목 배열)도 외부 구현 교차확인. 노상/노외/부설 구분·요일별 운영시간은 표기 미확정 → `extra="ignore"`로 흡수(`contract.py`의 `TODO(provenance)`). 라이브 키 없어 4xx/5xx·실데이터 경로는 mock 검증.

---

## wikipedia — 위키백과 읽기 (검색·요약·본문·링크)
- 상태: `done`
- 인증: **무인증**(전체 읽기 동작). 단 **`User-Agent` 헤더 요구**(없거나 약하면 403/스로틀) → 기본값 상수(`contract.DEFAULT_USER_AGENT`)를 항상 전송하고 `WIKIPEDIA_USER_AGENT`로 덮어쓴다(연락처 권장). (선택) `WIKIPEDIA_API_TOKEN` → `Authorization: Bearer`(UA와 함께) 전송 시 레이트리밋 완화. base **언어판별** `https://{lang}.wikipedia.org`.
- 공식 문서:
  - per-wiki REST(검색) 레퍼런스: https://www.mediawiki.org/wiki/API:REST_API/Reference
  - Wikimedia REST API(rest_v1 summary): https://www.mediawiki.org/wiki/Wikimedia_REST_API (per-wiki 명세: https://en.wikipedia.org/api/rest_v1/)
  - TextExtracts(`prop=extracts`·`exintro`·`explaintext`·`exchars`): https://www.mediawiki.org/wiki/Extension:TextExtracts
  - Action API Query(`prop=links|categories`·`formatversion=2`·`redirects`): https://www.mediawiki.org/wiki/API:Query
- 도구(MVP 4개, 전부 GET·읽기 · `https://{lang}.wikipedia.org<path>`):
  - `wikipedia_search(query, lang="en", limit=10)` — 클린 REST `/w/rest.php/v1/search/page?q=&limit=`(구식 Action `list=search` 아님). 제목·요약·스니펫(HTML 태그 제거)
  - `wikipedia_summary(title, lang="en")` — rest_v1 `/api/rest_v1/page/summary/{title}`(path segment 인코딩). lead extract·문서 URL·**Wikidata Q-id**(`wikibase_item`)·좌표(지리)·동음이의 안내
  - `wikipedia_extract(title, lang="en", intro_only=True, max_chars=None)` — TextExtracts `/w/api.php?action=query&prop=extracts&explaintext=1&formatversion=2`. 도입부/전체·`exchars`
  - `wikipedia_links(title, lang="en", limit=50)` — Action API `prop=links|categories&plnamespace=0&formatversion=2`. 나가는 문서 링크 + 분류
- 특수성: 세 종류 엔드포인트 혼합(per-wiki REST 검색 · rest_v1 요약 · Action API 본문/링크). ⚠️ `api.wikimedia.org/core/v1/*`(통합 REST)는 2026-07 deprecation 예정·후속 없음 → 사용하지 않는다. Action API는 `formatversion=2`로 `query.pages`를 **깨끗한 배열**(pageid-keyed 객체 아님)로 받고 `redirects=1`로 리다이렉트를 추적한다. rest_v1 요약은 리다이렉트를 자동 추적한다.
- 응답: REST 검색 `{"pages":[{id,key,title,excerpt(HTML),description,thumbnail?}]}`(**total 없음**, 라이브 확인). rest_v1 요약 최상위 `{type,title,description,extract,content_urls.desktop.page,thumbnail.source,lang,wikibase_item,coordinates?}`. TextExtracts `{"query":{"pages":[{pageid,title,extract}|{title,missing:true}],"redirects":?}}`. links/categories `query.pages[0].{links[]{ns,title},categories[]{ns,title}}`(둘 다 없을 수 있음). ⚠️ Action API는 잘못된 파라미터에 **HTTP 200 + `{"error":{"code","info"}}`**(4xx 아님) → 본문 보고 `error.info` 매핑.
- 제약(라이브 확인): 검색 `limit` **1–100**(기본 10), 링크/분류 `limit` **1–500**(기본 50), `max_chars`(exchars) **1–1200**. `lang`은 소문자 언어 코드(`[a-z]`+하이픈 변형, 예 `en`·`ko`·`de`·`zh`·`simple`·`zh-yue`) — 형식 위반은 HTTP 전에 차단(호스트 오염 방지). 요약 404 / 본문·링크 `missing:true` → "문서를 찾을 수 없습니다". 무 User-Agent → 403, 스로틀 → 429.
- 스코프(MVP): 포함 = 검색·요약·본문·링크/분류 / 제외 = 편집·쓰기, 미디어 업로드, 위키데이터 엔티티 상세(요약의 `wikibase_item`만 브리지), `api.wikimedia.org/core/v1/*`(deprecating), CirrusSearch 고급 구문, parse/HTML 렌더, 카테고리 멤버 역방향(`list=categorymembers`)
- 코어 의존: `get_json`만으로 충분(User-Agent/Bearer는 `headers=`로 주입, 콘텐츠는 본문). 새 코어 동사 불필요.
- provenance 노트: 4개 엔드포인트·모든 응답 필드를 라이브(en.wikipedia.org)에서 직접 확인. Action API **HTTP 200+`{error}`** 봉투(`action=nonsense` → `badvalue`, `exchars=abc` → `badinteger`)·REST 검색 **total 부재**·`formatversion=2` 배열 형태·`missing:true`·요약 `wikibase_item`/`coordinates`·rest_v1 리다이렉트 추적 전부 라이브 확인. `WIKIPEDIA_API_TOKEN`(Bearer)은 토큰 없이 라이브 검증 불가 → **헤더 조립만 단위 테스트로 확인**(유효성·완화 효과 미검증).

---

## 블록 템플릿 (복사해서 새 대상 추가)

```markdown
## <name> — <한 줄 설명>
- 상태: planned
- 인증: OAuth(scope: ...) | API key | none
- 공식 문서:
  - API 레퍼런스: <url>
  - 인증/토큰: <url>
  - 스키마/오브젝트: <url>
- 도구:
  - `<name>_<action>` — <설명>
- 스코프(MVP): 포함 = ... / 제외 = ...
```

> 채울 때 주의: 모든 링크는 **공식 provider 문서**여야 한다(블로그·서드파티 금지). 엔드포인트·필드
> 규격이 그 링크에서 확인되지 않으면 `planned` 상태로 두고 비워둔다 — 구현 단계에서 환각 방지.
