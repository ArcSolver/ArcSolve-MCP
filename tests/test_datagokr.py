"""data.go.kr 공유 게이트웨이 헬퍼(_datagokr) 단위 검증 — 네트워크 없음.

코드표 해석(explain_result_code)과 페이지네이션 클램프(clamp_paging)를 단위로 검증한다.
이 모듈은 6개 data.go.kr 서비스가 공유하므로, canonical 코드표의 일관성·완전성을 여기서 못박는다.
"""

from arcsolve.services import _datagokr


# ─── explain_result_code ───────────────────────────────────


def test_ok_and_none_return_none():
    # 정상("00")·None은 에러가 아니므로 None을 돌려준다(호출부는 데이터로 진행).
    assert _datagokr.explain_result_code(None) is None
    assert _datagokr.explain_result_code("00") is None
    assert _datagokr.explain_result_code("00", "NORMAL SERVICE.") is None


def test_known_code_uses_canonical_hint():
    out = _datagokr.explain_result_code("30", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    assert out is not None
    assert "등록되지 않은 서비스키" in out
    assert "Decoding" in out  # 키 미등록은 이중 인코딩 함정 안내를 포함
    # 원본 메시지를 괄호로 보존한다.
    assert "(SERVICE_KEY_IS_NOT_REGISTERED_ERROR)" in out


def test_known_code_without_msg_has_no_trailing_parens():
    out = _datagokr.explain_result_code("03")
    assert out == _datagokr.RESULT_CODE_HINTS["03"]
    assert "(" not in out.split("데이터 없음", 1)[1] or "()" not in out


def test_unknown_code_preserves_code_and_msg():
    # 알 수 없는 코드는 지어내지 않고 code/msg를 그대로 보존한다.
    out = _datagokr.explain_result_code("77", "WEIRD")
    assert out is not None
    assert "resultCode=77" in out
    assert "WEIRD" in out


def test_unknown_code_without_msg():
    out = _datagokr.explain_result_code("88")
    assert out == "응답 오류(resultCode=88)"


def test_msg_whitespace_is_stripped():
    out = _datagokr.explain_result_code("22", "  LIMIT  ")
    assert "(LIMIT)" in out  # 앞뒤 공백 제거 후 괄호로


def test_previously_missing_codes_now_covered():
    # 감사에서 절반의 서비스가 누락했던 코드(05/10/11/21)가 이제 모두 canonical로 안내된다.
    for code in ("05", "10", "11", "21"):
        out = _datagokr.explain_result_code(code, "X")
        assert out is not None
        assert f"({code})" in out  # 힌트 본문에 코드가 명시됨
        assert "resultCode=" not in out  # 알 수 없는 코드 폴백이 아니라 known 힌트


def test_full_canonical_table_present():
    # data.go.kr 공통 결과/에러 코드표 전체가 실려 있다(00 포함).
    expected = {
        "00", "01", "02", "03", "04", "05", "10", "11", "12",
        "20", "21", "22", "30", "31", "32", "33", "99",
    }
    assert expected <= set(_datagokr.RESULT_CODE_HINTS)
    assert _datagokr.RESULT_CODE_OK == "00"


def test_every_known_non_ok_code_yields_message():
    for code in _datagokr.RESULT_CODE_HINTS:
        if code == _datagokr.RESULT_CODE_OK:
            assert _datagokr.explain_result_code(code) is None
        else:
            assert _datagokr.explain_result_code(code) is not None


# ─── clamp_paging ──────────────────────────────────────────


def test_clamp_within_range_is_unchanged():
    assert _datagokr.clamp_paging(100, 1, max_rows=9999) == (100, 1)
    assert _datagokr.clamp_paging(9999, 50, max_rows=9999) == (9999, 50)


def test_clamp_num_of_rows_above_max():
    assert _datagokr.clamp_paging(100000, 1, max_rows=9999) == (9999, 1)


def test_clamp_num_of_rows_below_min():
    # 기본 하한 1.
    assert _datagokr.clamp_paging(0, 1, max_rows=9999) == (1, 1)
    assert _datagokr.clamp_paging(-5, 1, max_rows=9999) == (1, 1)


def test_clamp_respects_custom_min_rows():
    # ev_charger처럼 하한이 10인 경우.
    assert _datagokr.clamp_paging(5, 1, max_rows=9999, min_rows=10) == (10, 1)
    assert _datagokr.clamp_paging(50, 1, max_rows=9999, min_rows=10) == (50, 1)


def test_clamp_page_no_below_min():
    rows, page = _datagokr.clamp_paging(100, 0, max_rows=9999)
    assert page == 1
    rows, page = _datagokr.clamp_paging(100, -3, max_rows=9999)
    assert page == 1


def test_clamp_page_no_has_no_upper_bound():
    # pageNo는 상한이 없다(데이터 끝이면 빈 페이지).
    assert _datagokr.clamp_paging(100, 100000, max_rows=9999) == (100, 100000)


def test_clamp_custom_min_page():
    assert _datagokr.clamp_paging(100, 0, max_rows=9999, min_page=0) == (100, 0)
