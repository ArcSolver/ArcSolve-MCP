"""체인지로그 조각 합본 검증."""

from arcsolve.changelog import (
    BEGIN,
    END,
    collect_fragments,
    compile_changelog,
    render_unreleased,
)


def test_collect_skips_readme(tmp_path):
    d = tmp_path / "changelog.d"
    d.mkdir()
    (d / "kakao.md").write_text("- **kakao**: x 추가", encoding="utf-8")
    (d / "README.md").write_text("# 설명(스킵되어야 함)", encoding="utf-8")
    body = collect_fragments(d)
    assert "kakao" in body
    assert "스킵" not in body


def test_render_unreleased_has_markers():
    block = render_unreleased("- a")
    assert block.startswith(BEGIN)
    assert block.rstrip().endswith(END)
    assert "## [Unreleased]" in block


def test_compile_replaces_block_and_preserves_releases(tmp_path):
    d = tmp_path / "changelog.d"
    d.mkdir()
    (d / "a.md").write_text("- a 추가", encoding="utf-8")
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(
        f"# Changelog\n\n{BEGIN}\n## [Unreleased]\n\n_옛 내용_\n{END}\n\n## [0.1.0]\n- init\n",
        encoding="utf-8",
    )
    compile_changelog(cl, d)
    text = cl.read_text(encoding="utf-8")
    assert "- a 추가" in text       # 조각이 반영됨
    assert "_옛 내용_" not in text   # 이전 Unreleased는 교체됨
    assert "## [0.1.0]" in text      # 릴리즈된 섹션은 보존됨
