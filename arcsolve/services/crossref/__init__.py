from arcsolve.service import Service
from arcsolve.services.crossref.tools import register

SERVICE = Service(
    name="crossref",
    register=register,
    docs_url="https://github.com/CrossRef/rest-api-doc/blob/master/README.md",
    summary="Crossref 학술 메타데이터 읽기(works/journals 검색·조회)",
    # 무인증(키 없음) — polite pool은 선택 mailto 쿼리 파라미터. 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
