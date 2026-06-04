"""RSS/Atom/RDF 피드 읽기 계약(contract).

임의 피드 URL의 XML을 **표준 라이브러리 `xml.etree.ElementTree`**로 파싱해 통일 모델로
정규화한다. 세 포맷 지원: RSS 2.0(`<rss><channel>`), Atom 1.0(`<feed>`),
RSS 1.0/RDF(`<rdf:RDF>`). MCP/네트워크 무의존(순수 상수 + pydantic 모델 + stdlib XML).

전부 GET·읽기·**무인증**(키 없음). 피드는 JSON이 아니라 XML이라 코어 `get_text`(raw str)로
받고 여기서 파싱한다(feedparser/lxml 등 외부 의존 금지 — arxiv와 동형). 요소 탐색은
**로컬명 기반**(네임스페이스 무관)이라 RSS/Atom 변형과 `dc:`/`content:` 확장을 함께 흡수한다.

출처(공식 스펙):
  - RSS 2.0: https://www.rssboard.org/rss-specification
  - Atom 1.0 (RFC 4287): https://datatracker.ietf.org/doc/html/rfc4287
  - RSS 1.0 (RDF Site Summary): https://web.resource.org/rss/1.0/spec
  - Dublin Core elements (dc:creator·dc:date): https://www.dublincore.org/specifications/dublin-core/dcmi-terms/
"""

from __future__ import annotations

import html as _htmllib
import re
import xml.etree.ElementTree as ET

from arcsolve.xml import safe_fromstring

from pydantic import BaseModel

# ─── 제약 상수 ──────────────────────────────────────────────
# 요약 성격(전문은 link로) — 본문이 길면 자른다.
MAX_SUMMARY_CHARS = 500
MAX_DESCRIPTION_CHARS = 300
DEFAULT_ITEM_LIMIT = 20
MAX_ITEM_LIMIT = 100


def validate_limit(limit: int) -> int:
    """항목 개수 limit를 1..MAX_ITEM_LIMIT로 검증한다(위반 시 ValueError)."""
    if limit < 1 or limit > MAX_ITEM_LIMIT:
        raise ValueError(f"limit는 1..{MAX_ITEM_LIMIT} 범위여야 합니다(현재 {limit}).")
    return limit


# ─── 통일 응답 모델 ─────────────────────────────────────────
# RSS/Atom/RDF의 서로 다른 요소명을 하나의 모델로 정규화한다. 날짜는 **원본 문자열 그대로**
# 보존한다(RFC822 vs ISO8601 변환은 파싱 실패 위험이 있어 비목표 — 표시용으로 충분).


class FeedItem(BaseModel):
    """피드 항목 1개(RSS item · Atom entry · RDF item 공통)."""

    title: str | None = None
    link: str | None = None
    published: str | None = None  # 원본 날짜(pubDate/published/updated/dc:date) — 미변환
    summary: str | None = None  # 평문(태그 제거·길이 제한)
    author: str | None = None
    id: str | None = None  # guid(RSS) / id(Atom) / rdf:about(RDF)


class ParsedFeed(BaseModel):
    """피드 메타 + 항목 리스트."""

    format: str  # "rss" | "atom" | "rdf"
    title: str | None = None
    link: str | None = None
    description: str | None = None
    updated: str | None = None
    items: list[FeedItem] = []


