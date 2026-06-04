"""journey-planning 스킬 — 정적 불변식(네트워크·모델 없음)."""

from arcsolve.skill import load_skill

REQUIRED_TOOLS = {
    "seoul_subway_arrivals",
    "tago_bus_arrivals",
    "tago_train",
    "airport_arrivals",
    "parking_realtime",
    "ev_charger_status",
}

# 여정 = 여러 교통 서비스 교차. 단일 서비스가 아님을 보장.
REQUIRED_PREFIXES = {"seoul_", "tago_", "airport_", "parking_", "ev_charger_"}


def test_skill_loads_with_expected_name():
    s = load_skill("journey-planning")
    assert s is not None
    assert s.name == "journey-planning"
    assert s.description.strip()


def test_orchestrates_core_transit_tools():
    s = load_skill("journey-planning")
    missing = REQUIRED_TOOLS - set(s.tools)
    assert not missing, f"여정 핵심 도구 누락: {missing}"


def test_spans_multiple_transit_services():
    s = load_skill("journey-planning")
    covered = {p for p in REQUIRED_PREFIXES if any(t.startswith(p) for t in s.tools)}
    assert covered == REQUIRED_PREFIXES, f"가로지르지 못한 서비스: {REQUIRED_PREFIXES - covered}"
