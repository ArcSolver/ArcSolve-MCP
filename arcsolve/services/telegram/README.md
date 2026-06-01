# Telegram 서비스

Telegram Bot API 래퍼. 봇으로 텍스트/사진/문서를 전송하고("나에게 보내기" 결),
보낸 메시지를 편집·삭제하며, 봇 신원(헬스체크)을 확인한다.

## 계약 출처 (공식 문서)
- Bot API 레퍼런스: https://core.telegram.org/bots/api
- sendMessage 메서드: https://core.telegram.org/bots/api#sendmessage
- getMe 메서드: https://core.telegram.org/bots/api#getme
- sendPhoto 메서드: https://core.telegram.org/bots/api#sendphoto
- sendDocument 메서드: https://core.telegram.org/bots/api#senddocument
- editMessageText 메서드: https://core.telegram.org/bots/api#editmessagetext
- deleteMessage 메서드: https://core.telegram.org/bots/api#deletemessage
- 요청/응답 포맷(Making requests): https://core.telegram.org/bots/api#making-requests
- LinkPreviewOptions 오브젝트: https://core.telegram.org/bots/api#linkpreviewoptions
- User 오브젝트: https://core.telegram.org/bots/api#user
- Message 오브젝트: https://core.telegram.org/bots/api#message

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트·요청/응답 모델).

## 엔드포인트
| 종류 | METHOD · PATH |
|------|------|
| 봇 신원/헬스체크 | `GET /bot<token>/getMe` |
| 메시지 전송 | `POST /bot<token>/sendMessage` |
| 사진 전송 | `POST /bot<token>/sendPhoto` |
| 문서 전송 | `POST /bot<token>/sendDocument` |
| 메시지 편집 | `POST /bot<token>/editMessageText` |
| 메시지 삭제 | `POST /bot<token>/deleteMessage` |

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
| `telegram_get_me()` | 봇 신원/토큰 유효성 확인(헬스체크). 파라미터 없음 |
| `telegram_send_message(text, chat_id?, parse_mode?, disable_link_preview?, disable_notification?)` | 텍스트(1-4096자) 전송. `chat_id` 미지정 시 `TELEGRAM_CHAT_ID` 사용 |
| `telegram_send_photo(photo, caption?, chat_id?, parse_mode?)` | 사진 전송. `photo`는 **URL 또는 file_id 문자열만**. `caption` 0-1024자. `chat_id` 미지정 시 `TELEGRAM_CHAT_ID` 사용 |
| `telegram_send_document(document, caption?, chat_id?, parse_mode?)` | 문서 전송. `document`는 **URL 또는 file_id 문자열만**. `caption` 0-1024자. `chat_id` 미지정 시 `TELEGRAM_CHAT_ID` 사용 |
| `telegram_edit_message_text(chat_id, message_id, text, parse_mode?)` | 봇이 보낸 메시지의 텍스트(1-4096자) 편집 |
| `telegram_delete_message(chat_id, message_id)` | 메시지 삭제(성공 시 True) |

## 범위 / 제약
- 텍스트/사진/문서 전송, 메시지 편집·삭제, 봇 헬스체크를 노출한다. 인라인 키보드(`reply_markup`),
  답장(`reply_parameters`), 엔티티(`entities`)는 v2로 분리한다.
- `text`는 공식 제약대로 **1-4096자**(엔티티 파싱 후 기준). `caption`은 **0-1024자**.
- `parse_mode`는 `"MarkdownV2"` 또는 `"HTML"`만 노출(legacy `"Markdown"` 제외).
- **사진/문서 전송은 `photo`/`document`가 URL 또는 file_id 문자열일 때만 지원**한다.
  로컬 파일 업로드(multipart/form-data)는 **코어에 multipart 동사가 없어 미구현**이며,
  코어 multipart 동사가 추가된 뒤 별도로 지원할 예정이다.
- `editMessageText`/`deleteMessage`는 봇 자신이 보낸(또는 접근 가능한) 메시지에만 동작한다.
  인라인 메시지(`inline_message_id`) 경로는 범위 밖이다.

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

### sendPhoto / sendDocument 필드 (공식 계약, 노출분)
| 필드 | 필수 | 비고 |
|------|------|------|
| `chat_id` | 필수 | 정수 ID 또는 `"@channelusername"` |
| `photo` / `document` | 필수 | **URL 또는 file_id 문자열만** (로컬 업로드 미지원) |
| `caption` | 선택 | 0-1024자 |
| `parse_mode` | 선택 | `MarkdownV2` / `HTML` |

### editMessageText / deleteMessage 필드 (공식 계약, 노출분)
| 필드 | 필수 | 비고 |
|------|------|------|
| `chat_id` | 필수 | 정수 ID 또는 `"@channelusername"` |
| `message_id` | 필수 | 편집/삭제할 메시지 ID |
| `text` | 필수(편집) | 1-4096자 |
| `parse_mode` | 선택(편집) | `MarkdownV2` / `HTML` |

## 확장 포인트
- 로컬 파일 업로드: `sendPhoto`/`sendDocument`의 multipart/form-data 경로 — 코어 multipart 동사 추가 후.
- 인라인 버튼: `reply_markup`(InlineKeyboardMarkup) 모델 추가.
- 답장/엔티티: `reply_parameters`, `entities` 모델 추가.
- 인라인 메시지 편집: `editMessageText`의 `inline_message_id` 경로.
