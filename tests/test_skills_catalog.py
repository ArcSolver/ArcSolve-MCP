"""스킬 카탈로그 렌더링(네트워크 없음)."""

from arcsolve.catalog import build_skills_catalog, render_skills_markdown


def test_skills_catalog_includes_academic_discovery():
    cat = build_skills_catalog()
    assert any(s["name"] == "academic-discovery" for s in cat)


def test_render_skills_markdown():
    md = render_skills_markdown(build_skills_catalog())
    assert "# 스킬 카탈로그" in md
    assert "academic-discovery" in md
