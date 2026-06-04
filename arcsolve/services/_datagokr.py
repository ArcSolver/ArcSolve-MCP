"""data.go.kr(공공데이터포털) OpenAPI **공유 게이트웨이 헬퍼** — 6개 서비스 공통.

서비스 폴더가 아니라 `services/` 하위의 **공유 모듈**이다(이름 앞 `_`로 비서비스임을 명시 —
레지스트리는 패키지만 자동발견하므로 평면 모듈은 서비스로 잡히지 않는다). AGENTS.md "코어 확장"
규칙상, 여러 서비스가 같은 게이트웨이 규약을 각자 재구현하던 중복을 단일 출처로 상환한다.

이 모듈이 상환하는 중복(감사 결과):
  airkorea·egen·ev_charger·parking·tago_transit·airport 6종이 동일한 data.go.kr 게이트웨이
  결과/에러 코드표·numOfRows 클램프를 각자 재구현해, 같은 게이트웨이 오류에 안내 편차가 있었다
  (05/10/11/21 누락 편차, 클램프는 ev_charger만 보유). 이 모듈로 코드표·클램프를 통일한다.

**무엇을 공유하고 무엇을 안 하나**:
  - 공유: "결과코드 → 사람이 읽을 안내"(explain_result_code), "numOfRows/pageNo 클램프"(clamp_paging).
  - 비공유(서비스가 유지): "봉투에서 resultCode/resultMsg를 어떻게 꺼내는지". 봉투 구조가 서비스마다
    다르기 때문이다 — airkorea·tago·airport는 JSON `response.header.resultCode`, parking은 top-level
    `resultCode`, egen·ev_charger는 XML `header.resultCode`. 이 추출 로직은 통합하지 않는다.

출처(canonical — data.go.kr OpenAPI 공통 결과/에러 코드표):
  data.go.kr OpenAPI 활용가이드의 공통 응답 봉투 `cmmMsgHeader`(returnReasonCode/returnAuthMsg)
  및 `header.resultCode` 표준 결과코드표. 코드→문구는 게이트웨이가 돌려주는 영문 상수
  (예: SERVICE_KEY_IS_NOT_REGISTERED_ERROR)와 활용가이드의 한글 의미를 대응시킨 것이다.
  교차참조: data.go.kr 각 서비스 상세 페이지 응답 메시지, 공공데이터포털 OpenAPI 사용가이드,
  문화포털 OpenAPI 사용가이드(동일 게이트웨이 규약)의 결과코드 표.
"""

from __future__ import annotations

# 정상 결과코드. 출처: data.go.kr 공통 결과코드표(00 = NORMAL_CODE / NORMAL SERVICE).
RESULT_CODE_OK = "00"

# data.go.kr OpenAPI 공통 게이트웨이 결과/에러 코드 → 사람이 읽을 한글 안내.
#
# 출처: data.go.kr OpenAPI 활용가이드 공통 응답(cmmMsgHeader.returnReasonCode /
#   header.resultCode) 결과코드표. 각 문구는 게이트웨이 영문 상수와 활용가이드 한글 의미 대응.
#   - 30(SERVICE_KEY_IS_NOT_REGISTERED_ERROR)·31(DEADLINE_HAS_EXPIRED_ERROR)·
#     32(UNREGISTERED_IP_ERROR)·22(LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR)·
#     20(SERVICE_ACCESS_DENIED_ERROR)·12(NO_OPENAPI_SERVICE_ERROR)·04(HTTP_ERROR)·
#     01(APPLICATION_ERROR)·99(UNKNOWN_ERROR)는 다수 공식/구현 출처가 만장일치.
#   - 03(NODATA_ERROR)·02(DB_ERROR)는 활용가이드 표준.
#   - 05(SERVICETIMEOUT_ERROR)·10(INVALID_REQUEST_PARAMETER_ERROR)·
#     11(NO_MANDATORY_REQUEST_PARAMETERS_ERROR)·21(TEMPORARILY_DISABLE_THE_SERVICEKEY_ERROR)·
#     33(UNSIGNED_CALL_ERROR)는 활용가이드 전체 표 기준(일부 서비스 상세 페이지는 부분만 렌더).
#
# 30(키 미등록)은 data.go.kr 특유의 Encoding/Decoding 2종 키 함정을 함께 안내한다(이중 인코딩 방지).
RESULT_CODE_HINTS: dict[str, str] = {
    "00": "정상(00).",
    "01": "어플리케이션 에러(01): 잠시 후 재시도하세요.",
    "02": "데이터베이스 에러(02): 잠시 후 재시도하세요.",
    "03": "데이터 없음(03): 해당 조건의 데이터가 없습니다.",
    "04": "HTTP 에러(04).",
    "05": "서비스 연결 실패/타임아웃(05): 잠시 후 재시도하세요.",
    "10": "잘못된 요청 파라미터(10): 입력값(페이지·건수·코드·날짜 등)을 확인하세요.",
    "11": "필수 요청 파라미터 누락(11): serviceKey 등 필수 입력값을 확인하세요.",
    "12": "폐기된 서비스(12): 해당 OpenAPI는 더 이상 제공되지 않습니다(없거나 폐기).",
    "20": "서비스 접근 거부(20): 서비스키 권한/IP 설정을 확인하세요.",
    "21": "일시적 서비스키 비활성(21): 잠시 후 재시도하세요.",
    "22": "서비스 요청 제한 초과(22): 일일 트래픽 한도를 초과했습니다.",
    "30": (
        "등록되지 않은 서비스키(30): 서비스키를 확인하세요. "
        "⚠️ Encoding이 아니라 **Decoding 키(원문)**를 넣어야 합니다(이중 인코딩 방지)."
    ),
    "31": "기한 만료 서비스키(31): 활용기간이 만료되었습니다. data.go.kr에서 연장하세요.",
    "32": "등록되지 않은 IP(32): 서비스키에 허용 IP를 등록하세요.",
    "33": "서명되지 않은 호출(33): 인증 서명이 없는 호출입니다(서비스키/요청을 확인하세요).",
    "99": "기타 에러(99).",
}


