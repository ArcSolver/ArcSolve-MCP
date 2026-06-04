"""공유 XML 안전 파서 — XXE/엔티티 폭탄을 ParseError로 정규화하는지 검증(네트워크 없음)."""

import xml.etree.ElementTree as ET

import pytest

from arcsolve.xml import safe_fromstring

BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<lolz>&lol3;</lolz>"""

XXE = """<?xml version="1.0"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<foo>&xxe;</foo>"""


def test_safe_fromstring_parses_normal_xml():
    root = safe_fromstring("<rss><channel><title>ok</title></channel></rss>")
    assert root.find("channel/title").text == "ok"


def test_safe_fromstring_rejects_entity_expansion():
    # billion-laughs(엔티티 확장 폭탄)는 차단되어 ET.ParseError로 정규화된다.
    with pytest.raises(ET.ParseError):
        safe_fromstring(BILLION_LAUGHS)


def test_safe_fromstring_rejects_external_entity():
    # XXE(외부 엔티티 — 로컬 파일 탈취 시도)도 ET.ParseError로 정규화된다.
    with pytest.raises(ET.ParseError):
        safe_fromstring(XXE)


def test_safe_fromstring_malformed_is_parse_error():
    with pytest.raises(ET.ParseError):
        safe_fromstring("<broken><unclosed>")
