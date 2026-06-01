# Discord 서비스

Discord **Webhook**으로 채널에 메시지를 전송하는 래퍼.

## 계약 출처 (공식 문서)
- Execute Webhook: https://discord.com/developers/docs/resources/webhook#execute-webhook
- Message Object: https://discord.com/developers/docs/resources/message#message-object
> (위 URL은 `https://docs.discord.com/developers/...`로 301 리다이렉트된다.)
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트·요청/응답 모델).

## 엔드포인트
| 종류 | METHOD · PATH |
|------|------|
| Execute Webhook | `POST /webhooks/{webhook.id}/{webhook.token}` |

Base: 전체 Webhook URL을 `DISCORD_WEBHOOK_URL`로 통째로 받는다(id/token이 URL path에 포함) ·
인증: **없음** (Webhook URL 자체가 시크릿) · 스코프: 해당 없음

## 셋업
1. Discord 채널 → **설정 → 연동(Integrations) → 웹후크(Webhooks)**에서 웹후크 생성
2. **웹후크 URL 복사**
3. `.env`에 `DISCORD_WEBHOOK_URL=...` 작성 (인터랙티브 인증 단계 없음)

> 이 서비스는 OAuth가 아니므로 `arcsolve-mcp auth discord`가 없다. URL만 있으면 동작한다.

## 도구
| 도구 | 설명 |
|------|------|
| `discord_send_message(content, username?, avatar_url?, tts?)` | 채널에 메시지 전송(≤2000자) |

## 범위 / 제약
- MVP는 **Webhook 실행(메시지 전송)만**. Webhook은 인증이 없어 가장 단순하다.
- `content`는 최대 **2000자**(공식 제약). 공식 문서상 `content`/`embeds`/`components`/`file`/`poll`
  중 하나는 필수이며, 본 MVP는 `content`만 노출하므로 `content`를 필수로 둔다.
- 도구는 `?wait=true`로 호출해 서버 확인 + 생성된 Message 오브젝트를 받는다(기본 `wait=false`는
  `204 No Content`).

## 확장 포인트
- `embeds`(임베드 카드, 최대 10개) / `allowed_mentions` / `components` 필드: `contract.py`의
  `ExecuteWebhookRequest`에 추가 → `tools.py`에 인자 노출.
- Bot 토큰 경로 [create-message](https://discord.com/developers/docs/resources/message#create-message)
  (`Authorization: Bot <token>` 헤더 사용): 임의 채널 전송이 필요하면 별도 도구로 추가.
