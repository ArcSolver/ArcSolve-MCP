from arcsolve.service import Service
from arcsolve.services.wikidata.tools import register

SERVICE = Service(
    name="wikidata",
    register=register,
    docs_url="https://www.wikidata.org/wiki/Wikidata:Data_access",
    summary="Wikidata 읽기(엔티티 검색·단건 조회·statements·SPARQL)",
    # 무인증(키 없음) — 단 식별 가능한 User-Agent 필수(기본값 contract.DEFAULT_USER_AGENT,
    # WIKIDATA_USER_AGENT로 덮어씀). (선택) WIKIDATA_API_TOKEN Bearer로 레이트리밋 완화.
    # 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
