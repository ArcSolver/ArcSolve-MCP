from arcsolve.service import Service
from arcsolve.services.openalex.tools import register

SERVICE = Service(
    name="openalex",
    register=register,
    docs_url="https://developers.openalex.org/how-to-use-the-api/api-overview",
    summary="OpenAlex 학술 그래프 읽기(works/authors 검색·조회)",
    # API 키는 선택 쿼리 파라미터(키 없이도 동작) — 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
