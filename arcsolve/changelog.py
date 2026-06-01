"""changelog.d/ 조각을 단일 CHANGELOG.md의 [Unreleased] 섹션으로 합본한다.

각 서비스 에이전트는 `changelog.d/<name>.md`에 자기 변경만 적고(병렬 충돌 없음),
통합 단계에서 `arcsolve-mcp changelog`로 합본한다. 마커 사이만 교체하므로 릴리즈된
버전 섹션은 보존된다.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAGMENTS_DIR = ROOT / "changelog.d"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

BEGIN = "<!-- BEGIN UNRELEASED -->"
END = "<!-- END UNRELEASED -->"


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
