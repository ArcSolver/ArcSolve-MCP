"""Kakao 도구 런타임 기능 검증 — 네트워크/OAuth 없이 요청 조립·응답 파싱·에러 매핑 확인.

make_oauth_client는 access_token()을 즉시 돌려주는 스텁으로 대체한다(토큰 갱신 네트워크 회피).
"""

import json

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.kakao.tools import register

MOD = "arcsolve.services.kakao.tools"


class _FakeOAuth:
    async def access_token(self) -> str:
        return "TOKEN"


@pytest.fixture
def kk(monkeypatch, load_tools):
    monkeypatch.setattr(f"{MOD}.make_oauth_client", lambda: _FakeOAuth())
    return load_tools(register)


async def test_send_text_request_and_output(kk, monkeypatch, recording_http):
    http = recording_http(ret={"result_code": 0})
    monkeypatch.setattr(f"{MOD}.post_form", http)
    out = await kk["kakao_send_text_to_me"](text="hi")
    assert out == "전송 완료"
    assert http.last["url"].endswith("/v2/api/talk/memo/default/send")
    assert http.last["token"] == "TOKEN"
    template = json.loads(http.last["data"]["template_object"])
    assert template["object_type"] == "text" and template["text"] == "hi"


async def test_send_text_with_link_adds_button(kk, monkeypatch, recording_http):
    http = recording_http(ret={"result_code": 0})
    monkeypatch.setattr(f"{MOD}.post_form", http)
    out = await kk["kakao_send_text_to_me"](text="hi", link_url="https://x")
    assert out == "전송 완료"
    template = json.loads(http.last["data"]["template_object"])
    assert template["link"]["web_url"] == "https://x"


async def test_send_link_scrap_request(kk, monkeypatch, recording_http):
    http = recording_http(ret={"result_code": 0})
    monkeypatch.setattr(f"{MOD}.post_form", http)
    out = await kk["kakao_send_link_to_me"](url="https://x/page")
    assert out == "전송 완료"
    assert http.last["url"].endswith("/v2/api/talk/memo/scrap/send")
    assert http.last["data"]["request_url"] == "https://x/page"


async def test_maps_token_error(kk, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"code": -401, "msg": "expired"}))
    monkeypatch.setattr(f"{MOD}.post_form", http)
    out = await kk["kakao_send_text_to_me"](text="hi")
    assert "auth kakao" in out  # -401 → 재인증 안내


async def test_maps_scope_error(kk, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, {"code": -402, "msg": "scope"}))
    monkeypatch.setattr(f"{MOD}.post_form", http)
    out = await kk["kakao_send_text_to_me"](text="hi")
    assert "talk_message" in out  # -402 → 동의항목 안내
