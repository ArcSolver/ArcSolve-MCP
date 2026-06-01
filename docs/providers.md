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
