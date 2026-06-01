"""Telegram Bot API 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트, 인증 요건, 요청/응답 스키마.
MCP에 대한 의존성 없음(순수 상수 + pydantic 모델).

출처(공식 문서):
  - Bot API 레퍼런스        : https://core.telegram.org/bots/api
  - sendMessage 메서드      : https://core.telegram.org/bots/api#sendmessage
  - getMe 메서드            : https://core.telegram.org/bots/api#getme
  - sendPhoto 메서드        : https://core.telegram.org/bots/api#sendphoto
  - sendDocument 메서드     : https://core.telegram.org/bots/api#senddocument
  - editMessageText 메서드  : https://core.telegram.org/bots/api#editmessagetext
  - deleteMessage 메서드    : https://core.telegram.org/bots/api#deletemessage
  - 요청/응답 포맷(Making requests): https://core.telegram.org/bots/api#making-requests
  - LinkPreviewOptions 오브젝트 : https://core.telegram.org/bots/api#linkpreviewoptions
  - User 오브젝트            : https://core.telegram.org/bots/api#user
  - Message 오브젝트         : https://core.telegram.org/bots/api#message
  - LinkPreviewOptions 도입(7.0): https://core.telegram.org/bots/api-changelog
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

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


# 메서드 이름 상수
SEND_MESSAGE = "sendMessage"           # https://core.telegram.org/bots/api#sendmessage
GET_ME = "getMe"                       # https://core.telegram.org/bots/api#getme
SEND_PHOTO = "sendPhoto"               # https://core.telegram.org/bots/api#sendphoto
SEND_DOCUMENT = "sendDocument"         # https://core.telegram.org/bots/api#senddocument
EDIT_MESSAGE_TEXT = "editMessageText"  # https://core.telegram.org/bots/api#editmessagetext
DELETE_MESSAGE = "deleteMessage"       # https://core.telegram.org/bots/api#deletemessage

# parse_mode 허용값 (출처: https://core.telegram.org/bots/api#formatting-options)
PARSE_MODES = ("MarkdownV2", "HTML")  # "Markdown"은 legacy로도 존재하나 MVP는 권장 2종만 노출

# caption 길이 제약 (출처: sendPhoto/sendDocument 공식 표 "0-1024 characters")
CAPTION_MAX_LENGTH = 1024
# text 길이 제약 (출처: sendMessage/editMessageText 공식 표 "1-4096 characters")
TEXT_MAX_LENGTH = 4096

# multipart/form-data 업로드 크기 한도.
# 공식 "Sending files": "post the file using multipart/form-data ... 10 MB max for photos,
# 50 MB for other files." (HTTP URL 전송 시엔 5MB/20MB로 더 작다.)
# 출처: https://core.telegram.org/bots/api#sending-files
PHOTO_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
FILE_UPLOAD_MAX_BYTES = 50 * 1024 * 1024
# 참고: 입력이 로컬 파일인지(→ multipart) URL/file_id인지(→ JSON) 판별하는 것은 런타임
# 동작이므로 tools.py(is_local_file)에 둔다. contract.py는 순수 상수·모델만 담는다.


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
    text: str = Field(min_length=1, max_length=TEXT_MAX_LENGTH)
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

    # provenance(검증 완료): sendMessage의 required 필드는 chat_id, text 둘뿐이며 나머지는 전부
    # Optional임을 공식 스펙(Bot API 10.0)으로 행 단위 확인했다. 위 필드 이름·타입·필수성·제약
    # (text 1..4096, parse_mode 값, link_preview_options)이 공식과 일치한다. 그 외 선택 필드
    # (entities, reply_parameters, reply_markup, message_effect_id 등)는 MVP 범위 밖이라 의도적으로 생략.


class SendPhoto(BaseModel):
    """sendPhoto 요청 본문.

    공식 표의 필수 필드는 chat_id, photo이며 나머지는 선택.
    `photo`는 InputFile 또는 String이며, String일 때 **file_id 또는 HTTP URL**을 의미한다
    ("Pass a file_id ... Pass an HTTP URL ... or upload a new photo").
    이 **JSON 경로용 모델**은 photo가 문자열(URL/file_id)인 경우만 다룬다. 로컬 파일
    업로드(multipart)는 tools.py가 `post_multipart`로 별도 처리한다(이 모델을 쓰지 않음).
    출처: https://core.telegram.org/bots/api#sendphoto
    """

    chat_id: int | str
    # photo: URL 또는 file_id 문자열(로컬 파일은 tools.py의 multipart 경로에서 처리).
    photo: str = Field(min_length=1)
    # 선택: 캡션. "0-1024 characters after entities parsing."
    caption: str | None = Field(default=None, max_length=CAPTION_MAX_LENGTH)
    parse_mode: Literal["MarkdownV2", "HTML"] | None = None
    disable_notification: bool | None = None
    protect_content: bool | None = None

    # provenance(검증 완료): sendPhoto의 required는 chat_id, photo 둘뿐, caption은 0-1024자.
    # (caption_entities/show_caption_above_media/reply_parameters/reply_markup 등은 MVP 범위 밖 생략.)


class SendDocument(BaseModel):
    """sendDocument 요청 본문.

    필수 필드는 chat_id, document. `document`는 sendPhoto의 photo와 동일하게
    String일 때 file_id 또는 HTTP URL을 의미한다. 이 **JSON 경로용 모델**은 문자열만 다루며,
    로컬 파일 업로드(multipart)는 tools.py가 `post_multipart`로 처리한다.
    출처: https://core.telegram.org/bots/api#senddocument
    """

    chat_id: int | str
    # document: URL 또는 file_id 문자열(로컬 파일은 tools.py의 multipart 경로에서 처리).
    document: str = Field(min_length=1)
    # 선택: 캡션. "0-1024 characters after entities parsing."(sendPhoto와 동일 제약)
    caption: str | None = Field(default=None, max_length=CAPTION_MAX_LENGTH)
    parse_mode: Literal["MarkdownV2", "HTML"] | None = None
    disable_notification: bool | None = None
    protect_content: bool | None = None

    # provenance(검증 완료): sendDocument의 required는 chat_id, document, caption은 0-1024자.


class EditMessageText(BaseModel):
    """editMessageText 요청 본문.

    공식 필수성(조건부·상호 배타): chat_id+message_id는 inline_message_id가 없을 때 필수이고,
    inline_message_id는 chat_id/message_id가 없을 때 필수다. text는 항상 필수("1-4096 characters").
    성공 시 편집된 Message(또는 인라인 메시지의 경우 True)를 반환한다.
    출처: https://core.telegram.org/bots/api#editmessagetext
    """

    # 조건부 필수: (chat_id+message_id) 또는 inline_message_id 중 정확히 한 경로(아래 validator).
    chat_id: int | str | None = None
    message_id: int | None = None
    inline_message_id: str | None = None
    # 필수: 새 본문. "1-4096 characters after entities parsing."(sendMessage와 동일)
    text: str = Field(min_length=1, max_length=TEXT_MAX_LENGTH)
    parse_mode: Literal["MarkdownV2", "HTML"] | None = None
    link_preview_options: LinkPreviewOptions | None = None

    @model_validator(mode="after")
    def _require_one_target(self) -> EditMessageText:
        """공식의 조건부 필수성을 강제한다: 두 경로는 상호 배타, 정확히 하나만 지정."""
        has_chat = self.chat_id is not None and self.message_id is not None
        has_inline = self.inline_message_id is not None
        if has_inline and (self.chat_id is not None or self.message_id is not None):
            raise ValueError("inline_message_id와 chat_id/message_id는 함께 쓸 수 없습니다.")
        if not has_chat and not has_inline:
            raise ValueError("chat_id+message_id 또는 inline_message_id 중 하나가 필요합니다.")
        return self

    # provenance(검증 완료): chat_id/message_id/inline_message_id의 조건부·상호배타 필수성을
    # 공식대로 모델링(text 1-4096, parse_mode/link_preview_options는 Optional).
    # entities/reply_markup은 MVP 범위 밖 의도적 생략.


class DeleteMessage(BaseModel):
    """deleteMessage 요청 본문.

    공식: chat_id, message_id 모두 필수. "Returns True on success."
    출처: https://core.telegram.org/bots/api#deletemessage
    """

    chat_id: int | str
    message_id: int


class User(BaseModel):
    """getMe 결과 및 Message.from 등에 쓰이는 사용자 오브젝트(부분).

    getMe는 봇 자신을 나타내는 User를 반환한다("Returns basic information about the bot
    in form of a User object."). id/is_bot/first_name은 항상 존재, username 등은 선택.
    상류가 추가 필드(can_join_groups 등)를 보내므로 extra는 무시.
    출처: https://core.telegram.org/bots/api#user · https://core.telegram.org/bots/api#getme
    """

    model_config = {"extra": "ignore"}

    id: int
    is_bot: bool
    first_name: str
    last_name: str | None = None
    username: str | None = None


class Chat(BaseModel):
    """Message.chat 오브젝트(부분).

    출처: https://core.telegram.org/bots/api#chat
    """

    id: int
    type: str


class PhotoSize(BaseModel):
    """Message.photo 배열의 원소(부분). 사진 1장은 여러 해상도의 PhotoSize 배열로 온다.

    출처: https://core.telegram.org/bots/api#photosize
    """

    model_config = {"extra": "ignore"}

    file_id: str          # 이 파일을 내려받거나 재사용할 식별자
    file_unique_id: str   # 시간/봇 불변 고유 식별자(다운로드/재사용 불가)
    width: int
    height: int


class Document(BaseModel):
    """Message.document 오브젝트(부분).

    출처: https://core.telegram.org/bots/api#document
    """

    model_config = {"extra": "ignore"}

    file_id: str
    file_unique_id: str
    file_name: str | None = None
    mime_type: str | None = None


class Message(BaseModel):
    """send*/editMessageText 성공 시 반환되는 Message 오브젝트(MVP 부분 모델).

    공식: "On success, the sent Message is returned." 필수 필드는 message_id, date, chat.
    sendPhoto/sendDocument는 각각 photo/document·caption을, editMessageText는 편집된 본문을 채운다.
    상류가 추가 필드를 더 보내므로 extra는 무시(검증 실패 방지).
    출처: https://core.telegram.org/bots/api#message
    """

    model_config = {"extra": "ignore"}

    message_id: int            # 채팅 내 고유 메시지 식별자
    date: int                  # 전송 시각(Unix time)
    chat: Chat                 # 메시지가 속한 채팅
    text: str | None = None
    caption: str | None = None             # 사진/문서 캡션
    photo: list[PhotoSize] | None = None   # 사진 메시지의 사이즈 배열
    document: Document | None = None        # 문서 메시지


class ApiResponse(BaseModel):
    """Telegram Bot API 공통 응답 봉투.

    공식: "The response contains a JSON object, which always has a Boolean field 'ok'.
    If 'ok' equals True, ... the result ... in the 'result' field. ... 'ok' equals false
    and the error is explained in the 'description'. An Integer 'error_code' field is also
    returned." 출처: https://core.telegram.org/bots/api#making-requests
    """

    ok: bool
    # result는 메서드에 따라 오브젝트(dict)이거나 Boolean이다. 예: deleteMessage는 True,
    # editMessageText는 편집된 Message(dict) 또는 인라인 메시지의 경우 True를 반환한다.
    # (출처: #deletemessage "Returns True on success." · #editmessagetext "Message ... or True")
    result: dict | bool | None = None
    error_code: int | None = None
    description: str | None = None
