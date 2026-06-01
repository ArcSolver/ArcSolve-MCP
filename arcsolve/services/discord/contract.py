"""Discord Webhook REST API 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트, 인증 요건, 요청/응답 스키마.
MCP에 대한 의존성 없음(순수 상수 + pydantic 모델).

출처(공식 문서):
  - Execute Webhook : https://discord.com/developers/docs/resources/webhook#execute-webhook
  - Message Object  : https://discord.com/developers/docs/resources/message#message-object
  (위 URL은 https://docs.discord.com/developers/... 로 301 리다이렉트된다.)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── 인증 ───────────────────────────────────────────────────
# Execute Webhook은 "does not require authentication."
# Webhook URL 자체가 시크릿(URL path의 {webhook.token})이라 별도 인증 헤더가 없다.
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook

# ─── 엔드포인트 ──────────────────────────────────────────────
# Execute Webhook: POST /webhooks/{webhook.id}/{webhook.token}
# 단, 이 서비스는 전체 Webhook URL을 env(DISCORD_WEBHOOK_URL)로 통째로 받으므로
# BASE_URL/PATH 조합 대신 URL을 그대로 사용한다. (URL에 id/token이 이미 포함)
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook
EXECUTE_WEBHOOK_ROUTE = "/webhooks/{webhook_id}/{webhook_token}"

# 쿼리 파라미터 `wait`(boolean, 기본 false):
#   "waits for server confirmation of message send before response,
#    and returns the created message body"
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook-query-string-params
WAIT_PARAM = "wait"

# content 길이 제한: "the message contents (up to 2000 characters)"
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params
CONTENT_MAX_LENGTH = 2000


class ExecuteWebhookRequest(BaseModel):
    """Execute Webhook 요청 body (JSON/form params).

    공식 제약: "you must provide a value for at least one of content, embeds,
    components, file, or poll." 본 MVP는 content만 모델링하므로 content는 필수로 둔다.
    선택 필드(username/avatar_url/tts)는 문서의 JSON params 표에 실재한다.

    출처: https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params
    """

    # content: string · "the message contents (up to 2000 characters)"
    content: str = Field(max_length=CONTENT_MAX_LENGTH)
    # username: string (false) · "override the default username of the webhook"
    username: str | None = None
    # avatar_url: string (false) · "override the default avatar of the webhook"
    avatar_url: str | None = None
    # tts: boolean (false) · "true if this is a TTS message"
    tts: bool | None = None


class MessageResult(BaseModel):
    """`?wait=true`일 때 반환되는 Message 오브젝트(부분).

    Execute Webhook은 기본(wait=false) 시 204 No Content를 반환하고,
    wait=true일 때 생성된 Message 오브젝트를 반환한다.
    여기서는 도구가 확인용으로 읽는 최소 필드만 모델링한다.

    출처(필드 타입):
      - Execute Webhook 응답: https://discord.com/developers/docs/resources/webhook#execute-webhook
      - Message Structure   : https://discord.com/developers/docs/resources/message#message-object-message-structure
    """

    id: str | None = None          # snowflake
    channel_id: str | None = None  # snowflake
    content: str | None = None     # string
