# Kakao 서비스

카카오톡 메시지 REST API의 **'나에게 보내기'(memo)** 래퍼.

## 계약 출처 (공식 문서)
- 메시지 REST API: https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api
- 메시지 템플릿(text 등): https://developers.kakao.com/docs/latest/ko/message-template/common
- 카카오 로그인 REST API(토큰): https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트·스코프·요청/응답 모델).

## 엔드포인트 (memo — 추가 권한 신청 불필요)
| 종류 | METHOD · PATH |
|------|------|
| 기본 템플릿 | `POST /v2/api/talk/memo/default/send` |
| 사용자 정의 | `POST /v2/api/talk/memo/send` |
| 스크랩 | `POST /v2/api/talk/memo/scrap/send` |

Base: `https://kapi.kakao.com` · 인증: `Authorization: Bearer {token}` · 동의항목: `talk_message`

## 셋업
1. [카카오 개발자 콘솔](https://developers.kakao.com)에서 앱 생성 → **REST API 키** 확인
2. **카카오 로그인** 활성화 + **Redirect URI** 등록 (`KAKAO_REDIRECT_URI`와 동일하게)
3. **동의항목**에서 `카카오톡 메시지 전송(talk_message)` 사용 설정
4. `.env` 작성 후 `arcsolve-mcp auth kakao` 1회 실행

## 도구
- `kakao_send_text_to_me(text, link_url?, button_title?)` — 텍스트(≤200자), 옵션 링크/버튼
- `kakao_send_link_to_me(url)` — URL 스크랩(미리보기 카드)

## 범위 / 제약
- MVP는 **'나에게 보내기'만**. '친구에게'는 별도 **사용 권한 신청** + 친구 uuid 조회(소셜 API)가
  필요하므로 v2로 분리한다.

### text 오브젝트 필드 (공식 계약)
| 필드 | 필수 | 비고 |
|------|------|------|
| `object_type` | 필수 | `"text"` 고정 |
| `text` | 필수 | 최대 **200자** |
| `link` | 선택 | 없으면 버튼/링크 미표시 |
| `button_title` | 선택 | 기본 버튼 라벨(8자 권장) |
| `buttons` | 선택 | 최대 **2개** (현재 MVP 도구에선 미노출) |

## 확장 포인트
- 다른 `object_type`(feed / list / location / commerce / calendar): `contract.py`에 모델 추가 →
  `tools.py`에 도구 추가.
- 사용자 정의 템플릿: `MEMO_CUSTOM` + `template_id` / `template_args`.
