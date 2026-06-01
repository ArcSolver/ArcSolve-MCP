"""서비스 카탈로그 자동 생성.

ALL_SERVICES와 각 서비스가 등록하는 도구를 introspect해서 docs/services.md를 만든다.
손으로 갱신하지 않는다 — `arcsolve-mcp catalog`로 재생성한다.
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from arcsolve.services import discover_services

CATALOG_PATH = Path(__file__).resolve().parent.parent / "docs" / "services.md"


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
        "> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve-mcp catalog`로 재생성됩니다.",
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
