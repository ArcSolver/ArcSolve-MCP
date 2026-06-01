"""LINE Messaging API 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트, 인증 요건, 요청/응답 스키마.
MCP에 대한 의존성 없음(순수 상수 + pydantic 모델).

출처(공식 문서):
  - Messaging API 레퍼런스 : https://developers.line.biz/en/reference/messaging-api/
  - Send push message      : https://developers.line.biz/en/reference/messaging-api/#send-push-message
  - Send reply message     : https://developers.line.biz/en/reference/messaging-api/#send-reply-message
  - Send multicast message : https://developers.line.biz/en/reference/messaging-api/#send-multicast-message
  - Send broadcast message : https://developers.line.biz/en/reference/messaging-api/#send-broadcast-message
  - Get profile            : https://developers.line.biz/en/reference/messaging-api/#get-profile
  - Text message object    : https://developers.line.biz/en/reference/messaging-api/#text-message
  - Channel access token   : https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/
  - 텍스트 문자수 카운팅    : https://developers.line.biz/en/docs/messaging-api/text-character-count/
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ─── 인증 ───────────────────────────────────────────────────
# 채널 액세스 토큰을 Bearer 헤더로 전달한다. 인터랙티브 OAuth(authcode)가 아니므로
# AUTHORIZE_URL / TOKEN_URL / SCOPES 는 없다(콘솔에서 발급한 토큰을 env로 받는다).
# 출처: https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/

# ─── 메시지 API ─────────────────────────────────────────────
# 출처: https://developers.line.biz/en/reference/messaging-api/#send-push-message
BASE_URL = "https://api.line.me"
PUSH_MESSAGE = "/v2/bot/message/push"  # POST · Content-Type: application/json
# 출처: https://developers.line.biz/en/reference/messaging-api/#send-reply-message
REPLY_MESSAGE = "/v2/bot/message/reply"  # POST · Content-Type: application/json
# 출처: https://developers.line.biz/en/reference/messaging-api/#send-multicast-message
MULTICAST_MESSAGE = "/v2/bot/message/multicast"  # POST · Content-Type: application/json
# 출처: https://developers.line.biz/en/reference/messaging-api/#send-broadcast-message
BROADCAST_MESSAGE = "/v2/bot/message/broadcast"  # POST · Content-Type: application/json
# 출처: https://developers.line.biz/en/reference/messaging-api/#get-profile
# GET — 경로에 userId를 끼워넣는다: PROFILE.format(user_id=...)
PROFILE = "/v2/bot/profile/{user_id}"

# 문서 명시 제약(출처: 위 push message / text message 섹션)
MAX_MESSAGES = 5      # messages 배열은 최대 5개
MAX_TEXT_LENGTH = 5000  # text 필드 최대 5000자(UTF-16 코드 유닛 기준)
# multicast `to` 배열 상한(출처: send-multicast-message 요청 본문 "Max: 500 user IDs")
MAX_MULTICAST_RECIPIENTS = 500


class TextMessage(BaseModel):
    """텍스트 메시지 오브젝트.

    공식 필드: type("text" 고정) · text(필수). emojis/quoteToken 등
    선택 필드는 MVP에서 모델링하지 않는다(아래 동일 패턴으로 확장 가능).
    출처: https://developers.line.biz/en/reference/messaging-api/#text-message
    """

    type: Literal["text"] = "text"
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _within_utf16_limit(cls, v: str) -> str:
        """text 길이는 **UTF-16 코드 유닛** 기준 ≤5000.

        공식 카운팅 규칙: 길이를 UTF-16 코드 유닛으로 센다(BMP 밖 문자, 예: 이모지는 2로
        계산). pydantic의 max_length는 유니코드 코드포인트를 세므로 이모지 다수 포함 시
        과소계산되어 상류 400을 유발할 수 있다 → 정확히 UTF-16으로 검증한다.
        출처: https://developers.line.biz/en/docs/messaging-api/text-character-count/
        """
        units = len(v.encode("utf-16-le")) // 2
        if units > MAX_TEXT_LENGTH:
            raise ValueError(
                f"text는 UTF-16 코드 유닛 기준 최대 {MAX_TEXT_LENGTH}자입니다(현재 {units})."
            )
        return v


class PushRequest(BaseModel):
    """push message 요청 본문.

    공식 필드: to(필수, 수신자 userId/groupId/roomId) · messages(필수, 최대 5개) ·
    notificationDisabled(선택, true면 푸시 알림 미수신). customAggregationUnits는
    MVP에서 노출하지 않는다.
    출처: https://developers.line.biz/en/reference/messaging-api/#send-push-message
    """

    to: str
    messages: list[TextMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    notificationDisabled: bool | None = None  # noqa: N815 (공식 카멜케이스 필드명)


class SentMessage(BaseModel):
    """push 응답의 sentMessages 배열 항목.

    공식 필드: id(전송된 메시지 ID) · quoteToken(인용 토큰, 항상 제공되진 않음).
    id는 JSON에서 문자열로 직렬화된다(예: "461230966842064897").
    출처: https://developers.line.biz/en/reference/messaging-api/#send-push-message
    """

    model_config = {"extra": "ignore"}

    id: str
    quoteToken: str | None = None  # noqa: N815 (공식 카멜케이스 필드명)


class PushResult(BaseModel):
    """push message 응답.

    성공 시 HTTP 200 + 본문은 `{"sentMessages": [{"id": "...", "quoteToken": "..."}]}`.
    (이전 주석의 "빈 객체"는 오류 — 공식은 sentMessages 배열을 반환한다.)
    실패는 코어 http가 UpstreamError로 매핑.
    출처: https://developers.line.biz/en/reference/messaging-api/#send-push-message
    """

    model_config = {"extra": "ignore"}

    sentMessages: list[SentMessage] = Field(default_factory=list)  # noqa: N815 (공식 필드명)


class ReplyRequest(BaseModel):
    """reply message 요청 본문.

    공식 필드: replyToken(필수, webhook 이벤트에서 받은 일회용 토큰) ·
    messages(필수, 최대 5개) · notificationDisabled(선택). replyToken은 우리 범위 밖
    webhook 서버가 발급/전달한다(여기서는 그대로 받아 본문에 싣는다).
    출처: https://developers.line.biz/en/reference/messaging-api/#send-reply-message
    """

    replyToken: str = Field(min_length=1)  # noqa: N815 (공식 카멜케이스 필드명)
    messages: list[TextMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    notificationDisabled: bool | None = None  # noqa: N815 (공식 카멜케이스 필드명)


class MulticastRequest(BaseModel):
    """multicast message 요청 본문.

    공식 필드: to(필수, userId 배열 — 최대 500개, groupId/roomId 불가) ·
    messages(필수, 최대 5개) · notificationDisabled(선택). customAggregationUnits는
    MVP에서 노출하지 않는다.
    출처: https://developers.line.biz/en/reference/messaging-api/#send-multicast-message
    """

    to: list[str] = Field(min_length=1, max_length=MAX_MULTICAST_RECIPIENTS)
    messages: list[TextMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    notificationDisabled: bool | None = None  # noqa: N815 (공식 카멜케이스 필드명)


class BroadcastRequest(BaseModel):
    """broadcast message 요청 본문.

    공식 필드: messages(필수, 최대 5개) · notificationDisabled(선택). 수신자는
    LINE 공식 계정의 모든 친구(별도 to 없음).
    출처: https://developers.line.biz/en/reference/messaging-api/#send-broadcast-message
    """

    messages: list[TextMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    notificationDisabled: bool | None = None  # noqa: N815 (공식 카멜케이스 필드명)


class EmptyResult(BaseModel):
    """multicast/broadcast 응답.

    공식: 성공 시 HTTP 200 + **빈 JSON 객체 `{}`**(push/reply의 sentMessages와 다름).
    출처(multicast): https://developers.line.biz/en/reference/messaging-api/#send-multicast-message
    출처(broadcast): https://developers.line.biz/en/reference/messaging-api/#send-broadcast-message
    """

    model_config = {"extra": "ignore"}


class Profile(BaseModel):
    """Get profile 응답.

    공식 필드: displayName(항상) · userId(항상) · pictureUrl(선택, 프로필 이미지 없으면 미포함) ·
    statusMessage(선택, 상태 메시지 없으면 미포함) · language(선택, BCP 47 태그 — 사용자가
    개인정보 처리방침에 미동의 시 미포함). 문서상 "Not always included"로 표기된 셋만 Optional.
    출처: https://developers.line.biz/en/reference/messaging-api/#get-profile
    """

    model_config = {"extra": "ignore"}

    displayName: str  # noqa: N815 (공식 카멜케이스 필드명)
    userId: str  # noqa: N815 (공식 카멜케이스 필드명)
    pictureUrl: str | None = None  # noqa: N815 (공식 카멜케이스 필드명, "Not always included")
    statusMessage: str | None = None  # noqa: N815 (공식 카멜케이스 필드명, "Not always included")
    language: str | None = None  # ("Not always included")


class ErrorResponse(BaseModel):
    """Messaging API 표준 에러 응답.

    공식 형식: message(요약) · details[](선택, 각 항목 message/property).
    출처: https://developers.line.biz/en/reference/messaging-api/#error-responses
    """

    message: str | None = None
    details: list[dict] | None = None