def explain_result_code(code: str | None, msg: str | None = None) -> str | None:
    """data.go.kr 결과코드를 사람이 읽을 안내 문자열로 해석한다.

    - code가 None이거나 "00"(정상)이면 None을 돌려준다(에러 아님 → 호출부는 데이터로 진행).
    - 알려진 코드면 RESULT_CODE_HINTS의 canonical 힌트를 쓰고, msg가 있으면 괄호로 덧붙인다.
    - 알 수 없는 코드면 code와 msg를 보존한 일반 메시지를 만든다(환각 금지 — 원본 보존).

    봉투에서 code/msg를 어떻게 꺼내는지는 **서비스가 책임진다**(봉투 구조가 서비스마다 다름).
    이 함수는 추출된 (code, msg)만 받아 canonical 코드표로 해석만 한다.

    Args:
        code: 게이트웨이 결과코드(resultCode / returnReasonCode). None이면 정상으로 취급.
        msg: 게이트웨이 원본 메시지(resultMsg / returnAuthMsg). 있으면 안내에 덧붙인다.

    Returns:
        안내 문자열, 또는 정상(code None/"00")일 때 None.
    """
    if code is None or code == RESULT_CODE_OK:
        return None
    msg = (msg or "").strip()
    hint = RESULT_CODE_HINTS.get(code)
    if hint:
        return f"{hint}{(' (' + msg + ')') if msg else ''}"
    # 알 수 없는 코드: code/msg를 그대로 보존해 진단 가능하게 한다(지어내지 않음).
    return f"응답 오류(resultCode={code}){(': ' + msg) if msg else ''}"


def clamp_paging(
    num_of_rows: int,
    page_no: int,
    *,
    max_rows: int,
    min_rows: int = 1,
    min_page: int = 1,
) -> tuple[int, int]:
    """numOfRows/pageNo를 안전 범위로 클램프한다(상류 제약 위반 호출을 사전 방지).

    상류 data.go.kr 오퍼레이션은 numOfRows에 상·하한이 있고(예: 1~9999), 위반 시 결과코드 10
    (잘못된 요청 파라미터)을 돌려줄 수 있다. 호출부가 이상값을 넘겨도 게이트웨이 왕복 없이
    안전 범위로 보정한다. pageNo는 1 미만을 방지한다(상한 없음 — 데이터 끝이면 빈 페이지).

    Args:
        num_of_rows: 요청 페이지 크기.
        page_no: 요청 페이지 번호.
        max_rows: numOfRows 상한(오퍼레이션별 — 서비스가 지정).
        min_rows: numOfRows 하한(기본 1).
        min_page: pageNo 하한(기본 1).

    Returns:
        (클램프된 numOfRows, 클램프된 pageNo).
    """
    clamped_rows = max(min_rows, min(max_rows, num_of_rows))
    clamped_page = max(min_page, page_no)
    return clamped_rows, clamped_page
