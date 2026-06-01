"""LINE Messaging API 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트, 인증 요건, 요청/응답 스키마.
MCP에 대한 의존성 없음(순수 상수 + pydantic 모델).

출처(공식 문서):
  - Messaging API 레퍼런스 : https://developers.line.biz/en/reference/messaging-api/
  - Send push message      : https://developers.line.biz/en/reference/messaging-api/#send-push-message
  - Text message object    : https://developers.line.biz/en/reference/messaging-api/#text-message
  - Channel access token   : https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/
  - 텍스트 문자수 카운팅    : https://developers.line.biz/en/docs/messaging-api/text-character-count/
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ─── 인증 ───────────────────────────────────────────────────
# 채널 액세스 토큰을 Bearer 헤더로 전달한다. 인터랙티브 OAuth(authcode)가 아니므로
# AUTHORIZE_URL / TOKEN_URL / SCOPES 는 없다(콘솔에서 발급한 토큰을 env로 받는다).
# 출처: https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/

# ─── 메시지 API ─────────────────────────────────────────────
# 출처: https://developers.line.biz/en/reference/messaging-api/#send-push-message
BASE_URL = "https://api.line.me"
PUSH_MESSAGE = "/v2/bot/message/push"  # POST · Content-Type: application/json

# 문서 명시 제약(출처: 위 push message / text message 섹션)
MAX_MESSAGES = 5      # messages 배열은 최대 5개
MAX_TEXT_LENGTH = 5000  # text 필드 최대 5000자(UTF-16 코드 유닛 기준)


class TextMessage(BaseModel):
    """텍스트 메시지 오브젝트.

    공식 필드: type("text" 고정) · text(필수, ≤5000자). emojis/quoteToken 등
    선택 필드는 MVP에서 모델링하지 않는다(아래 동일 패턴으로 확장 가능).
    출처: https://developers.line.biz/en/reference/messaging-api/#text-message
    """

    type: Literal["text"] = "text"
    text: str = Field(max_length=MAX_TEXT_LENGTH)


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


class PushResult(BaseModel):
    """push message 응답.

    성공 시 HTTP 200 + 본문은 빈 객체 `{}`이다(sentMessages는 멀티캐스트/브로드캐스트 등
    일부 엔드포인트에서만 제공되며 push에는 없다). 실패는 코어 http가 UpstreamError로 매핑.
    출처: https://developers.line.biz/en/reference/messaging-api/#send-push-message
    """

    # push는 빈 객체를 반환하므로 모든 필드 선택. extra는 무시(상류 추가 필드 대비).


class ErrorResponse(BaseModel):
    """Messaging API 표준 에러 응답.

    공식 형식: message(요약) · details[](선택, 각 항목 message/property).
    출처: https://developers.line.biz/en/reference/messaging-api/#error-responses
    """

    message: str | None = None
    details: list[dict] | None = None
