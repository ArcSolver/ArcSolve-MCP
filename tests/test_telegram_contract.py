"""Telegram 계약 검증 — 네트워크 없이 contract.py만 테스트."""

import json

import pytest
from pydantic import ValidationError

from arcsolve.services.telegram.contract import (
    BASE_URL,
    PARSE_MODES,
    SEND_MESSAGE,
    ApiResponse,
    LinkPreviewOptions,
    Message,
    SendMessage,
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


def test_contract_constants():
    assert BASE_URL == "https://api.telegram.org"
    assert SEND_MESSAGE == "sendMessage"
    assert PARSE_MODES == ("MarkdownV2", "HTML")
