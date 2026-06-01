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
    PushResult,
    TextMessage,
)


def test_text_message_serialization():
    m = TextMessage(text="hello")
    payload = json.loads(m.model_dump_json())
    assert payload["type"] == "text"
    assert payload["text"] == "hello"


def test_text_max_length_enforced():
    TextMessage(text="가" * MAX_TEXT_LENGTH)  # 5000자(각 UTF-16 1유닛)는 허용
    with pytest.raises(ValidationError):
        TextMessage(text="가" * (MAX_TEXT_LENGTH + 1))  # 5001자는 거부


def test_text_length_counts_utf16_code_units():
    # LINE은 UTF-16 코드 유닛으로 센다 — BMP 밖 이모지는 2유닛.
    half = MAX_TEXT_LENGTH // 2  # 2500
    TextMessage(text="🍎" * half)  # 2500자 * 2유닛 = 5000유닛 → 허용
    with pytest.raises(ValidationError):
        TextMessage(text="🍎" * (half + 1))  # 2501자 * 2유닛 = 5002유닛 → 거부


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


def test_push_result_parses_sent_messages():
    # 공식 push 응답: {"sentMessages": [{"id": "...", "quoteToken": "..."}]}
    res = PushResult.model_validate(
        {"sentMessages": [{"id": "461230966842064897", "quoteToken": "IStG5h1Tz7b"}]}
    )
    assert res.sentMessages[0].id == "461230966842064897"
    assert res.sentMessages[0].quoteToken == "IStG5h1Tz7b"


def test_push_result_quote_token_optional():
    res = PushResult.model_validate({"sentMessages": [{"id": "123"}]})
    assert res.sentMessages[0].id == "123"
    assert res.sentMessages[0].quoteToken is None


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
