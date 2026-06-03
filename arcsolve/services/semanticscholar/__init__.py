from arcsolve.service import Service
from arcsolve.services.semanticscholar.tools import register

SERVICE = Service(
    name="semanticscholar",
    register=register,
    docs_url="https://api.semanticscholar.org/api-docs/graph",
    summary="Semantic Scholar 학술 그래프 읽기(papers/authors 검색·조회)",
    # API 키는 선택 x-api-key 헤더(키 없이 공유 풀로 동작) — 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
