"""LINE 계약 검증 — 네트워크 없이 contract.py만 테스트."""

import json

import pytest
from pydantic import ValidationError

from arcsolve.services.line.contract import (
    BASE_URL,
    MAX_MESSAGES,
    MAX_TEXT_LENGTH,
    PUSH_MESSAGE,
    ErrorResponse,
    PushRequest,
    TextMessage,
)


def test_text_message_serialization():
    m = TextMessage(text="hello")
    payload = json.loads(m.model_dump_json())
    assert payload["type"] == "text"
    assert payload["text"] == "hello"


def test_text_max_length_enforced():
    TextMessage(text="가" * MAX_TEXT_LENGTH)  # 5000자는 허용
    with pytest.raises(ValidationError):
        TextMessage(text="가" * (MAX_TEXT_LENGTH + 1))  # 5001자는 거부


def test_push_request_serialization_omits_optional():
    req = PushRequest(to="U123", messages=[TextMessage(text="hi")])
    payload = json.loads(req.model_dump_json(exclude_none=True))
    assert payload["to"] == "U123"
    assert payload["messages"][0]["text"] == "hi"
    assert "notificationDisabled" not in payload  # None은 제외되어야 함


def test_push_request_messages_max_five_enforced():
    msgs = [TextMessage(text="m")]
    PushRequest(to="U1", messages=msgs * MAX_MESSAGES)  # 5개는 허용
    with pytest.raises(ValidationError):
        PushRequest(to="U1", messages=msgs * (MAX_MESSAGES + 1))  # 6개는 거부


def test_push_request_messages_min_one_enforced():
    with pytest.raises(ValidationError):
        PushRequest(to="U1", messages=[])  # 빈 배열 거부


def test_error_response_parsing():
    err = ErrorResponse.model_validate(
        {"message": "The request body has 1 error(s)", "details": [{"message": "x", "property": "to"}]}
    )
    assert err.message.startswith("The request body")
    assert err.details[0]["property"] == "to"


def test_contract_constants():
    assert BASE_URL == "https://api.line.me"
    assert PUSH_MESSAGE == "/v2/bot/message/push"
    assert MAX_MESSAGES == 5
    assert MAX_TEXT_LENGTH == 5000
