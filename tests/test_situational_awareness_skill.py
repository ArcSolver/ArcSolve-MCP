"""situational-awareness 스킬 — 정적 불변식(네트워크·모델 없음)."""

from arcsolve.skill import load_skill

# 교차서비스 상황인지의 전제: 날씨·대기질·응급실 세 서비스의 핵심 도구가 모두 오케스트레이션 대상.
REQUIRED_TOOLS = {
    "openmeteo_geocode",
    "openmeteo_forecast",
    "airkorea_realtime_by_region",
    "egen_realtime_beds",
}

# 도구가 걸쳐야 하는 서비스 prefix(단일소스가 아니라 멀티서비스임을 보장).
REQUIRED_PREFIXES = {"openmeteo_", "airkorea_", "egen_"}


def test_skill_loads_with_expected_name():
    s = load_skill("situational-awareness")
    assert s is not None
    assert s.name == "situational-awareness"
    assert s.description.strip()


def test_orchestrates_all_three_domains():
    s = load_skill("situational-awareness")
    missing = REQUIRED_TOOLS - set(s.tools)
    assert not missing, f"상황인지 핵심 도구 누락: {missing}"


def test_spans_multiple_services():
    # 멀티서비스 스킬: 도구가 세 서비스 prefix를 모두 가로질러야 한다(단일소스 금지).
    s = load_skill("situational-awareness")
    covered = {p for p in REQUIRED_PREFIXES if any(t.startswith(p) for t in s.tools)}
    assert covered == REQUIRED_PREFIXES, f"가로지르지 못한 서비스: {REQUIRED_PREFIXES - covered}"
