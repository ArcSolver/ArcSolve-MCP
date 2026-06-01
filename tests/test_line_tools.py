"""LINE 도구 런타임 기능 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑 확인."""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.line.tools import register

MOD = "arcsolve.services.line.tools"
AUTH = {"Authorization": "Bearer CT"}


@pytest.fixture
def ln(monkeypatch, load_tools):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "CT")
    monkeypatch.setenv("LINE_TO", "U1")
    return load_tools(register)


async def test_push_request_and_output(ln, monkeypatch, recording_http):
    http = recording_http(ret={"sentMessages": [{"id": "5"}]})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await ln["line_send_text"](text="hi")
    assert out == "전송 완료 (id=5)"
    assert http.last["url"].endswith("/v2/bot/message/push")
    assert http.last["headers"] == AUTH
    assert http.last["json"] == {"to": "U1", "messages": [{"type": "text", "text": "hi"}]}


async def test_push_missing_token(monkeypatch, load_tools):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("LINE_TO", "U1")
    tools = load_tools(register)
    out = await tools["line_send_text"](text="hi")
    assert "LINE_CHANNEL_ACCESS_TOKEN" in out


async def test_reply_request_and_output(ln, monkeypatch, recording_http):
    http = recording_http(ret={"sentMessages": [{"id": "9"}]})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await ln["line_reply_text"](reply_token="R", text="hi")
    assert "회신 완료 (id=9)" in out
    assert http.last["url"].endswith("/v2/bot/message/reply")
    assert http.last["json"] == {"replyToken": "R", "messages": [{"type": "text", "text": "hi"}]}


async def test_multicast_request_and_output(ln, monkeypatch, recording_http):
    http = recording_http(ret={})  # 성공 응답은 빈 객체
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await ln["line_multicast_text"](to=["U1", "U2"], text="hi")
    assert "멀티캐스트 전송 완료 (2명)" in out
    assert http.last["url"].endswith("/v2/bot/message/multicast")
    assert http.last["json"]["to"] == ["U1", "U2"]


async def test_multicast_rejects_over_500(ln, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await ln["line_multicast_text"](to=["U"] * 501, text="hi")
    assert "입력 오류" in out
    assert not http.calls  # 계약(최대 500) 위반은 HTTP 전에 막힘


async def test_broadcast_request_and_output(ln, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await ln["line_broadcast_text"](text="hi")
    assert "브로드캐스트 전송 완료" in out
    assert http.last["url"].endswith("/v2/bot/message/broadcast")
    assert http.last["json"] == {"messages": [{"type": "text", "text": "hi"}]}


async def test_get_profile_request_and_parse(ln, monkeypatch, recording_http):
    http = recording_http(ret={"displayName": "Kim", "userId": "U1", "language": "ko"})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await ln["line_get_profile"](user_id="U1")
    assert "이름: Kim" in out and "userId: U1" in out
    assert http.last["url"].endswith("/v2/bot/profile/U1")
    assert http.last["headers"] == AUTH


async def test_maps_401(ln, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"message": "invalid token"}))
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await ln["line_send_text"](text="hi")
    assert "토큰" in out
