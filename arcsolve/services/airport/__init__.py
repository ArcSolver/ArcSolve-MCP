from arcsolve.service import Service
from arcsolve.services.airport.tools import register

SERVICE = Service(
    name="airport",
    register=register,
    docs_url="https://www.data.go.kr/data/15140153/openapi.do",
    summary="인천국제공항 여객편 운항현황 읽기(실시간 출발·도착 — 편명·항공사·시각·터미널·게이트·상태)",
    # 서비스키는 쿼리 파라미터 serviceKey(사전발급, **Decoding 키**) — 인터랙티브 OAuth 아님
    # → make_auth_client 없음. 인천국제공항공사 기관코드 B551177, 여객편 운항현황 상세조회.
)
