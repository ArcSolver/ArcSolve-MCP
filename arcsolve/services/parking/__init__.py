from arcsolve.service import Service
from arcsolve.services.parking.tools import register

SERVICE = Service(
    name="parking",
    register=register,
    docs_url="https://www.data.go.kr/data/15099883/openapi.do",
    summary="한국교통안전공단 전국 주차장 정보 읽기(시설·운영 + 실시간 잔여면 ⭐ 연동 주차장 한정)",
    # 서비스키는 쿼리 파라미터 serviceKey(사전발급, **Decoding 키**) — 인터랙티브 OAuth 아님
    # → make_auth_client 없음. 단일 키로 B553881/Parking의 3개 오퍼레이션 전부 커버.
)
