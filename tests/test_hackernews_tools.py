"""hackernews 도구 런타임 검증 — 요청 조립·JSON 파싱·검증·에러 매핑, 네트워크 없음.

Firebase/Algolia 둘 다 JSON이라 get_json을 RecordingHTTP로 monkeypatch한다. hn_top은
랭킹(배열)→아이템(dict) 두 종류 호출이라 url 분기 fake로 검증한다. 무인증.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.hackernews.tools import register

MOD = "arcsolve.services.hackernews.tools"

STORY = {
    "id": 8863,
    "type": "story",
    "by": "dhouston",
    "time": 1175714200,
    "title": "My YC app: Dropbox",
    "url": "http://www.getdropbox.com",
    "score": 111,
    "descendants": 71,
    "kids": [9224],
}
COMMENT = {
    "id": 2921983,
    "type": "comment",
    "by": "norvig",
    "time": 1314211127,
    "text": "Aw &amp; shucks",
    "parent": 2921506,
}
USER = {"id": "pg", "created": 1160418092, "karma": 155111, "about": "<a>Bio</a>", "submitted": [1, 2, 3]}
ALGOLIA = {
    "hits": [
        {"objectID": "8863", "title": "Dropbox", "author": "dhouston",
         "points": 111, "num_comments": 71, "url": "http://x"}
    ],
    "nbHits": 1,
    "nbPages": 1,
}


@pytest.fixture
def tools(load_tools):
    return load_tools(register)


# ─── hn_item ─────────────────────────────────────────────────


async def test_item_story(tools, monkeypatch, recording_http):
    http = recording_http(ret=STORY)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_item"](id=8863)
    assert http.last["url"].endswith("/item/8863.json")
    assert "Dropbox" in out and "111점" in out and "댓글 71" in out
    assert "dhouston" in out and "getdropbox" in out
    assert "id=8863" in out  # permalink


async def test_item_comment(tools, monkeypatch, recording_http):
    http = recording_http(ret=COMMENT)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_item"](id=2921983)
    assert "댓글" in out and "norvig" in out
    assert "Aw & shucks" in out  # 엔티티 복원
    assert "2921506" in out  # parent


async def test_item_not_found(tools, monkeypatch, recording_http):
    http = recording_http(ret={})  # HN은 없는 id에 null → 빈 응답
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_item"](id=999999999)
    assert "찾을 수 없" in out


async def test_item_404(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(404, "nf"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_item"](id=1)
    assert "404" in out


# ─── hn_top (N+1: 랭킹 배열 → 아이템 dict) ──────────────────


async def test_top(tools, monkeypatch):
    async def fake(url, **kw):
        if "topstories" in url:
            return [8863, 8864]
        return STORY

    monkeypatch.setattr(f"{MOD}.get_json", fake)
    out = await tools["hn_top"](kind="top", limit=2)
    assert "HN top 상위 2건" in out
    assert out.count("Dropbox") == 2  # 두 아이템 모두


async def test_top_bad_kind_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=[1])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_top"](kind="nope")
    assert "kind" in out
    assert not http.calls


async def test_top_bad_limit_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=[1])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_top"](kind="top", limit=999)
    assert "limit" in out
    assert not http.calls


# ─── hn_search (Algolia) ────────────────────────────────────


async def test_search_relevance(tools, monkeypatch, recording_http):
    http = recording_http(ret=ALGOLIA)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_search"](query="dropbox", limit=5)
    assert http.last["url"].endswith("/search")  # 관련도(기본)
    assert http.last["params"]["query"] == "dropbox"
    assert http.last["params"]["hitsPerPage"] == 5
    assert "총 1건" in out and "관련도순" in out
    assert "Dropbox" in out and "111점" in out


async def test_search_by_date_with_tags(tools, monkeypatch, recording_http):
    http = recording_http(ret=ALGOLIA)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_search"](query="x", by_date=True, tags="story")
    assert http.last["url"].endswith("/search_by_date")
    assert http.last["params"]["tags"] == "story"
    assert "최신순" in out


async def test_search_empty_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=ALGOLIA)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_search"](query="   ")
    assert "비어" in out
    assert not http.calls


# ─── hn_user ─────────────────────────────────────────────────


async def test_user(tools, monkeypatch, recording_http):
    http = recording_http(ret=USER)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_user"](id="pg")
    assert http.last["url"].endswith("/user/pg.json")
    assert "pg" in out and "karma 155111" in out and "제출 3건" in out
    assert "Bio" in out


async def test_user_not_found(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["hn_user"](id="ghost")
    assert "찾을 수 없" in out
