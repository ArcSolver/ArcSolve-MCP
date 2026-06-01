"""Discord 계약 검증 — 네트워크 없이 contract.py만 테스트."""

import json

import pytest
from pydantic import ValidationError

from arcsolve.services.discord.contract import (
    CONTENT_MAX_LENGTH,
    WAIT_PARAM,
    ExecuteWebhookRequest,
    MessageResult,
)


def test_request_serialization():
    r = ExecuteWebhookRequest(content="안녕", username="bot", avatar_url="https://a.b/x.png")
    payload = json.loads(r.model_dump_json(exclude_none=True))
    assert payload["content"] == "안녕"
    assert payload["username"] == "bot"
    assert payload["avatar_url"] == "https://a.b/x.png"
    assert "tts" not in payload  # None은 제외되어야 함


def test_request_omits_optional_when_absent():
    # 선택 필드는 없으면 전송 페이로드에서 아예 제외되어야 한다.
    r = ExecuteWebhookRequest(content="본문만")
    payload = json.loads(r.model_dump_json(exclude_none=True))
    assert payload == {"content": "본문만"}
    assert "username" not in payload
    assert "avatar_url" not in payload
    assert "tts" not in payload


def test_content_required():
    # content는 본 MVP에서 필수다.
    with pytest.raises(ValidationError):
        ExecuteWebhookRequest()


def test_content_max_length_enforced():
    ExecuteWebhookRequest(content="가" * CONTENT_MAX_LENGTH)  # 2000자는 허용
    with pytest.raises(ValidationError):
        ExecuteWebhookRequest(content="가" * (CONTENT_MAX_LENGTH + 1))  # 2001자는 거부


def test_message_result_partial():
    msg = MessageResult.model_validate({"id": "123", "channel_id": "456", "content": "hi"})
    assert msg.id == "123"
    assert msg.channel_id == "456"
    # 204(빈 body) 케이스: 모든 필드가 선택이라 빈 dict도 검증 통과해야 한다.
    assert MessageResult.model_validate({}).id is None


def test_contract_constants():
    assert CONTENT_MAX_LENGTH == 2000
    assert WAIT_PARAM == "wait"
