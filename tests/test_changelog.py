"""체인지로그 조각 합본 + 릴리스 컷 검증."""

import json

import pytest

from arcsolve import __version__
from arcsolve.changelog import (
    BEGIN,
    END,
    ROOT,
    SERVER_JSON_PATH,
    collect_fragments,
    compile_changelog,
    cut_release,
    render_unreleased,
    set_init_version,
    set_server_json_version,
    validate_version,
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


def test_validate_version_accepts_semver_rejects_garbage():
    assert validate_version("0.2.0") == "0.2.0"
    validate_version("1.0.0-rc.1")
    for bad in ("v0.2.0", "0.2", "1", "abc"):
        with pytest.raises(ValueError):
            validate_version(bad)


def test_set_init_version_updates_single_source(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('"""doc"""\n\n__version__ = "0.1.0"\n', encoding="utf-8")
    set_init_version("0.2.0", init)
    assert '__version__ = "0.2.0"' in init.read_text(encoding="utf-8")


def test_cut_release_finalizes_section_and_consumes_fragments(tmp_path):
    d = tmp_path / "changelog.d"
    d.mkdir()
    (d / "a.md").write_text("- a 추가", encoding="utf-8")
    (d / "b.md").write_text("- b 추가", encoding="utf-8")
    (d / "README.md").write_text("# 스킵", encoding="utf-8")
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(
        f"# Changelog\n\n{BEGIN}\n## [Unreleased]\n\n- a 추가\n- b 추가\n{END}\n", encoding="utf-8"
    )
    consumed = cut_release("0.2.0", "2026-06-05", path=cl, fragments_dir=d)

    text = cl.read_text(encoding="utf-8")
    assert "## [0.2.0] - 2026-06-05" in text   # 버전 섹션 확정
    assert "- a 추가" in text and "- b 추가" in text
    # [Unreleased]는 비워지고 마커는 유지
    unreleased = text.split(END)[0]
    assert "_변경 없음._" in unreleased
    assert "0.2.0" not in unreleased            # 확정 내용은 Unreleased 밖
    # 조각은 소비(삭제)되고 README는 보존
    assert set(consumed) == {"a.md", "b.md"}
    assert not (d / "a.md").exists() and not (d / "b.md").exists()
    assert (d / "README.md").exists()


def test_cut_release_without_fragments_raises(tmp_path):
    d = tmp_path / "changelog.d"
    d.mkdir()
    with pytest.raises(ValueError):
        cut_release("0.2.0", "2026-06-05", path=tmp_path / "CHANGELOG.md", fragments_dir=d)


def test_set_server_json_version_syncs(tmp_path):
    p = tmp_path / "server.json"
    p.write_text(json.dumps({"version": "0.1.0", "packages": [{"version": "0.1.0"}]}), "utf-8")
    assert set_server_json_version("0.2.0", p) is True
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["version"] == "0.2.0" and data["packages"][0]["version"] == "0.2.0"


def test_set_server_json_version_absent_is_noop(tmp_path):
    assert set_server_json_version("0.2.0", tmp_path / "nope.json") is False


def test_server_json_consistent_with_readme_and_version():
    """MCP 레지스트리 server.json — README mcp-name 마커·__version__과 일관(소유권/버전 검증)."""
    data = json.loads(SERVER_JSON_PATH.read_text(encoding="utf-8"))
    name = data["name"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {name} -->" in readme   # 레지스트리 소유권 검증 마커와 일치
    assert data["version"] == __version__            # server.json 버전 = 패키지 버전
    assert data["packages"][0]["version"] == __version__
    assert data["packages"][0]["identifier"] == "arcsolve"
    assert data["packages"][0]["registryType"] == "pypi"
