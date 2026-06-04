# situational-awareness (상황인지 — 한국)

한 장소의 **지금 상황**을 하나의 그림으로 묶는 **다중 서비스 오케스트레이션** 스킬: 위치를 한 번
지오코딩한 뒤 날씨(Open-Meteo)·실시간 대기질/미세먼지(에어코리아)·응급실 가용병상(E-Gen)을
가로질러 읽어 하나의 readout으로 정리한다. `academic-discovery`(학술 멀티소스)와 같은 결의
교차서비스 스킬이며, 대상 도메인은 **한국**이다(에어코리아·E-Gen이 한국 공공데이터).

> 이 스킬은 상류 API를 직접 치지 않고 **ArcSolve MCP 도구를 오케스트레이션**한다(AGENTS.md 규칙 2-2).
> 검증된 계약은 각 서비스의 `contract.py`에 단일 출처로 남는다(스킬은 계약을 재정의하지 않는다).

## 계약 출처 (공식 문서)
스킬이 기대는 MCP 서비스들의 검증된 계약:
- Open-Meteo(날씨·지오코딩): https://open-meteo.com/en/docs
- 에어코리아(한국환경공단 대기오염정보, data.go.kr): https://www.data.go.kr/data/15073861/openapi.do
- E-Gen(국립중앙의료원 응급의료정보, data.go.kr): https://www.data.go.kr/data/15000563/openapi.do

## 필요 MCP 도구
ArcSolve MCP 서버에서 아래 도구가 노출돼 있어야 한다(`SKILL.md`의 `allowed-tools`와 일치):
- Open-Meteo — `openmeteo_geocode`, `openmeteo_forecast`
- 에어코리아 — `airkorea_realtime_by_region`, `airkorea_realtime_by_station`, `airkorea_forecast`
- E-Gen — `egen_realtime_beds`, `egen_severe_acceptance`, `egen_list`

> 셋업: `arcsolve serve openmeteo airkorea egen` (또는 `ARCSOLVE_SERVICES=openmeteo,airkorea,egen`).
> Open-Meteo는 무인증, 에어코리아·E-Gen은 data.go.kr 서비스키가 필요하다(각 서비스 README의 환경변수 참고).

## 범위 / 경계
- **포함**: 장소 지오코딩 → 현재/예보 날씨 + 실시간 미세먼지(PM10/PM2.5) 등급 + (필요시) 응급실
  실시간 가용병상·중증질환 수용가능·기관 목록을 하나의 상황 readout으로 통합.
- **읽기 전용·정보 제공**: 의료 트리아지·진단·"이 병원으로 가라" 지시를 하지 않는다 — 응급실 정보는
  사실로 제시하고 응급 시 **119**를 안내한다. 미세먼지/날씨도 데이터만 제시하고 임의 기준을 만들지 않는다.
- **한국 한정**: 에어코리아·E-Gen은 한국 데이터. 미국 기상특보는 `nws_*`를 쓴다(이 스킬 범위 밖).
- **제외(다른 스킬)**: 알림 전송은 메시징 도구(`telegram_*`·`discord_*`·`kakao_*`)로 **안내만**(직접 수행 X).

## 품질 검증
- 정적 테스트: [`tests/test_situational_awareness_skill.py`](../../tests/test_situational_awareness_skill.py)
  — frontmatter·`allowed-tools`↔실재 도구·3개 서비스 교차 불변식.
- eval: [`evals/`](evals/) — skill-creator 하니스(비결정적, pytest CI와 별개).
