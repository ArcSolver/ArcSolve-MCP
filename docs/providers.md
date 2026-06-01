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
