"""Discord 계약 검증 — 네트워크 없이 contract.py만 테스트."""

import json

import pytest
from pydantic import ValidationError

from arcsolve.services.discord.contract import (
    API_BASE_URL,
    CHANNEL_MESSAGES_ROUTE,
    CONTENT_MAX_LENGTH,
    MAX_EMBEDS,
    MESSAGES_LIMIT_DEFAULT,
    MESSAGES_LIMIT_MAX,
    MESSAGES_LIMIT_MIN,
    WAIT_PARAM,
    WEBHOOK_MESSAGE_SUFFIX,
    CreateMessageRequest,
    EditWebhookMessageRequest,
    Embed,
    EmbedFooter,
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
    assert "embeds" not in payload


def test_content_max_length_enforced():
    ExecuteWebhookRequest(content="가" * CONTENT_MAX_LENGTH)  # 2000자는 허용
    with pytest.raises(ValidationError):
        ExecuteWebhookRequest(content="가" * (CONTENT_MAX_LENGTH + 1))  # 2001자는 거부


def test_content_empty_string_rejected():
    # None(임베드 전용)은 허용하되 명시적 빈 문자열("")은 거부(상류 400 사전 방지).
    ExecuteWebhookRequest(embeds=[Embed(title="t")])  # content 없음 = OK
    with pytest.raises(ValidationError):
        ExecuteWebhookRequest(content="")


def test_execute_webhook_content_optional_for_embed_only():
    # content/embeds 중 하나면 되므로, content 없이 embeds만 있어도 모델은 유효하다.
    r = ExecuteWebhookRequest(embeds=[Embed(title="t")])
    payload = json.loads(r.model_dump_json(exclude_none=True))
    assert "content" not in payload
    assert payload["embeds"][0]["title"] == "t"


def test_message_result_partial():
    msg = MessageResult.model_validate({"id": "123", "channel_id": "456", "content": "hi"})
    assert msg.id == "123"
    assert msg.channel_id == "456"
    # 204(빈 body) 케이스: 모든 필드가 선택이라 빈 dict도 검증 통과해야 한다.
    assert MessageResult.model_validate({}).id is None


def test_message_result_parses_author():
    msg = MessageResult.model_validate(
        {"id": "1", "content": "hi", "author": {"id": "9", "username": "alice"}}
    )
    assert msg.author is not None
    assert msg.author.username == "alice"
    assert msg.author.id == "9"


# ─── Embed 모델 ─────────────────────────────────────────────


def test_embed_footer_text_required():
    EmbedFooter(text="ok")  # text는 필수
    with pytest.raises(ValidationError):
        EmbedFooter()  # text 없으면 거부


def test_embed_full_serialization():
    e = Embed(
        title="제목",
        description="설명",
        url="https://x.y",
        color=16711680,  # color는 RGB 정수
        timestamp="2026-06-01T00:00:00Z",
        footer=EmbedFooter(text="footer"),
    )
    payload = json.loads(e.model_dump_json(exclude_none=True))
    assert payload["title"] == "제목"
    assert payload["color"] == 16711680
    assert isinstance(payload["color"], int)
    assert payload["footer"] == {"text": "footer"}  # icon_url(None)은 제외


def test_embed_color_must_be_int():
    with pytest.raises(ValidationError):
        Embed(color="red")  # 문자열은 정수로 강제 불가


def test_execute_webhook_embeds_max_length():
    ten = [Embed(title=str(i)) for i in range(MAX_EMBEDS)]
    ExecuteWebhookRequest(embeds=ten)  # 10개는 허용
    with pytest.raises(ValidationError):
        ExecuteWebhookRequest(embeds=ten + [Embed(title="overflow")])  # 11개는 거부


# ─── Edit / Create 요청 ─────────────────────────────────────


def test_edit_request_all_optional():
    # 모든 필드 선택 — 빈 요청도 유효하고, content 길이는 검증된다.
    r = EditWebhookMessageRequest(content="새 본문")
    assert json.loads(r.model_dump_json(exclude_none=True)) == {"content": "새 본문"}
    with pytest.raises(ValidationError):
        EditWebhookMessageRequest(content="가" * (CONTENT_MAX_LENGTH + 1))


def test_create_message_request_content_required():
    CreateMessageRequest(content="hi")
    with pytest.raises(ValidationError):
        CreateMessageRequest()  # content 필수
    with pytest.raises(ValidationError):
        CreateMessageRequest(content="가" * (CONTENT_MAX_LENGTH + 1))


# ─── 상수 / 라우트 ──────────────────────────────────────────


def test_contract_constants():
    assert CONTENT_MAX_LENGTH == 2000
    assert WAIT_PARAM == "wait"
    assert MAX_EMBEDS == 10
    assert API_BASE_URL == "https://discord.com/api/v10"
    assert MESSAGES_LIMIT_MIN == 1
    assert MESSAGES_LIMIT_MAX == 100
    assert MESSAGES_LIMIT_DEFAULT == 50


def test_route_templates():
    assert CHANNEL_MESSAGES_ROUTE.format(channel_id="42") == "/channels/42/messages"
    assert WEBHOOK_MESSAGE_SUFFIX.format(message_id="7") == "/messages/7"
