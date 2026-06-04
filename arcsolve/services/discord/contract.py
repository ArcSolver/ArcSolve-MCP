"""Discord REST API 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트, 인증 요건, 요청/응답 스키마.
MCP에 대한 의존성 없음(순수 상수 + pydantic 모델).

두 가지 인증 경로를 모델링한다:
  (A) Webhook 경로 — 인증 불필요. Webhook URL 자체가 시크릿(URL path의 {webhook.token}).
  (B) Bot 토큰 경로 — `Authorization: Bot <token>` 헤더로 임의 채널에 접근.

출처(공식 문서):
  - Execute Webhook        : https://discord.com/developers/docs/resources/webhook#execute-webhook
  - Edit Webhook Message   : https://discord.com/developers/docs/resources/webhook#edit-webhook-message
  - Delete Webhook Message : https://discord.com/developers/docs/resources/webhook#delete-webhook-message
  - Message Object / Embed : https://discord.com/developers/docs/resources/message#message-object
  - Create Message         : https://discord.com/developers/docs/resources/message#create-message
  - Get Channel Messages   : https://discord.com/developers/docs/resources/message#get-channel-messages
  - API Reference (base)   : https://discord.com/developers/docs/reference#api-reference-base-url
  (위 URL은 https://docs.discord.com/developers/... 로 301 리다이렉트된다.)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── 인증 ───────────────────────────────────────────────────
# (A) Execute/Edit/Delete Webhook은 "does not require authentication."
#     Webhook URL 자체가 시크릿(URL path의 {webhook.token})이라 별도 인증 헤더가 없다.
#     출처: https://discord.com/developers/docs/resources/webhook#execute-webhook
# (B) Bot 토큰 경로는 `Authorization: Bot <token>` 헤더를 직접 주입한다(Bearer 아님).
#     출처: https://discord.com/developers/docs/reference#authentication

# ─── API Base URL ───────────────────────────────────────────
# "Base URL: https://discord.com/api". 버전은 path에 붙인다(예: /api/v10).
# 버전 미지정 시 default는 구버전(deprecated)이므로 항상 v10을 명시한다("Available" 버전).
# 출처: https://discord.com/developers/docs/reference#api-reference-base-url
#       https://discord.com/developers/docs/reference#api-versioning-api-versions
API_BASE_URL = "https://discord.com/api/v10"

# ─── 엔드포인트 (A) Webhook 경로 ──────────────────────────────
# Execute Webhook: POST /webhooks/{webhook.id}/{webhook.token}
# 단, 이 서비스는 전체 Webhook URL을 env(DISCORD_WEBHOOK_URL)로 통째로 받으므로
# BASE_URL/PATH 조합 대신 URL을 그대로 사용한다. (URL에 id/token이 이미 포함)
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook
EXECUTE_WEBHOOK_ROUTE = "/webhooks/{webhook_id}/{webhook_token}"

# Edit Webhook Message:   PATCH  /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}
# Delete Webhook Message: DELETE /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}
# 본 서비스는 Webhook URL 뒤에 `/messages/{message_id}`를 덧붙여 경로를 파생한다.
# 출처: https://discord.com/developers/docs/resources/webhook#edit-webhook-message
#       https://discord.com/developers/docs/resources/webhook#delete-webhook-message
WEBHOOK_MESSAGE_SUFFIX = "/messages/{message_id}"

# ─── 엔드포인트 (B) Bot 토큰 경로 ─────────────────────────────
# Create Message:       POST /channels/{channel.id}/messages
# Get Channel Messages: GET  /channels/{channel.id}/messages
# 출처: https://discord.com/developers/docs/resources/message#create-message
#       https://discord.com/developers/docs/resources/message#get-channel-messages
CHANNEL_MESSAGES_ROUTE = "/channels/{channel_id}/messages"

# 쿼리 파라미터 `wait`(boolean, 기본 false):
#   "waits for server confirmation of message send before response,
#    and returns the created message body"
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook-query-string-params
WAIT_PARAM = "wait"

# content 길이 제한: "the message contents (up to 2000 characters)"
# Webhook(Execute Webhook)·Create Message 모두 동일한 2000자 상한을 따른다.
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params
CONTENT_MAX_LENGTH = 2000

# embeds 배열 상한: "array of up to 10 embed objects"
# 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params
MAX_EMBEDS = 10

# Get Channel Messages `limit` 쿼리 파라미터: "max number of messages to return (1-100)",
# 기본값 50.
# 출처: https://discord.com/developers/docs/resources/message#get-channel-messages-query-string-params
MESSAGES_LIMIT_MIN = 1
MESSAGES_LIMIT_MAX = 100
MESSAGES_LIMIT_DEFAULT = 50


class EmbedFooter(BaseModel):
    """Embed Footer 구조.

    필드:
      - text:     string (필수) · "footer text"
      - icon_url: string (선택) · "url of footer icon (only supports http(s) and attachments)"

    출처: https://discord.com/developers/docs/resources/message#embed-object-embed-footer-structure
    """

    text: str
    icon_url: str | None = None


class Embed(BaseModel):
    """Embed 오브젝트(부분 — 자주 쓰는 필드만 모델링).

    공식 제약: Webhook으로 보내는 embed는 type/provider/video, 이미지의 height/width/proxy_url을
    설정할 수 없다(설정해도 rich로 강제된다). 본 모델은 그 외 안전한 필드만 노출한다.

    필드:
      - title:       string  · "title of embed"
      - description: string  · "description of embed"
      - url:         string  · "url of embed"
      - color:       integer · "color code of the embed" (RGB 정수)
      - timestamp:   ISO8601 string · "timestamp of embed content"
      - footer:      embed footer object

    출처: https://discord.com/developers/docs/resources/message#embed-object-embed-structure
    """

    title: str | None = None
    description: str | None = None
    url: str | None = None
    color: int | None = None      # integer(RGB) — 공식: "color code of the embed"
    timestamp: str | None = None  # ISO8601
    footer: EmbedFooter | None = None


class ExecuteWebhookRequest(BaseModel):
    """Execute Webhook 요청 body (JSON/form params).

    공식 제약: "you must provide a value for at least one of content, embeds,
    components, file, or poll." 본 서비스는 content/embeds를 노출한다.
    선택 필드(username/avatar_url/tts)는 문서의 JSON params 표에 실재한다.

    출처: https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params
    """

    # content: string · "the message contents (up to 2000 characters)"
    # None(임베드 전용)은 허용하되, 명시적 빈 문자열("")은 차단(상류 400 사전 방지).
    content: str | None = Field(default=None, min_length=1, max_length=CONTENT_MAX_LENGTH)
    # embeds: array of up to 10 embed objects · "embedded rich content"
    embeds: list[Embed] | None = Field(default=None, max_length=MAX_EMBEDS)
    # username: string (false) · "override the default username of the webhook"
    username: str | None = None
    # avatar_url: string (false) · "override the default avatar of the webhook"
    avatar_url: str | None = None
    # tts: boolean (false) · "true if this is a TTS message"
    tts: bool | None = None


class EditWebhookMessageRequest(BaseModel):
    """Edit Webhook Message 요청 body (JSON/form params, 모두 선택).

    "All parameters to this endpoint are optional and nullable."
    본 서비스는 content/embeds만 노출한다.

    출처: https://discord.com/developers/docs/resources/webhook#edit-webhook-message-jsonform-params
    """

    # content: string · "the message contents (up to 2000 characters)"
    # None(임베드 전용)은 허용하되, 명시적 빈 문자열("")은 차단(상류 400 사전 방지).
    content: str | None = Field(default=None, min_length=1, max_length=CONTENT_MAX_LENGTH)
    # embeds: array of up to 10 embed objects · "embedded rich content"
    embeds: list[Embed] | None = Field(default=None, max_length=MAX_EMBEDS)


class CreateMessageRequest(BaseModel):
    """Create Message 요청 body (Bot 토큰 경로).

    공식 제약: "you must provide a value for at least one of content, embeds,
    sticker_ids, components, files[n], or poll." 본 서비스는 content만 노출하므로 필수로 둔다.
    content는 "up to 2000 characters"(Nitro 미적용 표준 상한)를 따른다.

    출처: https://discord.com/developers/docs/resources/message#create-message-jsonform-params
    """

    content: str = Field(min_length=1, max_length=CONTENT_MAX_LENGTH)  # 빈 본문 차단


class MessageAuthor(BaseModel):
    """Message author(User 오브젝트 부분).

    필드:
      - id:       snowflake · "the user's id"
      - username: string    · "the user's username"

    출처: https://discord.com/developers/docs/resources/user#user-object-user-structure
    """

    id: str | None = None
    username: str | None = None


class MessageResult(BaseModel):
    """Message 오브젝트(부분) — 도구가 확인용으로 읽는 최소 필드만.

    Execute Webhook은 기본(wait=false) 시 204 No Content를 반환하고,
    wait=true일 때 생성된 Message 오브젝트를 반환한다. Create Message/Edit Webhook Message는
    Message 오브젝트를 반환한다.

    출처(필드 타입):
      - Message Structure : https://discord.com/developers/docs/resources/message#message-object-message-structure
    """

    id: str | None = None          # snowflake
    channel_id: str | None = None  # snowflake
    content: str | None = None     # string
    author: MessageAuthor | None = None  # user object
