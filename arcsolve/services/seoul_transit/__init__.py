from arcsolve.service import Service
from arcsolve.services.seoul_transit.tools import register

SERVICE = Service(
    name="seoul_transit",
    register=register,
    docs_url="https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do",
    summary="서울 실시간 교통 읽기(지하철 도착·따릉이 대여소)",
    # 인증키는 URL path 세그먼트(사전발급) — 인터랙티브 OAuth 아님 → make_auth_client 없음.
    # ⚠️ 인증키 2종 분리: 지하철=SEOUL_SUBWAY_API_KEY, 따릉이=SEOUL_OPENDATA_API_KEY.
)
