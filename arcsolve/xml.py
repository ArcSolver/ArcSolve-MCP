"""신뢰불가 XML을 안전하게 파싱하는 공유 코어 헬퍼.

상류(또는 사용자 임의 URL)의 XML을 `xml.etree.ElementTree`로 직접 파싱하면 구형 expat에서
외부 엔티티(XXE)·엔티티 확장 폭탄(billion-laughs)에 노출될 수 있다. 최신 Python/expat은 이를
기본 차단하지만, `requires-python>=3.11`이라 구형 expat을 쓰는 환경의 회귀를 대비해 **defusedxml**로
파싱한다(심층방어). 반환은 표준 `ET.Element`라 기존 탐색 코드(ET.* )를 그대로 쓴다.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from defusedxml.ElementTree import fromstring as _defused_fromstring
from defusedxml.common import DefusedXmlException


def safe_fromstring(text: str) -> ET.Element:
    """defusedxml로 파싱(외부 엔티티/DTD 폭탄 차단). 악의적 구조는 `ET.ParseError`로 정규화한다.

    이렇게 하면 기존 `except ET.ParseError`(또는 `except ParseError`) 경로가 그대로 "잘못된 XML"로
    매핑해 사람용 메시지를 돌려준다(미처리 예외 누출 없이).
    """
    try:
        return _defused_fromstring(text)
    except DefusedXmlException as e:
        raise ET.ParseError(f"unsafe XML rejected: {type(e).__name__}") from e
