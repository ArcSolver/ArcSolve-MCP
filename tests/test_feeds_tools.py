"""feeds 도구 런타임 검증 — 요청 조립·XML 파싱·url/limit 검증·에러 매핑, 네트워크 없음.

get_text는 raw str(XML)을 돌려주므로 RecordingHTTP의 ret도 str(XML)로 준다. 무인증.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.feeds.tools import register

MOD = "arcsolve.services.feeds.tools"

RSS2 = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <link>https://news.example.com</link>
    <description>Headlines</description>
    <item>
      <title>First post</title>
      <link>https://news.example.com/1</link>
      <description>Hello world</description>
      <pubDate>Mon, 01 Jun 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""


@pytest.fixture
def tools(load_tools):
    return load_tools(register)


async def test_fetch_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=RSS2)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["feeds_fetch"](url="https://news.example.com/rss", limit=5)
    assert http.last["url"] == "https://news.example.com/rss"
    assert "arcsolve" in http.last["headers"]["User-Agent"]
    assert "Example News" in out and "[rss]" in out
    assert "First post" in out
    assert "https://news.example.com/1" in out
    assert "Hello world" in out
    assert "Mon, 01 Jun 2026 09:00:00 GMT" in out


async def test_fetch_empty_items(tools, monkeypatch, recording_http):
    http = recording_http(ret=EMPTY_RSS)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="https://x.com/feed")
    assert "항목 없음" in out


async def test_empty_url_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=RSS2)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="   ")
    assert "비어" in out
    assert not http.calls


async def test_non_http_url_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=RSS2)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="ftp://example.com/feed")
    assert "http" in out
    assert not http.calls


async def test_bad_limit_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=RSS2)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="https://x.com/feed", limit=0)
    assert "limit" in out
    assert not http.calls


async def test_maps_404(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(404, "not found"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="https://x.com/missing")
    assert "404" in out


async def test_maps_403(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "forbidden"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="https://x.com/private")
    assert "403" in out


async def test_maps_xml_parse_error(tools, monkeypatch, recording_http):
    http = recording_http(ret="<rss><channel>broken")
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="https://x.com/feed")
    assert "파싱 실패" in out


async def test_maps_unknown_format(tools, monkeypatch, recording_http):
    http = recording_http(ret="<html><body>page</body></html>")
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["feeds_fetch"](url="https://x.com/page")
    assert "알 수 없는 피드 포맷" in out
