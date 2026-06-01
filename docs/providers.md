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

## telegram — Telegram Bot 메시지 전송
- 상태: `done`
- 인증: Bot 토큰 (URL 경로 `/bot<token>/METHOD` — Bearer 아님)
- 공식 문서:
  - Bot API 레퍼런스: https://core.telegram.org/bots/api
  - sendMessage: https://core.telegram.org/bots/api#sendmessage
  - 요청/응답 포맷: https://core.telegram.org/bots/api#making-requests
- 도구:
  - `telegram_send_message` — 텍스트(1–4096자) 전송. chat_id 미지정 시 `TELEGRAM_CHAT_ID`
- 스코프(MVP): 포함 = sendMessage(텍스트) / 제외 = 미디어(sendPhoto 등 multipart → 코어 확장 필요), 인라인 키보드

---

## discord — Discord Webhook 메시지 전송
- 상태: `done`
- 인증: Webhook URL (URL 자체가 시크릿, 별도 인증 헤더 없음)
- 공식 문서:
  - Execute Webhook: https://discord.com/developers/docs/resources/webhook#execute-webhook
  - Message Object: https://discord.com/developers/docs/resources/message#message-object
- 도구:
  - `discord_send_message` — content(≤2000자) 전송, username/avatar_url 덮어쓰기 가능
- 스코프(MVP): 포함 = Execute Webhook(content) / 제외 = Bot 토큰 경로(create-message), embeds·file·components

---

## line — LINE Messaging API push 전송
- 상태: `done`
- 인증: 채널 액세스 토큰 (Bearer)
- 공식 문서:
  - Messaging API 레퍼런스: https://developers.line.biz/en/reference/messaging-api/
  - Send push message: https://developers.line.biz/en/reference/messaging-api/#send-push-message
  - 채널 액세스 토큰: https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/
- 도구:
  - `line_send_text` — 텍스트(≤5000자) push 1건. to 미지정 시 `LINE_TO`
- 스코프(MVP): 포함 = push message(text) / 제외 = reply/multicast/broadcast, sticker·image 등 비텍스트 메시지

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
