"""E-Gen(국립중앙의료원 중앙응급의료센터) 응급의료정보 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, **XML → pydantic 파싱**.
MCP/네트워크 무의존(순수 상수 + pydantic 모델 + 표준 라이브러리 XML 파서).

전부 GET·읽기. 인증은 **서비스키 필수**(data.go.kr 발급) — OAuth가 아니라 **쿼리 파라미터
`serviceKey`**다(헤더 아님). 응답 포맷은 **XML**이다(data.go.kr 상세 페이지의 출력 예시·활용
가이드가 XML 기준이며 `_type=json` 지원은 공식 확인 불가). 그래서 airkorea처럼 봉투
`response.header.resultCode`로 에러를 가르되, 본문은 arxiv처럼 코어 `get_text`(raw str)로 받아
**표준 라이브러리 `xml.etree.ElementTree`**로 파싱한다(feedparser/lxml 같은 외부 의존 금지).

⚠️ data.go.kr 서비스키 함정(airkorea와 동일): 키는 **Encoding/Decoding 2종**으로 발급된다.
httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, params에는 **Decoding 키(원문)**를 넣어 이중
인코딩을 피한다.

⚠️ 측정값 결측: 가용병상수(hvec 등)는 정수 문자열로, 가용여부(hvctayn 등)는 'Y'/'N'으로 온다.
결측은 빈 값/'-'/'N'일 수 있어 **전부 문자열**로 받는다(캐스팅 금지 — airkorea와 동형).

출처(공식 — data.go.kr / e-gen.or.kr):
  - 국립중앙의료원_전국 응급의료기관 정보 조회 서비스(ErmctInfoInqireService) 상세
    (base URL·오퍼레이션·요청 파라미터 STAGE1/STAGE2/pageNo/numOfRows·응답 필드):
    https://www.data.go.kr/data/15000563/openapi.do
  - 중앙응급의료센터 Open API 안내: https://www.e-gen.or.kr/nemc/open_api.do
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from arcsolve.xml import safe_fromstring

from pydantic import BaseModel

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base·오퍼레이션): https://www.data.go.kr/data/15000563/openapi.do
BASE_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService"
# 응급실 실시간 가용병상정보 조회
PATH_REALTIME_BEDS = "/getEmrrmRltmUsefulSckbdInfoInqire"
# 중증질환자 수용가능정보 조회
PATH_SEVERE_ACCEPTANCE = "/getSrsillDissAceptncPosblInfoInqire"
# 응급의료기관 목록정보 조회
PATH_LIST = "/getEgytListInfoInqire"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 공통 파라미터명. 출처: https://www.data.go.kr/data/15000563/openapi.do
PARAM_SERVICE_KEY = "serviceKey"
# 시도(STAGE1)·시군구(STAGE2)는 **한글 주소명**이다(예: STAGE1='서울특별시', STAGE2='강남구').
# 출처: 위 페이지 요청 파라미터(STAGE1 16자·필수, STAGE2 60자·선택).
PARAM_STAGE1 = "STAGE1"
PARAM_STAGE2 = "STAGE2"
PARAM_NUM_OF_ROWS = "numOfRows"
PARAM_PAGE_NO = "pageNo"

# 공통 페이지네이션 기본값. 출처: 위 페이지(numOfRows/pageNo, data.go.kr 공통 규약).
DEFAULT_NUM_OF_ROWS = 100
DEFAULT_PAGE_NO = 1

# 정상 응답 결과코드. 출처: data.go.kr(공통 OpenAPI 에러코드 규약 + 위 페이지 응답 header).
RESULT_CODE_OK = "00"


def _base_params(
    *,
    stage1: str,
    service_key: str,
    stage2: str | None,
    num_of_rows: int,
    page_no: int,
) -> dict[str, str | int]:
    """세 오퍼레이션 공통 쿼리스트링(serviceKey·STAGE1·STAGE2?·페이지네이션).

    serviceKey는 **Decoding 키 원문**을 넣는다(httpx가 자동 인코딩 → 이중 인코딩 방지).
    STAGE1은 필수, STAGE2는 빈 값이면 생략한다(시군구 미지정 → 시도 전체).
    출처: https://www.data.go.kr/data/15000563/openapi.do
    """
    params: dict[str, str | int] = {
        PARAM_SERVICE_KEY: service_key,
        PARAM_STAGE1: stage1,
        PARAM_NUM_OF_ROWS: num_of_rows,
        PARAM_PAGE_NO: page_no,
    }
    if stage2:
        params[PARAM_STAGE2] = stage2
    return params


def build_realtime_beds_params(
    *,
    stage1: str,
    service_key: str,
    stage2: str | None = None,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """응급실 실시간 가용병상(getEmrrmRltmUsefulSckbdInfoInqire) 쿼리스트링을 만든다.

    출처: https://www.data.go.kr/data/15000563/openapi.do
    """
    return _base_params(
        stage1=stage1, service_key=service_key, stage2=stage2,
        num_of_rows=num_of_rows, page_no=page_no,
    )


def build_severe_acceptance_params(
    *,
    stage1: str,
    service_key: str,
    stage2: str | None = None,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """중증질환자 수용가능정보(getSrsillDissAceptncPosblInfoInqire) 쿼리스트링을 만든다.

    출처: https://www.data.go.kr/data/15000563/openapi.do
    """
    return _base_params(
        stage1=stage1, service_key=service_key, stage2=stage2,
        num_of_rows=num_of_rows, page_no=page_no,
    )


def build_list_params(
    *,
    stage1: str,
    service_key: str,
    stage2: str | None = None,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """응급의료기관 목록정보(getEgytListInfoInqire) 쿼리스트링을 만든다.

    출처: https://www.data.go.kr/data/15000563/openapi.do
    """
    return _base_params(
        stage1=stage1, service_key=service_key, stage2=stage2,
        num_of_rows=num_of_rows, page_no=page_no,
    )


# ─── 응답 모델 ──────────────────────────────────────────────
# 봉투(data.go.kr 공통): <response><header><resultCode/><resultMsg/></header>
#   <body><items><item>...</item></items><numOfRows/><pageNo/><totalCount/></body></response>.
# 모든 측정/속성 필드는 **문자열**로 받는다(가용수=정수문자열, 가용여부='Y'/'N', 결측=빈 값/'N').
# extra="ignore"로 느슨히(오퍼레이션별 필드차 흡수).
# 출처: https://www.data.go.kr/data/15000563/openapi.do


class Header(BaseModel):
    """응답 헤더 봉투 `{resultCode, resultMsg}`.

    resultCode != "00"이면 에러(서비스키 오류 등). data.go.kr는 한글/영문 메시지를 섞어 준다.
    출처: 위 페이지 응답 header(resultCode/resultMsg).
    """

    model_config = {"extra": "ignore"}

    resultCode: str | None = None
    resultMsg: str | None = None


class RealtimeBeds(BaseModel):
    """응급실 실시간 가용병상 항목(getEmrrmRltmUsefulSckbdInfoInqire, 부분).

    공식 필드(출처: 위 페이지 응답 — 한글 설명 병기):
      hpid(기관코드) · phpid(구기관코드) · dutyName(기관명) · dutyTel3(응급실전화) ·
      hvidate(입력일시) ·
      가용병상수(정수 문자열): hvec(응급실) · hvoc(수술실) · hvcc(신경중환자) ·
        hvncc(신생중환자) · hvccc(흉부중환자) · hvicc(일반중환자) · hvgc(입원실) ·
        hv2(내과중환자실) · hv3(외과중환자실) · hv4(정형외과입원실) · hv5(신경과입원실) ·
        hv6(신경외과중환자실) · hv7(약물중환자) · hv8(화상중환자) · hv9(외상중환자) ·
        hv10(VENTI 소아) · hv11(인큐베이터) ·
      가용여부('Y'/'N'): hvctayn(CT) · hvmriayn(MRI) · hvangioayn(조영촬영기) ·
        hvventiayn(인공호흡기) · hvamyn(구급차) ·
      당직 연락처: hv1(응급실 당직의 직통) · hv12(소아 당직의 직통) · hvdnm(당직의).
    값은 전부 문자열(결측은 빈 값/'-'/'N'). 캐스팅하지 않는다.
    출처: https://www.data.go.kr/data/15000563/openapi.do
    """

    model_config = {"extra": "ignore"}

    hpid: str | None = None
    phpid: str | None = None
    dutyName: str | None = None
    dutyTel3: str | None = None
    hvidate: str | None = None
    # 가용 병상수(정수 문자열)
    hvec: str | None = None
    hvoc: str | None = None
    hvcc: str | None = None
    hvncc: str | None = None
    hvccc: str | None = None
    hvicc: str | None = None
    hvgc: str | None = None
    hv2: str | None = None
    hv3: str | None = None
    hv4: str | None = None
    hv5: str | None = None
    hv6: str | None = None
    hv7: str | None = None
    hv8: str | None = None
    hv9: str | None = None
    hv10: str | None = None
    hv11: str | None = None
    # 가용 여부('Y'/'N')
    hvctayn: str | None = None
    hvmriayn: str | None = None
    hvangioayn: str | None = None
    hvventiayn: str | None = None
    hvamyn: str | None = None
    # 당직/직통
    hv1: str | None = None
    hv12: str | None = None
    hvdnm: str | None = None


class SevereAcceptance(BaseModel):
    """중증질환자 수용가능정보 항목(getSrsillDissAceptncPosblInfoInqire, 부분).

    기관 식별·입력일시는 실시간 가용병상과 동형(hpid/dutyName/hvidate). 수용 가능/불가는
    `MKioskTy1..MKioskTy28` 슬롯 + 각 슬롯의 라벨 `MKioskTy{n}` 형태로, 응급의료기관 단말
    (E-GEN 키오스크)에 표시되는 중증질환(심근경색·뇌출혈·중증화상 등) 수용 가능 여부를 'Y'/'N'/
    '정보없음'으로 나타낸다. 값은 전부 문자열로 받는다.
    # TODO(provenance): MKioskTy1~28 각 슬롯이 매핑하는 정확한 중증질환 항목명과 전체 개수는
    #   data.go.kr 상세 페이지의 **다운로드 활용가이드(.hwp)**에만 표로 있어 인라인 확인 불가.
    #   따라서 개별 MKioskTy 필드를 고정 모델링하지 않고 extra="ignore" + 원본 dict 보존
    #   (mkiosk)으로 느슨히 받아 버전/항목 변경을 흡수한다. (airkorea ver 필드와 동일한 전략.)
    출처: https://www.data.go.kr/data/15000563/openapi.do
    """

    model_config = {"extra": "ignore"}

    hpid: str | None = None
    dutyName: str | None = None
    dutyTel3: str | None = None
    hvidate: str | None = None
    # MKioskTy* 슬롯은 항목명·개수가 가이드(.hwp) 의존이라 고정 모델링하지 않는다.
    # 파서가 'MKioskTy'로 시작하는 모든 요소를 mkiosk dict에 그대로 담는다(라벨=텍스트).
    mkiosk: dict[str, str] = {}


class Institution(BaseModel):
    """응급의료기관 목록 항목(getEgytListInfoInqire, 부분).

    공식 필드(출처: 위 페이지 응답 — 한글 설명 병기):
      rnum(일련번호) · hpid(기관코드) · dutyName(기관명) · dutyAddr(주소) ·
      dutyTel1(대표전화) · dutyTel3(응급실전화) · dutyEmclsName(응급의료기관 분류명) ·
      wgs84Lon(병원 경도) · wgs84Lat(병원 위도).
    출처: https://www.data.go.kr/data/15000563/openapi.do
    """

    model_config = {"extra": "ignore"}

    rnum: str | None = None
    hpid: str | None = None
    dutyName: str | None = None
    dutyAddr: str | None = None
    dutyTel1: str | None = None
    dutyTel3: str | None = None
    dutyEmclsName: str | None = None
    wgs84Lon: str | None = None
    wgs84Lat: str | None = None


# ─── XML → 모델 파싱 ────────────────────────────────────────
# data.go.kr XML은 네임스페이스가 없는 평면 트리다(<response><header/><body><items><item/>…).
# 출처: https://www.data.go.kr/data/15000563/openapi.do (응답 출력 예시).


def _text(el: ET.Element | None) -> str | None:
    """요소 텍스트를 trim해 돌려준다(없으면 None). 빈 문자열도 None."""
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def parse_header(root: ET.Element) -> Header:
    """봉투 <header>에서 resultCode/resultMsg를 뽑는다(없으면 빈 Header).

    data.go.kr 게이트웨이 키 오류는 <header> 없이 <cmmMsgHeader><returnReasonCode/>로 올 수
    있어, header가 비면 cmmMsgHeader도 훑어 resultCode/resultMsg를 채운다.
    출처: https://www.data.go.kr/data/15000563/openapi.do + data.go.kr 공통 에러 봉투.
    """
    header = root.find("header")
    if header is not None:
        return Header(
            resultCode=_text(header.find("resultCode")),
            resultMsg=_text(header.find("resultMsg")),
        )
    # 게이트웨이 공통 에러 봉투(OpenAPI_ServiceResponse/cmmMsgHeader)
    cmm = root.find(".//cmmMsgHeader")
    if cmm is not None:
        return Header(
            resultCode=_text(cmm.find("returnReasonCode")),
            resultMsg=_text(cmm.find("returnAuthMsg")) or _text(cmm.find("errMsg")),
        )
    return Header()


def _items(root: ET.Element) -> list[ET.Element]:
    """<body><items><item>* 목록을 돌려준다(없으면 빈 리스트)."""
    return root.findall(".//body/items/item")


def parse_page(root: ET.Element) -> tuple[int | None, int | None, int | None]:
    """<body>의 (totalCount, pageNo, numOfRows)를 int로 파싱한다(없으면 None)."""

    def _int(tag: str) -> int | None:
        t = _text(root.find(f".//body/{tag}"))
        if t is None:
            return None
        try:
            return int(t)
        except ValueError:
            return None

    return _int("totalCount"), _int("pageNo"), _int("numOfRows")


Page = tuple[int | None, int | None, int | None]  # (totalCount, pageNo, numOfRows)


def parse_realtime_beds(xml_text: str) -> tuple[Header, list[RealtimeBeds], Page]:
    """응급실 실시간 가용병상 XML을 (Header, items, page)로 파싱한다.

    XML이 깨졌으면 ET.ParseError가 올라간다(호출부가 매핑).
    출처: https://www.data.go.kr/data/15000563/openapi.do
    """
    root = safe_fromstring(xml_text)
    header = parse_header(root)
    items = [
        RealtimeBeds(**{c.tag: (c.text or "").strip() for c in item if c.text})
        for item in _items(root)
    ]
    return header, items, parse_page(root)


def parse_severe_acceptance(xml_text: str) -> tuple[Header, list[SevereAcceptance], Page]:
    """중증질환자 수용가능정보 XML을 (Header, items, page)로 파싱한다.

    MKioskTy*로 시작하는 요소는 mkiosk dict에 라벨=텍스트로 모은다(고정 모델 회피).
    출처: https://www.data.go.kr/data/15000563/openapi.do
    """
    root = safe_fromstring(xml_text)
    header = parse_header(root)
    items: list[SevereAcceptance] = []
    for item in _items(root):
        fields: dict[str, str] = {}
        mkiosk: dict[str, str] = {}
        for c in item:
            text = (c.text or "").strip()
            if not text:
                continue
            if c.tag.startswith("MKioskTy"):
                mkiosk[c.tag] = text
            else:
                fields[c.tag] = text
        items.append(SevereAcceptance(mkiosk=mkiosk, **fields))
    return header, items, parse_page(root)


def parse_list(xml_text: str) -> tuple[Header, list[Institution], Page]:
    """응급의료기관 목록 XML을 (Header, items, page)로 파싱한다.

    출처: https://www.data.go.kr/data/15000563/openapi.do
    """
    root = safe_fromstring(xml_text)
    header = parse_header(root)
    items = [
        Institution(**{c.tag: (c.text or "").strip() for c in item if c.text})
        for item in _items(root)
    ]
    return header, items, parse_page(root)
