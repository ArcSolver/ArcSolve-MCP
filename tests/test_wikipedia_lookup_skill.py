"""wikipedia-lookup 스킬 — 정적 불변식(네트워크·모델 없음)."""

from arcsolve.skill import load_skill

# 단일소스 조회의 전제: 위키백과 읽기 도구 4종이 모두 오케스트레이션 대상이어야 한다.
REQUIRED_TOOLS = {
    "wikipedia_search",
    "wikipedia_summary",
    "wikipedia_extract",
    "wikipedia_links",
}


def test_skill_loads_with_expected_name():
    s = load_skill("wikipedia-lookup")
    assert s is not None
    assert s.name == "wikipedia-lookup"
    assert s.description.strip()


def test_orchestrates_wikipedia_read_tools():
    s = load_skill("wikipedia-lookup")
    missing = REQUIRED_TOOLS - set(s.tools)
    assert not missing, f"위키백과 읽기 도구 누락: {missing}"


def test_single_source_only_wikipedia_tools():
    # 미니멀 단일소스 스킬: wikipedia_ 접두 도구만 오케스트레이션한다.
    s = load_skill("wikipedia-lookup")
    nonwiki = [t for t in s.tools if not t.startswith("wikipedia_")]
    assert not nonwiki, f"단일소스 스킬에 비-wikipedia 도구: {nonwiki}"
