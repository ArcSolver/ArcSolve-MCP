"""messaging-routing 스킬 — 정적 불변식(네트워크·모델 없음)."""

from arcsolve.skill import load_skill

REQUIRED_TOOLS = {
    "kakao_send_text_to_me",
    "telegram_send_message",
    "discord_send_message",
    "line_send_text",
}

# 라우팅 = 여러 메시징 채널 교차. 단일 채널이 아님을 보장.
REQUIRED_PREFIXES = {"kakao_", "telegram_", "discord_", "line_"}


def test_skill_loads_with_expected_name():
    s = load_skill("messaging-routing")
    assert s is not None
    assert s.name == "messaging-routing"
    assert s.description.strip()


def test_orchestrates_all_four_channels():
    s = load_skill("messaging-routing")
    missing = REQUIRED_TOOLS - set(s.tools)
    assert not missing, f"메시징 핵심 도구 누락: {missing}"


def test_spans_multiple_channels():
    s = load_skill("messaging-routing")
    covered = {p for p in REQUIRED_PREFIXES if any(t.startswith(p) for t in s.tools)}
    assert covered == REQUIRED_PREFIXES, f"가로지르지 못한 채널: {REQUIRED_PREFIXES - covered}"
