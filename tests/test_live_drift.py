"""라이브 계약 드리프트 점검 — **무인증** 서비스의 대표 도구를 실제 엔드포인트로 호출해
상류 계약(엔드포인트·필드명) 변화를 사람 개입 전에 포착한다.

평소(PR/CI)에는 **건너뛴다**(무네트워크 원칙 유지). nightly에서 `ARCSOLVE_LIVE=1`로만 돈다.
실패는 PR 게이트가 아니라 nightly의 빨간불(알림)로 다룬다 — 상류 가용성에 따라 flaky할 수 있다.

  ARCSOLVE_LIVE=1 uv run pytest -m live -q
"""

import os

import pytest

from arcsolve.services.arxiv.tools import register as arxiv_register
from arcsolve.services.crossref.tools import register as crossref_register
from arcsolve.services.feeds.tools import register as feeds_register
from arcsolve.services.hackernews.tools import register as hn_register
from arcsolve.services.nws.tools import register as nws_register
from arcsolve.services.openalex.tools import register as openalex_register
from arcsolve.services.openmeteo.tools import register as openmeteo_register
from arcsolve.services.usgs_quake.tools import register as usgs_register

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("ARCSOLVE_LIVE"),
        reason="ARCSOLVE_LIVE 미설정 — 라이브 드리프트 점검 생략(무네트워크 기본)",
    ),
]

# 응답에 이 표지가 있으면 계약 드리프트/접근 문제를 의심한다(도구가 _explain으로 매핑한 에러).
_FAILURE_MARKERS = ("API 오류", "요청이 차단", "인증/권한 오류", "Traceback", "파싱 실패")

# (서비스, register, 도구, 인자, 기대 부분문자열|None) — 모두 **키 없이** 동작하는 서비스.
# 참고: wikipedia/wikidata는 Wikimedia 정책상 식별 UA(WIKIPEDIA_USER_AGENT)가 필요해 제외한다.
CASES = [
    ("openmeteo", openmeteo_register, "openmeteo_geocode", {"name": "Seoul"}, "Seoul"),
    ("hackernews", hn_register, "hn_top", {}, None),
    ("openalex", openalex_register, "openalex_search_works", {"query": "graphene"}, None),
    ("crossref", crossref_register, "crossref_search_works", {"query": "machine learning"}, None),
    ("arxiv", arxiv_register, "arxiv_search", {"query": "all:electron", "max_results": 3}, None),
    ("usgs_quake", usgs_register, "usgs_count_earthquakes", {"minmagnitude": 6.0}, None),
    ("nws", nws_register, "nws_forecast", {"latitude": 38.8977, "longitude": -77.0365}, None),
    ("feeds", feeds_register, "feeds_fetch", {"url": "https://hnrss.org/frontpage"}, None),
]


def _load(register) -> dict:
    class FakeMCP:
        def __init__(self) -> None:
            self.tools: dict = {}

        def tool(self, fn):
            self.tools[fn.__name__] = fn
            return fn

    m = FakeMCP()
    register(m)
    return m.tools


@pytest.mark.parametrize(
    "name,register,tool,kwargs,expect", CASES, ids=[c[0] for c in CASES]
)
async def test_live_contract_drift(name, register, tool, kwargs, expect):
    tools = _load(register)
    assert tool in tools, f"{name}: {tool} 미등록"
    result = await tools[tool](**kwargs)
    assert isinstance(result, str) and result.strip(), f"{name}: 빈 응답"
    for marker in _FAILURE_MARKERS:
        assert marker not in result, f"{name}: 드리프트/접근 의심 — '{marker}':\n{result[:300]}"
    if expect:
        assert expect in result, f"{name}: 기대 내용 '{expect}' 없음:\n{result[:300]}"
