# Telegram 서비스

Telegram Bot API의 **sendMessage** 래퍼. 봇으로 텍스트 메시지를 전송한다("나에게 보내기" 결).

## 계약 출처 (공식 문서)
- Bot API 레퍼런스: https://core.telegram.org/bots/api
- sendMessage 메서드: https://core.telegram.org/bots/api#sendmessage
- 요청/응답 포맷(Making requests): https://core.telegram.org/bots/api#making-requests
- LinkPreviewOptions 오브젝트: https://core.telegram.org/bots/api#linkpreviewoptions

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트·요청/응답 모델).

## 엔드포인트
| 종류 | METHOD · PATH |
|------|------|
| 메시지 전송 | `POST /bot<token>/sendMessage` |

Base: `https://api.telegram.org` · 인증: **봇 토큰을 URL 경로에** (`/bot<token>/...`, Bearer 아님) · 스코프: 없음

## 셋업
1. Telegram [@BotFather](https://t.me/BotFather)로 봇 생성 → **봇 토큰** 발급
2. 봇과 1:1 대화를 시작(또는 그룹에 추가)해 대상 채팅을 활성화
3. `.env`에 자격증명 작성:
   - `TELEGRAM_BOT_TOKEN=123456:ABC-...` (필수)
   - `TELEGRAM_CHAT_ID=123456789` (선택 — 기본 대상; 도구 인자로 덮어쓸 수 있음)

> 이 서비스는 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth telegram`이 필요 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `telegram_send_message(text, chat_id?, parse_mode?, disable_link_preview?, disable_notification?)` | 텍스트(1-4096자) 전송. `chat_id` 미지정 시 `TELEGRAM_CHAT_ID` 사용 |

## 범위 / 제약
- MVP는 **텍스트 전송(sendMessage)만**. 사진/문서 등 미디어, 인라인 키보드(`reply_markup`),
  답장(`reply_parameters`), 엔티티(`entities`) 등은 v2로 분리한다.
- `text`는 공식 제약대로 **1-4096자**(엔티티 파싱 후 기준).
- `parse_mode`는 `"MarkdownV2"` 또는 `"HTML"`만 노출(legacy `"Markdown"` 제외).

### sendMessage 필드 (공식 계약, MVP 노출분)
| 필드 | 필수 | 비고 |
|------|------|------|
| `chat_id` | 필수 | 정수 ID 또는 `"@channelusername"` |
| `text` | 필수 | 1-4096자 |
| `parse_mode` | 선택 | `MarkdownV2` / `HTML` |
| `message_thread_id` | 선택 | 포럼 토픽 ID (contract.py에만, 도구 미노출) |
| `link_preview_options` | 선택 | 구 `disable_web_page_preview` 대체 (Bot API 7.0) |
| `disable_notification` | 선택 | 조용히 전송 |
| `protect_content` | 선택 | 전달/저장 방지 (contract.py에만, 도구 미노출) |

## 확장 포인트
- 미디어 전송: `sendPhoto` / `sendDocument` 메서드 + (multipart) 코어 동사 필요 시 보강.
- 인라인 버튼: `reply_markup`(InlineKeyboardMarkup) 모델 추가.
- 답장/엔티티: `reply_parameters`, `entities` 모델 추가.
