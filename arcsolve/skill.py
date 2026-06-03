"""스킬의 균일 계약 + 자동 발견.

스킬은 import되는 코드가 아니라 **배포되는 데이터**다 — 레포 루트 `skills/<name>/SKILL.md`를
스캔해 frontmatter(`name`·`description`·`allowed-tools`)에서 `Skill`을 만든다.

MCP 서비스가 `contract.py`로 "API가 무엇인가"를 박제하듯, 스킬은 `SKILL.md`로 "그 도구를
어떻게 엮는가"를 담는다. 재사용은 **도구 경계**에서 일어난다: 스킬은 실행 중인 MCP 도구를
오케스트레이션할 뿐 `contract.py`를 import하지 않는다(AGENTS.md 규칙 2-2).

frontmatter 파서는 표준 라이브러리만 쓰는 **최소 YAML 부분집합**이다(우리 통제 포맷 한정):
`key: value`(문자열)·`key: [a, b]`(인라인 리스트)·블록 리스트(`key:` 다음 줄들이 `- item`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# 레포 루트의 skills/ — 패키지(arcsolve/) 바깥의 데이터 트리.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass(frozen=True)
class Skill:
    name: str                          # 폴더명 = frontmatter name
    description: str                   # 공개 약속(트리거) — "무엇을 + 언제"
    tools: tuple[str, ...] = ()         # allowed-tools: 오케스트레이션할 MCP 도구명
    path: Path | None = None


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _split_frontmatter(text: str) -> str:
    """선두 `---` ... `---` 블록만 반환. 없으면 빈 문자열."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return ""


def parse_frontmatter(text: str) -> dict:
    """SKILL.md frontmatter를 dict로(최소 YAML 부분집합)."""
    data: dict = {}
    key: str | None = None
    for raw in _split_frontmatter(text).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 블록 리스트 항목: 들여쓰기 + "- "
        if raw[:1] in (" ", "\t") and stripped.startswith("- ") and key is not None:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(_unquote(stripped[2:]))
            continue
        if ":" not in raw:
            continue
        k, _, v = raw.partition(":")
        key = k.strip()
        v = v.strip()
        if v == "":
            data[key] = []  # 블록 리스트가 이어질 수 있음
        elif v.startswith("[") and v.endswith("]"):
            data[key] = [_unquote(x) for x in v[1:-1].split(",") if x.strip()]
        else:
            data[key] = _unquote(v)
    return data


def _as_tools(val: object) -> tuple[str, ...]:
    """allowed-tools를 도구명 튜플로(리스트·콤마 문자열 모두 허용)."""
    if val is None:
        return ()
    if isinstance(val, str):
        return tuple(t.strip() for t in val.split(",") if t.strip())
    if isinstance(val, (list, tuple)):
        return tuple(str(t).strip() for t in val if str(t).strip())
    return ()


def available() -> list[str]:
    """등록된 스킬 이름 — SKILL.md를 가진 폴더만 스캔(import 없음)."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").exists())


def load_skill(name: str) -> Skill | None:
    """스킬 하나를 SKILL.md frontmatter에서 로드. 없으면 None."""
    skill_md = SKILLS_DIR / name / "SKILL.md"
    if not skill_md.exists():
        return None
    fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    return Skill(
        name=str(fm.get("name") or name),
        description=str(fm.get("description", "")),
        tools=_as_tools(fm.get("allowed-tools")),
        path=SKILLS_DIR / name,
    )


def discover_skills() -> list[Skill]:
    """로드 가능한 모든 스킬(빈 SKILL.md는 스킵)."""
    loaded = (load_skill(n) for n in available())
    return sorted((s for s in loaded if s is not None), key=lambda s: s.name)
