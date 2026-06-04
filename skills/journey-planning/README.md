# journey-planning (여정 계획 — 한국)

한국 내 이동을 **실시간·문전(door-to-door)**으로 묶는 **다중 서비스 오케스트레이션** 스킬: 지하철·버스
도착, 고속/시외버스·열차, 인천공항 운항, 따릉이, 그리고 목적지의 주차 잔여·EV 충전 상태를 한 계획으로
정리한다. `situational-awareness`와 같은 결의 교차서비스 스킬이며, 대상은 **한국**이다.

> 이 스킬은 상류 API를 직접 치지 않고 **ArcSolve MCP 도구를 오케스트레이션**한다(AGENTS.md 규칙 2-2).
> 검증된 계약은 각 서비스의 `contract.py`에 단일 출처로 남는다.

## 계약 출처 (공식 문서)
스킬이 기대는 MCP 서비스들의 검증된 계약:
- 서울 실시간 교통(지하철·따릉이): https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
- TAGO 전국 대중교통(버스·열차, data.go.kr): https://www.data.go.kr/data/15098530/openapi.do
- 인천공항 운항현황(data.go.kr): https://www.data.go.kr/data/15140153/openapi.do
- 전국 주차장 정보(data.go.kr): https://www.data.go.kr/data/15099883/openapi.do
- 전기차 충전소(data.go.kr): https://www.data.go.kr/data/15076352/openapi.do

## 필요 MCP 도구
ArcSolve MCP 서버에서 아래 도구가 노출돼 있어야 한다(`SKILL.md`의 `allowed-tools`와 일치):
- 서울 교통 — `seoul_subway_arrivals`, `seoul_bike_status`
- TAGO — `tago_search_bus_stops`, `tago_bus_arrivals`, `tago_bus_route`, `tago_express_bus`, `tago_intercity_bus`, `tago_train`, `tago_city_codes`
- 인천공항 — `airport_arrivals`, `airport_departures`
- 주차 — `parking_search`, `parking_realtime`
- 충전 — `ev_charger_status`, `ev_charger_info`

> 셋업: `arcsolve serve seoul_transit tago_transit airport parking ev_charger`. 모두 data.go.kr/서울
> 열린데이터 서비스키가 필요하다(각 서비스 README의 환경변수 참고).

## 범위 / 경계
- **포함**: 구간별 실시간 도착(지하철·버스)·고속/시외버스·열차·공항 운항·따릉이 + 목적지 주차 잔여·EV 충전 상태를 한 계획으로 통합.
- **읽기 전용·정보 제공**: 예약·결제·발권을 하지 않는다. 경로 최적화 엔진이 아니라 공식 출처의 도착/시간표를 보고한다(임의 소요시간 생성 X).
- **한국 한정**: 한국 공공데이터 서비스.
- **제외(다른 스킬)**: 경로 상의 날씨·미세먼지는 `situational-awareness`로, 계획 전송은 메시징 도구로 **안내만**(직접 수행 X).

## 품질 검증
- 정적 테스트: [`tests/test_journey_planning_skill.py`](../../tests/test_journey_planning_skill.py)
  — frontmatter·`allowed-tools`↔실재 도구·다중 서비스 교차 불변식.
- eval: [`evals/`](evals/) — skill-creator 하니스(비결정적, pytest CI와 별개).
