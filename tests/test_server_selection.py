"""런타임 서비스 선택 검증."""

import pytest

from arcsolve.server import build_server
from arcsolve.services import available, select_services


def test_available_lists_kakao():
    assert "kakao" in available()


def test_select_default_includes_all():
    names = [s.name for s in select_services()]
    assert "kakao" in names


def test_select_subset():
    assert [s.name for s in select_services(["kakao"])] == ["kakao"]


def test_select_unknown_raises():
    with pytest.raises(ValueError):
        select_services(["does-not-exist"])


async def test_build_server_with_selection_exposes_only_selected():
    mcp = build_server(["kakao"])
    tool_names = {t.name for t in await mcp.list_tools()}
    assert "kakao_send_text_to_me" in tool_names
