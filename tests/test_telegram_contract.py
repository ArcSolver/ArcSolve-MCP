"""Telegram 계약 검증 — 네트워크 없이 contract.py(+업로드 헬퍼)만 테스트."""

import json

import pytest
from pydantic import ValidationError

from arcsolve.services.telegram.contract import (
    BASE_URL,
    CAPTION_MAX_LENGTH,
    DELETE_MESSAGE,
    EDIT_MESSAGE_TEXT,
    FILE_UPLOAD_MAX_BYTES,
    GET_ME,
    PARSE_MODES,
    PHOTO_UPLOAD_MAX_BYTES,
    SEND_DOCUMENT,
    SEND_MESSAGE,
    SEND_PHOTO,
    TEXT_MAX_LENGTH,
    ApiResponse,
    DeleteMessage,
    Document,
    EditMessageText,
    LinkPreviewOptions,
    Message,
    PhotoSize,
    SendDocument,
    SendMessage,
    SendPhoto,
    User,
    method_path,
)


def test_send_message_serialization():
    m = SendMessage(chat_id=123, text="안녕", parse_mode="HTML")
    payload = json.loads(m.model_dump_json(exclude_none=True))
    assert payload["chat_id"] == 123
    assert payload["text"] == "안녕"
    assert payload["parse_mode"] == "HTML"
    # 미설정 선택 필드는 페이로드에서 제외되어야 함
    assert "link_preview_options" not in payload
    assert "disable_notification" not in payload


def test_chat_id_accepts_string_username():
    m = SendMessage(chat_id="@channelusername", text="hi")
    assert m.chat_id == "@channelusername"


def test_text_min_length_enforced():
    with pytest.raises(ValidationError):
        SendMessage(chat_id=1, text="")  # 0자는 거부 (1-4096)


def test_text_max_length_enforced():
    SendMessage(chat_id=1, text="가" * 4096)  # 4096자는 허용
    with pytest.raises(ValidationError):
        SendMessage(chat_id=1, text="가" * 4097)  # 4097자는 거부


def test_parse_mode_enum_enforced():
    with pytest.raises(ValidationError):
        SendMessage(chat_id=1, text="x", parse_mode="bogus")
    for mode in PARSE_MODES:
        SendMessage(chat_id=1, text="x", parse_mode=mode)


def test_link_preview_options_disabled():
    m = SendMessage(chat_id=1, text="x", link_preview_options=LinkPreviewOptions(is_disabled=True))
    payload = json.loads(m.model_dump_json(exclude_none=True))
    assert payload["link_preview_options"] == {"is_disabled": True}


def test_method_path_puts_token_in_url():
    # 토큰은 Bearer 헤더가 아니라 URL 경로에 들어간다.
    assert method_path("TOKEN", SEND_MESSAGE) == "/botTOKEN/sendMessage"
    assert (BASE_URL + method_path("T", SEND_MESSAGE)) == "https://api.telegram.org/botT/sendMessage"


def test_api_response_success_and_error():
    ok = ApiResponse.model_validate(
        {"ok": True, "result": {"message_id": 42, "date": 1, "chat": {"id": 1, "type": "private"}}}
    )
    assert ok.ok is True
    msg = Message.model_validate(ok.result)
    assert msg.message_id == 42

    err = ApiResponse.model_validate({"ok": False, "error_code": 400, "description": "Bad Request"})
    assert err.ok is False
    assert err.error_code == 400
    assert err.description == "Bad Request"


def test_message_ignores_extra_fields():
    # 상류가 보내는 추가 필드는 무시되어야 한다(검증 실패 방지).
    msg = Message.model_validate(
        {"message_id": 7, "date": 1, "chat": {"id": 1, "type": "private"}, "from": {"id": 9}}
    )
    assert msg.message_id == 7


def test_upload_size_constants():
    assert PHOTO_UPLOAD_MAX_BYTES == 10 * 1024 * 1024  # 공식 multipart 사진 한도 10MB
    assert FILE_UPLOAD_MAX_BYTES == 50 * 1024 * 1024  # 공식 multipart 파일 한도 50MB


def test_contract_constants():
    assert BASE_URL == "https://api.telegram.org"
    assert SEND_MESSAGE == "sendMessage"
    assert PARSE_MODES == ("MarkdownV2", "HTML")
    # 확장 메서드 상수 (공식 메서드 이름과 정확히 일치)
    assert GET_ME == "getMe"
    assert SEND_PHOTO == "sendPhoto"
    assert SEND_DOCUMENT == "sendDocument"
    assert EDIT_MESSAGE_TEXT == "editMessageText"
    assert DELETE_MESSAGE == "deleteMessage"
    # 길이 제약 상수 (공식: caption 0-1024, text 1-4096)
    assert CAPTION_MAX_LENGTH == 1024
    assert TEXT_MAX_LENGTH == 4096


# ─── getMe / User ───────────────────────────────────────────


def test_user_parses_getme_result_and_ignores_extra():
    # getMe는 봇의 User를 반환하며 상류 추가 필드(can_join_groups 등)는 무시되어야 한다.
    u = User.model_validate(
        {
            "id": 7,
            "is_bot": True,
            "first_name": "MyBot",
            "username": "my_bot",
            "can_join_groups": True,
        }
    )
    assert u.id == 7
    assert u.is_bot is True
    assert u.username == "my_bot"


def test_user_optional_fields_default_none():
    u = User.model_validate({"id": 1, "is_bot": True, "first_name": "Bot"})
    assert u.last_name is None
    assert u.username is None


# ─── sendPhoto / sendDocument ───────────────────────────────


