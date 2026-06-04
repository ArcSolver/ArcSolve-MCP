"""서비스 카탈로그 자동 생성.

ALL_SERVICES와 각 서비스가 등록하는 도구를 introspect해서 docs/services.md를 만든다.
손으로 갱신하지 않는다 — `arcsolve catalog`로 재생성한다.
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from arcsolve.services import discover_services
from arcsolve.skill import discover_skills

CATALOG_PATH = Path(__file__).resolve().parent.parent / "docs" / "services.md"
SKILLS_CATALOG_PATH = Path(__file__).resolve().parent.parent / "docs" / "skills.md"


def _first_line(text: str | None) -> str:
    text = (text or "").strip()
    return text.splitlines()[0] if text else ""


async def build_catalog() -> list[dict]:
    """각 서비스를 빈 서버에 등록해 도구 목록을 수집한다."""
    catalog: list[dict] = []
    for svc in discover_services():
        probe = FastMCP(svc.name)
        svc.register(probe)
        tools = await probe.list_tools()
        catalog.append(
            {
                "name": svc.name,
                "summary": svc.summary,
                "docs_url": svc.docs_url,
                "tools": sorted(
                    (
                        {"name": t.name, "description": _first_line(getattr(t, "description", ""))}
                        for t in tools
                    ),
                    key=lambda d: d["name"],
                ),
            }
        )
    return catalog


def render_markdown(catalog: list[dict]) -> str:
    total_tools = sum(len(s["tools"]) for s in catalog)
    lines = [
        "# 서비스 카탈로그",
        "",
        "> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve catalog`로 재생성됩니다.",
        "",
        f"현재 **{len(catalog)}개 서비스 · 총 {total_tools}개 도구**.",
        "",
    ]
    for s in catalog:
        title = f"## {s['name']}"
        if s["summary"]:
            title += f" — {s['summary']}"
        lines.append(title)
        if s["docs_url"]:
            lines.append(f"공식 문서: {s['docs_url']}")
        lines += ["", "| 도구 | 설명 |", "|------|------|"]
        lines += [f"| `{t['name']}` | {t['description']} |" for t in s["tools"]]
        lines.append("")
    return "\n".join(lines)


async def write_catalog(path: Path = CATALOG_PATH) -> Path:
    md = render_markdown(await build_catalog())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md + "\n", encoding="utf-8")
    return path


# ── 스킬 카탈로그 ────────────────────────────────────────────────────────────
# 스킬은 실행 중인 MCP 도구를 오케스트레이션한다(검증된 계약은 MCP 서비스 쪽 단일 출처).
# 도구 introspection이 필요 없어 동기 함수다.

def build_skills_catalog() -> list[dict]:
    return [
        {"name": s.name, "description": s.description, "tools": list(s.tools)}
        for s in discover_skills()
    ]


def render_skills_markdown(catalog: list[dict]) -> str:
    lines = [
        "# 스킬 카탈로그",
        "",
        "> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve catalog`로 재생성됩니다.",
        "",
        f"현재 **{len(catalog)}개 스킬**. 스킬은 실행 중인 MCP 도구를 오케스트레이션한다"
        "(검증된 계약은 MCP 서비스 쪽 단일 출처).",
        "",
    ]
    for s in catalog:
        lines.append(f"## {s['name']}")
        if s["description"]:
            lines += ["", s["description"]]
        if s["tools"]:
            tools = ", ".join(f"`{t}`" for t in s["tools"])
            lines += ["", f"오케스트레이션 도구: {tools}"]
        lines.append("")
    return "\n".join(lines)


def write_skills_catalog(path: Path = SKILLS_CATALOG_PATH) -> Path:
    md = render_skills_markdown(build_skills_catalog())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md + "\n", encoding="utf-8")
    return path
