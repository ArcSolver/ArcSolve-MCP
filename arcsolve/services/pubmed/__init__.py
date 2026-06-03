from arcsolve.service import Service
from arcsolve.services.pubmed.tools import register

SERVICE = Service(
    name="pubmed",
    register=register,
    docs_url="https://www.ncbi.nlm.nih.gov/books/NBK25500/",
    summary="PubMed(NCBI E-utilities) 생의학 문헌 읽기(검색·요약·abstract)",
    # API 키는 선택 쿼리 파라미터(키 없이도 3 req/s로 동작) — 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