def test_send_photo_serialization_and_target():
    m = SendPhoto(chat_id="@chan", photo="https://example.com/a.jpg", caption="cap")
    payload = json.loads(m.model_dump_json(exclude_none=True))
    assert payload == {"chat_id": "@chan", "photo": "https://example.com/a.jpg", "caption": "cap"}


def test_send_photo_accepts_file_id_string():
    m = SendPhoto(chat_id=1, photo="AgACAgID-file_id")
    assert m.photo == "AgACAgID-file_id"


def test_send_photo_empty_source_rejected():
    with pytest.raises(ValidationError):
        SendPhoto(chat_id=1, photo="")  # URL/file_id 문자열은 비어 있으면 안 됨


def test_caption_max_length_enforced_photo():
    SendPhoto(chat_id=1, photo="u", caption="가" * CAPTION_MAX_LENGTH)  # 1024자 허용
    with pytest.raises(ValidationError):
        SendPhoto(chat_id=1, photo="u", caption="가" * (CAPTION_MAX_LENGTH + 1))  # 1025자 거부


def test_send_document_serialization_and_caption_limit():
    m = SendDocument(chat_id=1, document="https://example.com/f.pdf", parse_mode="HTML")
    payload = json.loads(m.model_dump_json(exclude_none=True))
    assert payload["document"] == "https://example.com/f.pdf"
    assert payload["parse_mode"] == "HTML"
    SendDocument(chat_id=1, document="d", caption="x" * CAPTION_MAX_LENGTH)
    with pytest.raises(ValidationError):
        SendDocument(chat_id=1, document="d", caption="x" * (CAPTION_MAX_LENGTH + 1))


def test_send_photo_parse_mode_enum_enforced():
    with pytest.raises(ValidationError):
        SendPhoto(chat_id=1, photo="u", parse_mode="bogus")


# ─── editMessageText ────────────────────────────────────────


def test_edit_message_text_serialization():
    m = EditMessageText(chat_id="@chan", message_id=42, text="new", parse_mode="MarkdownV2")
    payload = json.loads(m.model_dump_json(exclude_none=True))
    assert payload == {
        "chat_id": "@chan",
        "message_id": 42,
        "text": "new",
        "parse_mode": "MarkdownV2",
    }


def test_edit_message_text_length_enforced():
    EditMessageText(chat_id=1, message_id=1, text="가" * TEXT_MAX_LENGTH)  # 4096자 허용
    with pytest.raises(ValidationError):
        EditMessageText(chat_id=1, message_id=1, text="")  # 0자 거부
    with pytest.raises(ValidationError):
        EditMessageText(chat_id=1, message_id=1, text="가" * (TEXT_MAX_LENGTH + 1))  # 4097자 거부


def test_edit_message_text_inline_path_ok():
    # inline_message_id 경로(공식 조건부 필수의 다른 한쪽)
    m = EditMessageText(inline_message_id="abc123", text="new")
    payload = json.loads(m.model_dump_json(exclude_none=True))
    assert payload == {"inline_message_id": "abc123", "text": "new"}


def test_edit_message_text_requires_a_target():
    # 두 경로 모두 없으면 거부(공식: 조건부 필수)
    with pytest.raises(ValidationError):
        EditMessageText(text="new")
    # chat_id만 있고 message_id 없으면 chat 경로 미완성 → 거부
    with pytest.raises(ValidationError):
        EditMessageText(chat_id=1, text="new")


def test_edit_message_text_paths_mutually_exclusive():
    # 두 경로를 함께 주면 거부(공식: 상호 배타)
    with pytest.raises(ValidationError):
        EditMessageText(chat_id=1, message_id=2, inline_message_id="x", text="new")


# ─── deleteMessage ──────────────────────────────────────────


def test_delete_message_serialization():
    m = DeleteMessage(chat_id=123, message_id=7)
    payload = json.loads(m.model_dump_json(exclude_none=True))
    assert payload == {"chat_id": 123, "message_id": 7}


def test_delete_message_requires_message_id():
    with pytest.raises(ValidationError):
        DeleteMessage(chat_id=1)  # message_id 누락


# ─── 응답 봉투: Boolean result ──────────────────────────────


def test_api_response_accepts_boolean_result():
    # deleteMessage는 result=True를, editMessageText는 인라인 시 True를 반환한다.
    resp = ApiResponse.model_validate({"ok": True, "result": True})
    assert resp.ok is True
    assert resp.result is True


def test_message_parses_photo_and_caption():
    # sendPhoto 성공 응답: photo는 PhotoSize 배열, caption 포함.
    msg = Message.model_validate(
        {
            "message_id": 5,
            "date": 1,
            "chat": {"id": 1, "type": "private"},
            "caption": "hi",
            "photo": [
                {"file_id": "fid", "file_unique_id": "u", "width": 90, "height": 90},
            ],
        }
    )
    assert msg.caption == "hi"
    assert msg.photo is not None
    assert msg.photo[0].width == 90


def test_message_parses_document():
    msg = Message.model_validate(
        {
            "message_id": 6,
            "date": 1,
            "chat": {"id": 1, "type": "private"},
            "document": {"file_id": "fid", "file_unique_id": "u", "file_name": "f.pdf"},
        }
    )
    assert msg.document is not None
    assert msg.document.file_name == "f.pdf"


def test_photosize_and_document_ignore_extra():
    ps = PhotoSize.model_validate(
        {"file_id": "a", "file_unique_id": "b", "width": 1, "height": 1, "file_size": 999}
    )
    assert ps.file_id == "a"
    doc = Document.model_validate({"file_id": "a", "file_unique_id": "b", "mime_type": "x/y"})
    assert doc.mime_type == "x/y"
