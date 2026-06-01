"""Telegram Bot API 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트, 인증 요건, 요청/응답 스키마.
MCP에 대한 의존성 없음(순수 상수 + pydantic 모델).

출처(공식 문서):
  - Bot API 레퍼런스        : https://core.telegram.org/bots/api
  - sendMessage 메서드      : https://core.telegram.org/bots/api#sendmessage
  - 요청/응답 포맷(Making requests): https://core.telegram.org/bots/api#making-requests
  - LinkPreviewOptions 오브젝트 : https://core.telegram.org/bots/api#linkpreviewoptions
  - Message 오브젝트         : https://core.telegram.org/bots/api#message
  - LinkPreviewOptions 도입(7.0): https://core.telegram.org/bots/api-changelog
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ─── 인증 / 엔드포인트 ───────────────────────────────────────
# 공식: "All queries to the Telegram Bot API must be served over HTTPS and need to
#       be presented in this form: https://api.telegram.org/bot<token>/METHOD_NAME"
#       → 봇 토큰은 Bearer 헤더가 아니라 URL 경로에 들어간다.
#       (출처: https://core.telegram.org/bots/api#making-requests)
BASE_URL = "https://api.telegram.org"


def method_path(token: str, method: str) -> str:
    """`/bot<token>/<METHOD_NAME>` 경로를 조립한다.

    출처: https://core.telegram.org/bots/api#making-requests
    """
    return f"/bot{token}/{method}"


# 메서드 이름 상수 (출처: https://core.telegram.org/bots/api#sendmessage)
SEND_MESSAGE = "sendMessage"

# parse_mode 허용값 (출처: https://core.telegram.org/bots/api#formatting-options)
PARSE_MODES = ("MarkdownV2", "HTML")  # "Markdown"은 legacy로도 존재하나 MVP는 권장 2종만 노출


class LinkPreviewOptions(BaseModel):
    """발신 메시지의 링크 미리보기 옵션.

    Bot API 7.0(2023-12-29)에서 도입되어 sendMessage의 구(舊) `disable_web_page_preview`를
    대체한다. 모든 필드는 선택.
    출처: https://core.telegram.org/bots/api#linkpreviewoptions
    """

    is_disabled: bool | None = None        # 링크 미리보기 비활성화 여부
    url: str | None = None                 # 미리보기를 생성할 URL(미지정 시 본문 첫 URL)
    prefer_small_media: bool | None = None  # 작은 미디어 선호
    prefer_large_media: bool | None = None  # 큰 미디어 선호
    show_above_text: bool | None = None     # 본문 위에 미리보기 표시


class SendMessage(BaseModel):
    """sendMessage 요청 본문.

    공식 표의 필수 필드는 chat_id, text 두 개이며, 나머지는 선택이다.
    출처: https://core.telegram.org/bots/api#sendmessage
    """

    # 필수: 대상 채팅 ID(정수) 또는 채널 username("@channelusername") 문자열.
    chat_id: int | str
    # 필수: 본문. "1-4096 characters after entities parsing."
    text: str = Field(min_length=1, max_length=4096)
    # 선택: 메시지 엔티티 파싱 모드("MarkdownV2" | "HTML" 등).
    parse_mode: Literal["MarkdownV2", "HTML"] | None = None
    # 선택: 포럼 슈퍼그룹의 특정 토픽 ID(Bot API 6.x에서 추가).
    message_thread_id: int | None = None
    # 선택: 링크 미리보기 옵션(구 disable_web_page_preview 대체).
    link_preview_options: LinkPreviewOptions | None = None
    # 선택: 알림 없이 조용히 전송.
    disable_notification: bool | None = None
    # 선택: 전달/저장 방지.
    protect_content: bool | None = None

    # TODO(provenance): chat_id/parse_mode/message_thread_id 등 개별 행의 "Optional/Required"
    # 라벨은 sendMessage 메서드 표를 직접(행 단위) 렌더해 재확인하지 못했다(공식 페이지가 매우 커
    # WebFetch markdown 변환에서 methods 섹션이 잘림). 필드의 *존재*와 chat_id/text 필수,
    # text 1..4096, parse_mode 값, link_preview_options 도입은 공식 도메인(core.telegram.org)에서
    # 교차 확인했다. 추가 선택 필드(entities, reply_parameters, reply_markup, message_effect_id 등)는
    # MVP 범위 밖이라 의도적으로 생략.


class User(BaseModel):
    """Message.from 등에 쓰이는 사용자 오브젝트(부분).

    출처: https://core.telegram.org/bots/api#user
    """

    id: int
    is_bot: bool
    first_name: str


class Chat(BaseModel):
    """Message.chat 오브젝트(부분).

    출처: https://core.telegram.org/bots/api#chat
    """

    id: int
    type: str


class Message(BaseModel):
    """sendMessage 성공 시 반환되는 Message 오브젝트(MVP 부분 모델).

    공식: "On success, the sent Message is returned." 필수 필드는 message_id, date, chat.
    상류가 추가 필드를 더 보내므로 extra는 무시(검증 실패 방지).
    출처: https://core.telegram.org/bots/api#message
    """

    model_config = {"extra": "ignore"}

    message_id: int      # 채팅 내 고유 메시지 식별자
    date: int            # 전송 시각(Unix time)
    chat: Chat           # 메시지가 속한 채팅
    text: str | None = None


class ApiResponse(BaseModel):
    """Telegram Bot API 공통 응답 봉투.

    공식: "The response contains a JSON object, which always has a Boolean field 'ok'.
    If 'ok' equals True, ... the result ... in the 'result' field. ... 'ok' equals false
    and the error is explained in the 'description'. An Integer 'error_code' field is also
    returned." 출처: https://core.telegram.org/bots/api#making-requests
    """

    ok: bool
    result: dict | None = None
    error_code: int | None = None
    description: str | None = None
