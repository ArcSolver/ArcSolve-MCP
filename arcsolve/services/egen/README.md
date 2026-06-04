# E-Gen(응급의료정보) 서비스

국립중앙의료원 중앙응급의료센터 **전국 응급의료기관 정보 조회 서비스**(ErmctInfoInqireService)
**읽기** 래퍼 — 응급실 실시간 가용병상·중증질환자 수용가능·응급의료기관 목록. 전부 GET·**XML**.
**서비스키 필수**(공공데이터포털 발급), 키는 **쿼리 파라미터 `serviceKey`**다(OAuth 아님).

## 계약 출처 (공식 문서)
- 국립중앙의료원_전국 응급의료기관 정보 조회 서비스(ErmctInfoInqireService) 상세: https://www.data.go.kr/data/15000563/openapi.do
- 중앙응급의료센터 Open API 안내: https://www.e-gen.or.kr/nemc/open_api.do

> base `http://apis.data.go.kr/B552657/ErmctInfoInqireService`. 공통 파라미터(serviceKey·STAGE1·STAGE2·numOfRows·pageNo), 봉투 구조(`response.header`/`response.body.items.item`), 오퍼레이션별 응답 필드는 위 data.go.kr 상세 페이지에서 확인된다. **응답 포맷은 XML**이다(`_type=json` 지원은 공식 확인 불가 — XML로 받아 표준 라이브러리 파싱).
>
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로·쿼리 빌더·XML 파서·응답 모델).

## 인증 (필수)
`EgenSettings`(`EGEN_*`)가 서비스키를 로드한다. **헤더가 아니라 쿼리 파라미터**다.

| env | 쿼리 파라미터 | 비고 |
|---|---|---|
| `EGEN_SERVICE_KEY` | `serviceKey=<키>` | 필수. data.go.kr에서 발급 |

> ⚠️ **Decoding 키(원문)를 넣으세요.** data.go.kr 서비스키는 **Encoding/Decoding 2종**으로 발급됩니다. httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, 이미 인코딩된 키를 넣으면 **이중 인코딩**되어 `등록되지 않은 서비스키(30)` 오류가 납니다. 반드시 **Decoding 키(원문)**를 사용하세요.
> 키가 없으면 HTTP 호출 전에 안내 문자열을 반환합니다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 도구 | METHOD · PATH |
|------|------|
| 응급실 실시간 가용병상 | `GET /getEmrrmRltmUsefulSckbdInfoInqire?STAGE1=&STAGE2=&numOfRows=&pageNo=` |
| 중증질환자 수용가능 | `GET /getSrsillDissAceptncPosblInfoInqire?STAGE1=&STAGE2=&numOfRows=&pageNo=` |
| 응급의료기관 목록 | `GET /getEgytListInfoInqire?STAGE1=&STAGE2=&numOfRows=&pageNo=` |

> 응답 봉투(XML): `<response><header><resultCode/><resultMsg/></header><body><items><item>...</item></items><totalCount/><pageNo/><numOfRows/></body></response>`. **`resultCode != "00"`이면 에러**(서비스키 오류 등) — HTTP 200이라도 봉투로 온다. 가용병상수(`hvec` 등)는 정수 문자열, 가용여부(`hvctayn` 등)는 `Y`/`N`이며 결측은 빈 값/`-`/`N` → **전부 문자열로 받고 캐스팅하지 않는다.**

## 셋업
1. [공공데이터포털 응급의료정보 OpenAPI](https://www.data.go.kr/data/15000563/openapi.do)에서 활용 신청 → **Decoding 서비스키** 확인.
2. `.env`:
   - `EGEN_SERVICE_KEY=<Decoding 키>`

> 서비스키는 사전발급 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth egen` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `egen_realtime_beds(stage1, stage2?, numOfRows?, pageNo?)` | 응급실 실시간 가용병상. 기관별 응급실·수술실·중환자실·입원실 가용수 + CT/MRI/인공호흡기/구급차 가용여부 |
| `egen_severe_acceptance(stage1, stage2?, numOfRows?, pageNo?)` | 중증질환자 수용가능(심근경색·뇌출혈·중증화상 등 MKioskTy 단말 표시 기준). 수용 가능('Y') 항목을 추려 표시 |
| `egen_list(stage1, stage2?, numOfRows?, pageNo?)` | 응급의료기관 목록. 기관명·주소·전화(대표/응급실)·분류·위경도 |

> `stage1`/`stage2`는 **한글 시도/시군구명**(예: `서울특별시`, `강남구`). `stage2` 생략 시 시도 전체.

## 범위 / 제약 (공식)
- **읽기만.** 응급실 실시간 가용병상 + 중증질환 수용가능 + 응급의료기관 목록(MVP).
- 제외: 외상센터(getStrmListInfoInqire 등)·중증응급질환별 메시지·AED·약국·기관 위치/기본정보 등 별도 오퍼레이션.
- 페이지네이션: `numOfRows`(기본 100)·`pageNo`(기본 1) — 건수/페이지는 응답 **본문**(`body.totalCount/pageNo`)에 실린다.

## UNVERIFIED / provenance 노트
- **응답 포맷**: data.go.kr 상세 페이지의 출력 예시·활용가이드가 **XML** 기준이며 `_type=json` 지원 여부를 공식 확인할 수 없어, 안전하게 XML로 받아(`get_text`) 표준 라이브러리(`xml.etree.ElementTree`)로 파싱한다(arxiv 패턴).
- **중증질환 수용가능(MKioskTy)**: `getSrsillDissAceptncPosblInfoInqire`의 `MKioskTy1~28` 각 슬롯이 매핑하는 정확한 중증질환 항목명과 전체 개수는 data.go.kr 상세 페이지의 **다운로드 활용가이드(.hwp)**에만 표로 있어 인라인 확인이 어렵다. 개별 `MKioskTy` 필드를 고정 모델링하지 않고 `mkiosk` dict(라벨=값)로 느슨히 받아 항목 변경을 흡수한다(`contract.py`의 `TODO(provenance)` 참고).
- 실시간 가용병상 필드(`hvec`·`hvoc`·`hvctayn` 등)는 data.go.kr 상세 페이지의 출력 예시에서 한글 설명과 함께 확인된 것만 모델링했고, 응답 모델은 `extra="ignore"`로 느슨히 받아 오퍼레이션/버전차를 흡수한다.

## 확장 포인트
- 외상센터 목록(`getStrmListInfoInqire`)·기관 위치(`getEgytLcinfoInqire`)·기본정보(`getEgytBassInfoInqire`)는 동일 패턴으로 경로 상수·XML 파서·도구를 추가.
