# Discord 서비스

Discord 채널에 메시지를 보내고(임베드 포함) 편집·삭제하며, Bot 토큰으로 임의 채널에
메시지를 전송·조회하는 래퍼. 두 인증 경로(Webhook / Bot 토큰)를 지원한다.

## 계약 출처 (공식 문서)
- Execute Webhook: https://discord.com/developers/docs/resources/webhook#execute-webhook
- Edit Webhook Message: https://discord.com/developers/docs/resources/webhook#edit-webhook-message
- Delete Webhook Message: https://discord.com/developers/docs/resources/webhook#delete-webhook-message
- Message Object / Embed: https://discord.com/developers/docs/resources/message#message-object
- Create Message: https://discord.com/developers/docs/resources/message#create-message
- Get Channel Messages: https://discord.com/developers/docs/resources/message#get-channel-messages
- API Base URL / 버전: https://discord.com/developers/docs/reference#api-reference-base-url
- 인증(Bot 토큰 스킴): https://discord.com/developers/docs/reference#authentication
- JSON 에러 코드: https://discord.com/developers/docs/topics/opcodes-and-status-codes#json-json-error-codes
> (위 URL은 `https://docs.discord.com/developers/...`로 301 리다이렉트된다.)
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트·요청/응답 모델).

## 엔드포인트
| 종류 | METHOD · PATH | 인증 |
|------|------|------|
| Execute Webhook | `POST /webhooks/{webhook.id}/{webhook.token}` | 없음 (Webhook URL이 시크릿) |
| Edit Webhook Message | `PATCH /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}` | 없음 |
| Delete Webhook Message | `DELETE /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}` | 없음 |
| Create Message | `POST /channels/{channel.id}/messages` | `Authorization: Bot <token>` |
| Get Channel Messages | `GET /channels/{channel.id}/messages?limit=N` | `Authorization: Bot <token>` |

Base(Bot 토큰 경로): `https://discord.com/api/v10` (v10은 현행 "Available" 버전) ·
Webhook 경로: 전체 Webhook URL을 `DISCORD_WEBHOOK_URL`로 통째로 받는다(id/token이 URL path에 포함).

## 인증 (두 경로)
- **Webhook**: 인증 헤더가 없다. Webhook URL 자체가 시크릿이다. `discord_send_message` /
  `discord_send_embed` / `discord_edit_message` / `discord_delete_message`가 이 경로를 쓴다.
- **Bot 토큰**: `Authorization: Bot <token>` 헤더(Bearer 아님)를 직접 주입한다.
  `discord_create_message` / `discord_list_messages`가 이 경로를 쓴다.

## 셋업
**Webhook 경로**
1. Discord 채널 → **설정 → 연동(Integrations) → 웹후크(Webhooks)**에서 웹후크 생성
2. **웹후크 URL 복사**
3. `.env`에 `DISCORD_WEBHOOK_URL=...` 작성 (인터랙티브 인증 단계 없음)

**Bot 토큰 경로(선택)**
1. [Discord 개발자 포털](https://discord.com/developers/applications)에서 애플리케이션·봇 생성
2. **봇 토큰 발급** 후 대상 길드에 초대(채널 View/Send 권한 부여)
3. `.env`에 `DISCORD_BOT_TOKEN=...` 작성

> 이 서비스는 OAuth가 아니므로 `arcsolve-mcp auth discord`가 없다.
> Webhook 경로는 URL만, Bot 경로는 토큰만 있으면 동작한다.
> `DISCORD_BOT_TOKEN` 미설정 시 Bot 도구는 친절한 설정 안내를 반환한다.

## 도구
| 도구 | 경로 | 설명 |
|------|------|------|
| `discord_send_message(content, username?, avatar_url?, tts?)` | Webhook | 채널에 텍스트 전송(≤2000자) |
| `discord_send_embed(title?, description?, url?, color?, footer?)` | Webhook | 리치 임베드 1개 전송(필드 ≥1 필수) |
| `discord_edit_message(message_id, content?)` | Webhook | Webhook 메시지 본문 편집 |
| `discord_delete_message(message_id)` | Webhook | Webhook 메시지 삭제(성공 204) |
| `discord_create_message(channel_id, content)` | Bot | 임의 채널에 텍스트 전송(≤2000자) |
| `discord_list_messages(channel_id, limit?)` | Bot | 채널 최근 메시지 조회(limit 1–100, 기본 50) |

## 범위 / 제약
- `content`는 최대 **2000자**(공식 제약, Webhook·Create Message 공통). Nitro 적용 시 4000자지만
  본 서비스는 표준 2000자 상한을 강제한다.
- `embeds`는 메시지당 **최대 10개**(공식 제약). 본 서비스 `discord_send_embed`는 임베드 1개를 보낸다.
  Webhook 임베드는 `type`/`provider`/`video`, 이미지 `height`/`width`/`proxy_url`을 설정할 수 없다(공식).
- `color`는 **RGB 정수**(예: 빨강 `16711680`). `footer`는 텍스트 문자열 1개로 단순화했다.
- 임베드/편집은 표시할 필드가 최소 하나 있어야 한다(없으면 입력 오류 안내).
- 메시지 전송/임베드는 `?wait=true`로 호출해 생성된 Message 오브젝트(특히 `id`)를 받는다
  (기본 `wait=false`는 `204 No Content`). 이 `id`로 편집·삭제가 가능하다.
- 편집·삭제는 **동일 Webhook이 보낸 메시지**에만 적용된다.
- `discord_list_messages`의 `limit`은 **1–100**(공식 제약), 범위를 벗어나면 입력 오류 안내.

## 확장 포인트
- `allowed_mentions` / `components` / `attachments`(파일 업로드, multipart): `contract.py`에 모델 추가 →
  `tools.py`에 인자 노출. 파일 업로드는 `multipart/form-data`가 필요해 코어 HTTP 확장이 선행돼야 한다.
- 임베드의 `fields`/`author`/`image`/`thumbnail` 등 더 풍부한 하위 모델: `Embed`에 필드 추가.
- Bot 토큰 경로의 메시지 편집/삭제(`PATCH`/`DELETE /channels/{channel.id}/messages/{message.id}`):
  필요 시 별도 도구로 추가.
