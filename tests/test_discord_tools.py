"""Discord 도구 런타임 기능 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑 확인."""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.discord.tools import register

MOD = "arcsolve.services.discord.tools"
WEBHOOK = "https://discord.com/api/webhooks/1/abc"


@pytest.fixture
def dc(monkeypatch, load_tools):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", WEBHOOK)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "B")
    return load_tools(register)


async def test_send_message_webhook_request_and_output(dc, monkeypatch, recording_http):
    http = recording_http(ret={"id": "100", "channel_id": "c", "content": "hi"})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await dc["discord_send_message"](content="hi")
    assert out == "전송 완료 (message id: 100)"
    assert http.last["url"] == f"{WEBHOOK}?wait=true"
    assert http.last["json"] == {"content": "hi"}


async def test_send_message_missing_webhook(monkeypatch, load_tools):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    tools = load_tools(register)
    out = await tools["discord_send_message"](content="hi")
    assert "DISCORD_WEBHOOK_URL" in out


async def test_send_embed_builds_embeds_array(dc, monkeypatch, recording_http):
    http = recording_http(ret={"id": "101"})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await dc["discord_send_embed"](title="T", description="D", color=16711680)
    assert "임베드 전송 완료" in out
    embeds = http.last["json"]["embeds"]
    assert embeds[0]["title"] == "T" and embeds[0]["description"] == "D"
    assert embeds[0]["color"] == 16711680


async def test_send_embed_requires_a_field(dc, monkeypatch, recording_http):
    http = recording_http(ret={"id": "x"})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await dc["discord_send_embed"]()  # 모든 필드 None
    assert "입력 오류" in out
    assert not http.calls


async def test_edit_message_uses_patch_on_derived_path(dc, monkeypatch, recording_http):
    http = recording_http(ret={"id": "100"})
    monkeypatch.setattr(f"{MOD}.patch_json", http)
    out = await dc["discord_edit_message"](message_id="100", content="new")
    assert "편집 완료" in out
    assert http.last["url"] == f"{WEBHOOK}/messages/100"
    assert http.last["json"] == {"content": "new"}


async def test_delete_message_uses_delete_on_derived_path(dc, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.delete_json", http)
    out = await dc["discord_delete_message"](message_id="100")
    assert "삭제 완료" in out
    assert http.last["url"] == f"{WEBHOOK}/messages/100"


async def test_create_message_uses_bot_header_and_api_route(dc, monkeypatch, recording_http):
    http = recording_http(ret={"id": "200"})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await dc["discord_create_message"](channel_id="C", content="hi")
    assert out == "전송 완료 (message id: 200)"
    assert http.last["url"] == "https://discord.com/api/v10/channels/C/messages"
    assert http.last["headers"] == {"Authorization": "Bot B"}
    assert http.last["json"] == {"content": "hi"}


async def test_create_message_missing_bot_token(monkeypatch, load_tools):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", WEBHOOK)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    tools = load_tools(register)
    out = await tools["discord_create_message"](channel_id="C", content="hi")
    assert "DISCORD_BOT_TOKEN" in out


async def test_list_messages_request_and_parse(dc, monkeypatch, recording_http):
    http = recording_http(ret=[{"id": "1", "content": "hi", "author": {"username": "bob"}}])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await dc["discord_list_messages"](channel_id="C", limit=50)
    assert "1" in out and "bob" in out
    assert http.last["url"] == "https://discord.com/api/v10/channels/C/messages"
    assert http.last["params"] == {"limit": 50}
    assert http.last["headers"] == {"Authorization": "Bot B"}


async def test_list_messages_limit_validation(dc, monkeypatch, recording_http):
    http = recording_http(ret=[])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await dc["discord_list_messages"](channel_id="C", limit=999)
    assert "입력 오류" in out
    assert not http.calls


async def test_error_code_mapping(dc, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, {"code": 50013, "message": "x"}))
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await dc["discord_create_message"](channel_id="C", content="hi")
    assert "권한" in out  # 50013 → 권한 부족 안내
