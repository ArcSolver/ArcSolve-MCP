"""LINE 계약 검증 — 네트워크 없이 contract.py만 테스트."""

import json

import pytest
from pydantic import ValidationError

from arcsolve.services.line.contract import (
    BASE_URL,
    BROADCAST_MESSAGE,
    MAX_MESSAGES,
    MAX_MULTICAST_RECIPIENTS,
    MAX_TEXT_LENGTH,
    MULTICAST_MESSAGE,
    PROFILE,
    PUSH_MESSAGE,
    REPLY_MESSAGE,
    BroadcastRequest,
    EmptyResult,
    ErrorResponse,
    MulticastRequest,
    Profile,
    PushRequest,
    PushResult,
    ReplyRequest,
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


# ─── reply ──────────────────────────────────────────────────


def test_reply_request_serialization_omits_optional():
    req = ReplyRequest(replyToken="abc", messages=[TextMessage(text="hi")])
    payload = json.loads(req.model_dump_json(exclude_none=True))
    assert payload["replyToken"] == "abc"
    assert payload["messages"][0]["text"] == "hi"
    assert "notificationDisabled" not in payload  # None은 제외


def test_reply_request_requires_token():
    with pytest.raises(ValidationError):
        ReplyRequest(replyToken="", messages=[TextMessage(text="hi")])


def test_reply_request_messages_max_five_enforced():
    msgs = [TextMessage(text="m")]
    ReplyRequest(replyToken="t", messages=msgs * MAX_MESSAGES)
    with pytest.raises(ValidationError):
        ReplyRequest(replyToken="t", messages=msgs * (MAX_MESSAGES + 1))


def test_reply_response_uses_sent_messages():
    # 공식: reply도 push와 동일하게 sentMessages[]를 반환.
    res = PushResult.model_validate({"sentMessages": [{"id": "461230966842064897"}]})
    assert res.sentMessages[0].id == "461230966842064897"


# ─── multicast ──────────────────────────────────────────────


def test_multicast_request_serialization():
    req = MulticastRequest(to=["U1", "U2"], messages=[TextMessage(text="hi")])
    payload = json.loads(req.model_dump_json(exclude_none=True))
    assert payload["to"] == ["U1", "U2"]
    assert payload["messages"][0]["text"] == "hi"
    assert "notificationDisabled" not in payload


def test_multicast_to_max_500_enforced():
    # 공식: "Max: 500 user IDs"
    assert MAX_MULTICAST_RECIPIENTS == 500
    MulticastRequest(to=["U"] * MAX_MULTICAST_RECIPIENTS, messages=[TextMessage(text="m")])
    with pytest.raises(ValidationError):
        MulticastRequest(
            to=["U"] * (MAX_MULTICAST_RECIPIENTS + 1), messages=[TextMessage(text="m")]
        )


def test_multicast_to_min_one_enforced():
    with pytest.raises(ValidationError):
        MulticastRequest(to=[], messages=[TextMessage(text="m")])


def test_multicast_messages_max_five_enforced():
    msgs = [TextMessage(text="m")]
    MulticastRequest(to=["U1"], messages=msgs * MAX_MESSAGES)
    with pytest.raises(ValidationError):
        MulticastRequest(to=["U1"], messages=msgs * (MAX_MESSAGES + 1))


# ─── broadcast ──────────────────────────────────────────────


def test_broadcast_request_serialization():
    req = BroadcastRequest(messages=[TextMessage(text="hi")])
    payload = json.loads(req.model_dump_json(exclude_none=True))
    assert payload["messages"][0]["text"] == "hi"
    assert "notificationDisabled" not in payload
    assert "to" not in payload  # broadcast는 to가 없다


def test_broadcast_messages_max_five_enforced():
    msgs = [TextMessage(text="m")]
    BroadcastRequest(messages=msgs * MAX_MESSAGES)
    with pytest.raises(ValidationError):
        BroadcastRequest(messages=msgs * (MAX_MESSAGES + 1))


def test_empty_result_parses_empty_object():
    # 공식: multicast/broadcast 성공 응답은 빈 객체 {}.
    EmptyResult.model_validate({})
    EmptyResult.model_validate({"unexpected": 1})  # extra="ignore"


# ─── profile ────────────────────────────────────────────────


def test_profile_full_response():
    p = Profile.model_validate(
        {
            "displayName": "LINE taro",
            "userId": "U4af4980629",
            "language": "en",
            "pictureUrl": "https://profile.line-scdn.net/x",
            "statusMessage": "Hello, LINE!",
        }
    )
    assert p.displayName == "LINE taro"
    assert p.userId == "U4af4980629"
    assert p.language == "en"
    assert p.pictureUrl.startswith("https://")
    assert p.statusMessage == "Hello, LINE!"


def test_profile_optional_fields_absent():
    # pictureUrl/statusMessage/language는 "Not always included" → 없어도 유효.
    p = Profile.model_validate({"displayName": "taro", "userId": "U1"})
    assert p.pictureUrl is None
    assert p.statusMessage is None
    assert p.language is None


def test_profile_requires_display_name_and_user_id():
    with pytest.raises(ValidationError):
        Profile.model_validate({"displayName": "taro"})  # userId 누락
    with pytest.raises(ValidationError):
        Profile.model_validate({"userId": "U1"})  # displayName 누락


# ─── endpoint constants ─────────────────────────────────────


def test_new_endpoint_constants():
    assert REPLY_MESSAGE == "/v2/bot/message/reply"
    assert MULTICAST_MESSAGE == "/v2/bot/message/multicast"
    assert BROADCAST_MESSAGE == "/v2/bot/message/broadcast"
    assert PROFILE == "/v2/bot/profile/{user_id}"
    assert PROFILE.format(user_id="U1") == "/v2/bot/profile/U1"
