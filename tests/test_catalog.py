"""카탈로그 자동 생성 검증 — 네트워크 없이 레지스트리 introspection만."""

from arcsolve.catalog import build_catalog, render_markdown


async def test_catalog_includes_kakao_with_tools():
    catalog = await build_catalog()
    by_name = {s["name"]: s for s in catalog}
    assert "kakao" in by_name
    tool_names = {t["name"] for t in by_name["kakao"]["tools"]}
    assert {"kakao_send_text_to_me", "kakao_send_link_to_me"} <= tool_names
    # 각 도구는 docstring 첫 줄을 설명으로 갖는다.
    assert all(t["description"] for t in by_name["kakao"]["tools"])


async def test_render_markdown_has_header_and_warning():
    md = render_markdown(await build_catalog())
    assert md.startswith("# 서비스 카탈로그")
    assert "자동 생성" in md
    assert "`kakao_send_text_to_me`" in md
