"""academic-discovery 스킬 — 정적 불변식(네트워크·모델 없음)."""

from arcsolve.skill import load_skill

# 다섯 출처의 '검색' 도구가 모두 오케스트레이션 대상이어야 한다(멀티소스 탐색의 전제).
CORE_SEARCH = {
    "arxiv_search",
    "crossref_search_works",
    "openalex_search_works",
    "pubmed_search",
    "s2_search_papers",
}


def test_skill_loads_with_expected_name():
    s = load_skill("academic-discovery")
    assert s is not None
    assert s.name == "academic-discovery"
    assert s.description.strip()


def test_orchestrates_core_search_tools_of_all_sources():
    s = load_skill("academic-discovery")
    missing = CORE_SEARCH - set(s.tools)
    assert not missing, f"코어 검색 도구 누락: {missing}"


def test_references_file_resolves():
    s = load_skill("academic-discovery")
    assert (s.path / "references" / "sources.md").exists()
