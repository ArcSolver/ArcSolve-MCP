"""info-gathering 스킬 — 정적 불변식(네트워크·모델 없음)."""

from arcsolve.skill import load_skill

REQUIRED_TOOLS = {"feeds_fetch", "hn_top", "hn_search"}
REQUIRED_PREFIXES = {"feeds_", "hn_"}


def test_skill_loads_with_expected_name():
    s = load_skill("info-gathering")
    assert s is not None
    assert s.name == "info-gathering"
    assert s.description.strip()


def test_orchestrates_feeds_and_hackernews():
    s = load_skill("info-gathering")
    missing = REQUIRED_TOOLS - set(s.tools)
    assert not missing, f"정보수집 핵심 도구 누락: {missing}"


def test_spans_both_sources():
    s = load_skill("info-gathering")
    covered = {p for p in REQUIRED_PREFIXES if any(t.startswith(p) for t in s.tools)}
    assert covered == REQUIRED_PREFIXES, f"가로지르지 못한 서비스: {REQUIRED_PREFIXES - covered}"
