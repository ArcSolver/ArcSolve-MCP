# USGS Earthquake 서비스

USGS FDSN Event Web Service 지진 정보 **읽기** 래퍼 — 지진 이벤트 검색·건수 조회.
전부 GET·읽기. 응답은 `format=geojson` 고정(검색=GeoJSON FeatureCollection, 건수=`{count,maxAllowed}`). **무인증**(키 없음).

## 계약 출처 (공식 문서)
- FDSN Event API 명세(엔드포인트·전체 쿼리 파라미터·기본/제약·orderby·format·시간형식·에러): https://earthquake.usgs.gov/fdsnws/event/1/
- 실시간 피드(GeoJSON) 안내(`properties` 필드 의미 — mag/place/time/url 등): https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
- 라이브 응답 확인: `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson` · `/count?format=geojson`

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 상수·쿼리 제약·GeoJSON 응답 모델).

## 인증 (없음)
USGS FDSN Event API는 **무인증**이다(API 키·env 불필요). 식별용 User-Agent 헤더만 전송한다.

- base `https://earthquake.usgs.gov/fdsnws/event/1`. 응답 포맷은 항상 `format=geojson`.
- 건수/페이지네이션 정보가 모두 **응답 본문**(FeatureCollection의 `metadata`·`features` 길이, count의 `count`)에 있으므로 코어 `get_json`만 쓴다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 종류 | METHOD · PATH |
|------|------|
| 지진 검색/나열 | `GET /query?format=geojson&starttime=&endtime=&minmagnitude=&...` |
| 지진 건수 | `GET /count?format=geojson&starttime=&...` |

Base: `https://earthquake.usgs.gov/fdsnws/event/1` · 인증: 없음 · 스코프: 읽기 전용

> 시간은 **ISO8601**(`2024-01-01` 또는 `2024-01-01T00:00:00`, 미지정 시 UTC). `limit`은 1–20000(기본 20). `orderby`는 `time`(기본·최신순)/`time-asc`/`magnitude`(큰 규모순)/`magnitude-asc`. 위치(원형) 검색은 `latitude`+`longitude`+`maxradiuskm`(0–20001.6 km)를 한 묶음으로 준다.
> 검색 응답 봉투: `{type:"FeatureCollection", metadata:{...}, features:[{properties:{mag,place,time,url,...}, geometry:{coordinates:[lon,lat,depth]}, id},...]}`. `time`은 **밀리초 epoch**, `coordinates`는 **[경도, 위도, 깊이(km)]** 순서(GeoJSON 규약). 건수 응답: `{"count":N, "maxAllowed":20000}`.

## 셋업
1. 키 발급 단계 없음(무인증).
2. `.env` 변경 불필요.

> 무인증 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth usgs_quake` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `usgs_search_earthquakes(starttime?, endtime?, minmagnitude?, maxmagnitude?, latitude?, longitude?, maxradiuskm?, limit?, orderby?)` | 지진 이벤트 검색/나열. 각 결과: 규모·위치·발생시각(UTC)·좌표·깊이·이벤트 URL. limit 기본 20·1..20000 |
| `usgs_count_earthquakes(starttime?, endtime?, minmagnitude?, maxmagnitude?, latitude?, longitude?, maxradiuskm?)` | 동일 조건의 매칭 건수만 반환(`{count,maxAllowed}`) |

## 범위 / 제약 (공식)
- **읽기만.** 지진 검색·건수 조회만(MVP).
- 제외: QuakeML/CSV/KML/text/xml 포맷(geojson 고정), 실시간 요약 피드 파일(`feed/v1.0/...geojson`), 상세 detail product, `eventid` 단건 상세, rectangle(min/max lat·lon) 위치 검색, `offset`/`mindepth`/`maxdepth`/`reviewstatus` 등 부가 필터.
- `limit` 1–20000(초과 시 400 Bad Request). `orderby`=time/time-asc/magnitude/magnitude-asc. 원형 위치는 `latitude`+`longitude`+`maxradiuskm`(maxradiuskm ≤ 20001.6). 시간 미지정 시 기본 범위는 NOW-30일~현재.

## UNVERIFIED / provenance 노트
- `properties.time`/`updated`는 **밀리초 epoch**(라이브 확인) → 도구가 UTC ISO8601로 변환해 표기한다.
- `geometry.coordinates`는 GeoJSON 규약대로 **[경도, 위도, 깊이(km)]** 순서(위도가 먼저가 아님)다. 도구 출력은 사람이 읽기 쉽게 `위도, 경도 (depth km)`로 재배열한다.
- `format=geojson`일 때 결과 없음은 **HTTP 200 + 빈 `features`**다(`nodata` 204를 쓰지 않음 — 라이브 확인). 에러 본문은 **text/plain**(`Error 400: Bad Request\n\n...`)이라 JSON으로 파싱하지 않고 첫 의미 줄만 노출한다.

## 확장 포인트
- rectangle 위치(`minlatitude`/`maxlatitude`/`minlongitude`/`maxlongitude`), `eventid` 단건 상세, `offset` 페이지네이션, `mindepth`/`maxdepth`/`reviewstatus` 필터는 동일 패턴으로 contract 상수·도구 파라미터 추가. QuakeML/CSV 등 비-JSON 포맷은 코어 `get_text` 동사가 필요하다.
