"""provenance(출처) 강제 — 모든 스킬이 출처·필요 도구를 문서화하고
allowed-tools가 실재 MCP 도구를 가리키는지 검증(네트워크 없음, 도구 register만)."""

import asyncio

from arcsolve.catalog import build_catalog
from arcsolve.skill import discover_skills


def _all_tool_names() -> set[str]:
    catalog = asyncio.run(build_catalog())
    return {t["name"] for s in catalog for t in s["tools"]}


def test_every_skill_has_name_and_description():
    for s in discover_skills():
        assert s.name, "스킬 name 누락"
        assert s.description.strip(), f"{s.name}: description 누락"


def test_every_skill_readme_cites_sources_and_tools():
    for s in discover_skills():
        readme = s.path / "README.md"
        assert readme.exists(), f"{s.name}: README.md 없음"
        text = readme.read_text(encoding="utf-8")
        assert "계약 출처" in text, f"{s.name}: README에 '계약 출처' 섹션 없음"
        assert "필요 MCP 도구" in text, f"{s.name}: README에 '필요 MCP 도구' 섹션 없음"


def test_skill_allowed_tools_exist():
    known = _all_tool_names()
    for s in discover_skills():
        for tool in s.tools:
            assert tool in known, f"{s.name}: allowed-tools '{tool}'가 실재 도구가 아님"
