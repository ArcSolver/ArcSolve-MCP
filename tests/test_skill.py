"""skill.py — frontmatter 파서 + 스킬 자동 발견(네트워크 없음)."""

from arcsolve.skill import (
    _as_tools,
    available,
    discover_skills,
    load_skill,
    parse_frontmatter,
)


def test_parse_frontmatter_scalars_and_block_list():
    text = (
        "---\n"
        "name: demo\n"
        'description: "Does a thing when asked."\n'
        "allowed-tools:\n"
        "  - foo_a\n"
        "  - foo_b\n"
        "---\n"
        "body\n"
    )
    fm = parse_frontmatter(text)
    assert fm["name"] == "demo"
    assert fm["description"] == "Does a thing when asked."
    assert fm["allowed-tools"] == ["foo_a", "foo_b"]


def test_parse_frontmatter_inline_list():
    fm = parse_frontmatter("---\nallowed-tools: [a, b, c]\n---\n")
    assert fm["allowed-tools"] == ["a", "b", "c"]


def test_description_with_colon_keeps_full_value():
    fm = parse_frontmatter("---\ndescription: Use when: finding papers.\n---\n")
    assert fm["description"] == "Use when: finding papers."


def test_no_frontmatter_returns_empty():
    assert parse_frontmatter("no frontmatter here") == {}


def test_as_tools_accepts_csv_list_and_none():
    assert _as_tools("a, b , c") == ("a", "b", "c")
    assert _as_tools(["x", "y"]) == ("x", "y")
    assert _as_tools(None) == ()


def test_discover_finds_academic_discovery():
    assert "academic-discovery" in available()
    skills = {s.name: s for s in discover_skills()}
    assert "academic-discovery" in skills
    assert skills["academic-discovery"].tools  # non-empty


def test_load_unknown_skill_returns_none():
    assert load_skill("does-not-exist") is None