# ─── 텍스트 헬퍼 ─────────────────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(raw: str | None, *, limit: int | None = MAX_SUMMARY_CHARS) -> str | None:
    """HTML 태그 제거 + 엔티티 복원(`html.unescape`) + 공백 정리. limit 넘으면 자른다.

    피드 description/summary는 HTML 스니펫인 경우가 많아 평문화한다(wikipedia.strip_html과 동형).
    None/빈값이면 None.
    """
    if not raw:
        return None
    text = _TAG_RE.sub("", raw)
    text = _htmllib.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return None
    if limit and len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _local(tag: str) -> str:
    """`{namespace}local` 형태(ET의 정규화된 태그)에서 로컬명만 뽑는다."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el: ET.Element | None) -> str | None:
    """요소의 전체 텍스트(하위 mixed content 포함)를 trim해 돌려준다(없으면 None).

    description/summary에 raw inline 마크업(`<b>` 등)이 섞여 ET가 자식 엘리먼트로 쪼개도
    `itertext()`로 모두 모은다(escaped HTML은 별도로 clean_text가 태그 제거). 빈 문자열도 None.
    """
    if el is None:
        return None
    t = "".join(el.itertext()).strip()
    return t or None


def _child(parent: ET.Element, name: str) -> ET.Element | None:
    """네임스페이스 무관하게 로컬명이 name인 첫 직계 자식을 돌려준다."""
    for child in parent:
        if _local(child.tag) == name:
            return child
    return None


def _children(parent: ET.Element, name: str) -> list[ET.Element]:
    """네임스페이스 무관하게 로컬명이 name인 모든 직계 자식을 돌려준다."""
    return [child for child in parent if _local(child.tag) == name]


def _child_text(parent: ET.Element, name: str) -> str | None:
    return _text(_child(parent, name))


# ─── 포맷별 파서 ─────────────────────────────────────────────


def _atom_link(parent: ET.Element) -> str | None:
    """Atom `<link href rel>` 중 rel='alternate'(또는 rel 미지정)의 href를 고른다.

    출처: RFC 4287 §4.2.7 (link relation; "alternate" 기본). self/enclosure 등은 제외.
    """
    fallback: str | None = None
    for ln in _children(parent, "link"):
        rel = ln.get("rel")
        href = ln.get("href")
        if not href:
            continue
        if rel in (None, "alternate"):
            return href
        if fallback is None:
            fallback = href
    return fallback


def _parse_atom(root: ET.Element) -> ParsedFeed:
    """Atom 1.0 `<feed>` → ParsedFeed. 출처: RFC 4287."""
    items: list[FeedItem] = []
    for e in _children(root, "entry"):
        author_el = _child(e, "author")
        author = _child_text(author_el, "name") if author_el is not None else None
        # summary 우선, 없으면 content.
        body = _child_text(e, "summary") or _child_text(e, "content")
        items.append(
            FeedItem(
                title=clean_text(_child_text(e, "title"), limit=None),
                link=_atom_link(e),
                published=_child_text(e, "published") or _child_text(e, "updated"),
                summary=clean_text(body),
                author=author,
                id=_child_text(e, "id"),
            )
        )
    return ParsedFeed(
        format="atom",
        title=clean_text(_child_text(root, "title"), limit=None),
        link=_atom_link(root),
        description=clean_text(_child_text(root, "subtitle"), limit=MAX_DESCRIPTION_CHARS),
        updated=_child_text(root, "updated"),
        items=items,
    )


def _parse_rss_item(it: ET.Element) -> FeedItem:
    """RSS 2.0 `<item>` → FeedItem. author는 <author> 또는 <dc:creator>."""
    return FeedItem(
        title=clean_text(_child_text(it, "title"), limit=None),
        link=_child_text(it, "link"),
        published=_child_text(it, "pubDate") or _child_text(it, "date"),
        summary=clean_text(_child_text(it, "description") or _child_text(it, "encoded")),
        author=_child_text(it, "author") or _child_text(it, "creator"),
        id=_child_text(it, "guid"),
    )


def _parse_rss(root: ET.Element) -> ParsedFeed:
    """RSS 2.0 `<rss><channel>` → ParsedFeed. 출처: RSS 2.0 spec."""
    channel = _child(root, "channel")
    if channel is None:
        return ParsedFeed(format="rss")
    items = [_parse_rss_item(it) for it in _children(channel, "item")]
    return ParsedFeed(
        format="rss",
        title=clean_text(_child_text(channel, "title"), limit=None),
        link=_child_text(channel, "link"),
        description=clean_text(_child_text(channel, "description"), limit=MAX_DESCRIPTION_CHARS),
        updated=_child_text(channel, "lastBuildDate") or _child_text(channel, "pubDate"),
        items=items,
    )


def _parse_rdf(root: ET.Element) -> ParsedFeed:
    """RSS 1.0/RDF `<rdf:RDF>` → ParsedFeed.

    RDF에서 `<item>`은 `<channel>` 밖, `<rdf:RDF>` 직계에 형제로 온다. dc:date/dc:creator 사용.
    출처: RSS 1.0 spec.
    """
    channel = _child(root, "channel")
    items: list[FeedItem] = []
    for it in _children(root, "item"):
        items.append(
            FeedItem(
                title=clean_text(_child_text(it, "title"), limit=None),
                link=_child_text(it, "link"),
                published=_child_text(it, "date"),  # dc:date
                summary=clean_text(_child_text(it, "description") or _child_text(it, "encoded")),
                author=_child_text(it, "creator"),  # dc:creator
                id=it.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about")
                or _child_text(it, "link"),
            )
        )
    return ParsedFeed(
        format="rdf",
        title=clean_text(_child_text(channel, "title"), limit=None) if channel is not None else None,
        link=_child_text(channel, "link") if channel is not None else None,
        description=(
            clean_text(_child_text(channel, "description"), limit=MAX_DESCRIPTION_CHARS)
            if channel is not None
            else None
        ),
        updated=_child_text(channel, "date") if channel is not None else None,
        items=items,
    )


def parse_feed(xml_text: str) -> ParsedFeed:
    """피드 XML 문자열을 ParsedFeed로 파싱한다(루트 엘리먼트로 포맷 자동 감지).

    - `<feed>` → Atom 1.0
    - `<rss>` → RSS 2.0
    - `<rdf:RDF>` → RSS 1.0/RDF
    XML이 깨졌으면 `ET.ParseError`가 올라간다(호출부가 매핑). 알 수 없는 루트는 ValueError.
    """
    root = safe_fromstring(xml_text)
    name = _local(root.tag)
    if name == "feed":
        return _parse_atom(root)
    if name == "rss":
        return _parse_rss(root)
    if name == "RDF":
        return _parse_rdf(root)
    raise ValueError(
        f"알 수 없는 피드 포맷(root=<{name}>). RSS 2.0·Atom 1.0·RSS 1.0/RDF만 지원합니다."
    )
