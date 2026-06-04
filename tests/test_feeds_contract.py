"""feeds 계약 검증 — RSS 2.0/Atom 1.0/RSS 1.0(RDF) 파싱·포맷 감지·정규화, 네트워크 없음."""

import pytest

from arcsolve.services.feeds import contract as c

RSS2 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Example News</title>
    <link>https://news.example.com</link>
    <description>Latest <b>headlines</b></description>
    <lastBuildDate>Mon, 01 Jun 2026 12:00:00 GMT</lastBuildDate>
    <item>
      <title>First post</title>
      <link>https://news.example.com/1</link>
      <description>Body &amp; <i>markup</i> here</description>
      <pubDate>Mon, 01 Jun 2026 09:00:00 GMT</pubDate>
      <guid>https://news.example.com/1</guid>
      <dc:creator>Alice</dc:creator>
    </item>
    <item>
      <title>Second post</title>
      <link>https://news.example.com/2</link>
      <author>bob@example.com</author>
    </item>
  </channel>
</rss>"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Blog</title>
  <subtitle>Thoughts</subtitle>
  <link href="https://blog.example.com" rel="alternate"/>
  <link href="https://blog.example.com/feed" rel="self"/>
  <updated>2026-06-01T12:00:00Z</updated>
  <entry>
    <title>Hello Atom</title>
    <link href="https://blog.example.com/hello" rel="alternate"/>
    <id>tag:blog.example.com,2026:hello</id>
    <published>2026-06-01T09:00:00Z</published>
    <summary>An &lt;b&gt;atom&lt;/b&gt; summary</summary>
    <author><name>Carol</name></author>
  </entry>
</feed>"""

RDF = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns="http://purl.org/rss/1.0/"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel rdf:about="https://rdf.example.com">
    <title>RDF Site</title>
    <link>https://rdf.example.com</link>
    <description>An RDF feed</description>
  </channel>
  <item rdf:about="https://rdf.example.com/a">
    <title>RDF item</title>
    <link>https://rdf.example.com/a</link>
    <description>rdf body</description>
    <dc:date>2026-06-01</dc:date>
    <dc:creator>Dave</dc:creator>
  </item>
</rdf:RDF>"""


# ─── 포맷 감지 + RSS 2.0 ─────────────────────────────────────


def test_parse_rss2():
    feed = c.parse_feed(RSS2)
    assert feed.format == "rss"
    assert feed.title == "Example News"
    assert feed.link == "https://news.example.com"
    assert feed.description == "Latest headlines"  # 태그 제거됨
    assert feed.updated == "Mon, 01 Jun 2026 12:00:00 GMT"
    assert len(feed.items) == 2
    first = feed.items[0]
    assert first.title == "First post"
    assert first.link == "https://news.example.com/1"
    assert first.summary == "Body & markup here"  # 엔티티 복원 + 태그 제거
    assert first.published == "Mon, 01 Jun 2026 09:00:00 GMT"
    assert first.id == "https://news.example.com/1"
    assert first.author == "Alice"  # dc:creator
    assert feed.items[1].author == "bob@example.com"  # <author> 폴백


# ─── Atom 1.0 ───────────────────────────────────────────────


def test_parse_atom():
    feed = c.parse_feed(ATOM)
    assert feed.format == "atom"
    assert feed.title == "Example Blog"
    assert feed.description == "Thoughts"  # subtitle
    assert feed.link == "https://blog.example.com"  # rel=alternate, rel=self 아님
    assert feed.updated == "2026-06-01T12:00:00Z"
    assert len(feed.items) == 1
    e = feed.items[0]
    assert e.title == "Hello Atom"
    assert e.link == "https://blog.example.com/hello"
    assert e.id == "tag:blog.example.com,2026:hello"
    assert e.published == "2026-06-01T09:00:00Z"
    assert e.summary == "An atom summary"
    assert e.author == "Carol"  # author/name


# ─── RSS 1.0/RDF ────────────────────────────────────────────


def test_parse_rdf():
    feed = c.parse_feed(RDF)
    assert feed.format == "rdf"
    assert feed.title == "RDF Site"
    assert feed.link == "https://rdf.example.com"
    assert len(feed.items) == 1  # item은 channel 밖 형제
    it = feed.items[0]
    assert it.title == "RDF item"
    assert it.link == "https://rdf.example.com/a"
    assert it.published == "2026-06-01"  # dc:date
    assert it.author == "Dave"  # dc:creator
    assert it.id == "https://rdf.example.com/a"  # rdf:about


# ─── clean_text ─────────────────────────────────────────────


def test_clean_text_strips_and_truncates():
    assert c.clean_text("<p>hi &amp; bye</p>") == "hi & bye"
    assert c.clean_text(None) is None
    assert c.clean_text("   ") is None
    long = "x" * (c.MAX_SUMMARY_CHARS + 50)
    out = c.clean_text(long)
    assert out.endswith("…") and len(out) <= c.MAX_SUMMARY_CHARS + 1


# ─── 에러 / 검증 ─────────────────────────────────────────────


def test_unknown_root_raises():
    with pytest.raises(ValueError, match="알 수 없는 피드 포맷"):
        c.parse_feed("<html><body>not a feed</body></html>")


def test_validate_limit():
    assert c.validate_limit(20) == 20
    with pytest.raises(ValueError):
        c.validate_limit(0)
    with pytest.raises(ValueError):
        c.validate_limit(c.MAX_ITEM_LIMIT + 1)
