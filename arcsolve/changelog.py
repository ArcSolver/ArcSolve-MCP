"""changelog.d/ 조각을 단일 CHANGELOG.md의 [Unreleased] 섹션으로 합본한다.

각 서비스 에이전트는 `changelog.d/<name>.md`에 자기 변경만 적고(병렬 충돌 없음),
통합 단계에서 `arcsolve changelog`로 합본한다. 마커 사이만 교체하므로 릴리즈된
버전 섹션은 보존된다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAGMENTS_DIR = ROOT / "changelog.d"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
INIT_PATH = ROOT / "arcsolve" / "__init__.py"
SERVER_JSON_PATH = ROOT / "server.json"

BEGIN = "<!-- BEGIN UNRELEASED -->"
END = "<!-- END UNRELEASED -->"

# 버전 단일 출처(arcsolve/__init__.py) — 릴리스 컷 시 여기를 갱신한다(pyproject는 hatch dynamic).
_VERSION_RE = re.compile(r'(__version__\s*=\s*")[^"]+(")')
# SemVer(MAJOR.MINOR.PATCH) + 선택적 pre-release/빌드 식별자.
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([.\-+][0-9A-Za-z.\-]+)?$")


def collect_fragments(fragments_dir: Path = FRAGMENTS_DIR) -> str:
    if not fragments_dir.exists():
        return ""
    parts: list[str] = []
    for p in sorted(fragments_dir.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        text = p.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def render_unreleased(body: str) -> str:
    inner = body if body.strip() else "_변경 없음._"
    return f"{BEGIN}\n## [Unreleased]\n\n{inner}\n{END}"


def _initial() -> str:
    return (
        "# Changelog\n\n"
        "이 프로젝트의 주요 변경 사항. Keep a Changelog 형식 · SemVer 준수.\n\n"
        f"{render_unreleased('')}\n"
    )


def _replace_block(text: str, block: str) -> str:
    if BEGIN in text and END in text:
        pre = text.split(BEGIN)[0]
        post = text.split(END, 1)[1]
        return f"{pre}{block}{post}"
    return text.rstrip() + "\n\n" + block + "\n"


def compile_changelog(
    path: Path = CHANGELOG_PATH, fragments_dir: Path = FRAGMENTS_DIR
) -> Path:
    block = render_unreleased(collect_fragments(fragments_dir))
    text = path.read_text(encoding="utf-8") if path.exists() else _initial()
    path.write_text(_replace_block(text, block), encoding="utf-8")
    return path


# ── 릴리스 컷 (arcsolve release <ver>) ───────────────────────────────────────


def validate_version(version: str) -> str:
    """SemVer 형식을 검증해 반환. 아니면 ValueError."""
    if not _SEMVER_RE.match(version):
        raise ValueError(f"버전 형식이 올바르지 않습니다(SemVer MAJOR.MINOR.PATCH 권장): {version}")
    return version


def set_init_version(version: str, init_path: Path = INIT_PATH) -> None:
    """arcsolve/__init__.py의 __version__을 갱신(버전 단일 출처)."""
    text = init_path.read_text(encoding="utf-8")
    new, n = _VERSION_RE.subn(rf"\g<1>{version}\g<2>", text)
    if n != 1:
        raise ValueError(f"__version__ 라인을 찾지 못했습니다: {init_path}")
    init_path.write_text(new, encoding="utf-8")


def set_server_json_version(version: str, path: Path = SERVER_JSON_PATH) -> bool:
    """MCP 레지스트리 server.json의 version·packages[].version을 갱신(있을 때만).

    server.json의 버전은 PyPI 릴리스 버전과 일치해야 하므로 릴리스 컷에서 함께 올린다.
    반환: 갱신했으면 True(파일 없으면 False).
    """
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    for pkg in data.get("packages", []):
        pkg["version"] = version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _consumed_fragments(fragments_dir: Path) -> list[Path]:
    return [p for p in sorted(fragments_dir.glob("*.md")) if p.name.lower() != "readme.md"]


def cut_release(
    version: str,
    date: str,
    path: Path = CHANGELOG_PATH,
    fragments_dir: Path = FRAGMENTS_DIR,
    delete_fragments: bool = True,
) -> list[str]:
    """[Unreleased] 조각을 `## [version] - date` 섹션으로 확정하고 Unreleased를 비운다.

    소비한 changelog.d 조각 파일을 삭제(다음 사이클에 다시 쌓이지 않게). 반환은 소비된 조각 파일명.
    조각이 없으면 ValueError. BEGIN/END 마커 위쪽(머리말)·아래쪽(과거 릴리스 섹션)은 보존된다.
    """
    body = collect_fragments(fragments_dir)
    if not body.strip():
        raise ValueError("릴리스할 changelog.d 조각이 없습니다.")
    text = path.read_text(encoding="utf-8") if path.exists() else _initial()
    version_section = f"## [{version}] - {date}\n\n{body}"
    path.write_text(
        _replace_block(text, f"{render_unreleased('')}\n\n{version_section}"), encoding="utf-8"
    )
    consumed: list[str] = []
    if delete_fragments:
        for p in _consumed_fragments(fragments_dir):
            consumed.append(p.name)
            p.unlink()
    return consumed
