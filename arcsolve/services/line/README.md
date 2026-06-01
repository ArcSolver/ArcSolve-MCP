# LINE 서비스

LINE Messaging API의 **push 메시지(텍스트)** 래퍼.

## 계약 출처 (공식 문서)
- Messaging API 레퍼런스: https://developers.line.biz/en/reference/messaging-api/
- Send push message: https://developers.line.biz/en/reference/messaging-api/#send-push-message
- Text message object: https://developers.line.biz/en/reference/messaging-api/#text-message
- 채널 액세스 토큰: https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트·요청/응답 모델·제약).

## 엔드포인트
| 종류 | METHOD · PATH |
|------|------|
| push 메시지 | `POST /v2/bot/message/push` |

Base: `https://api.line.me` · 인증: `Authorization: Bearer {channel access token}` · Content-Type: `application/json`

## 셋업
1. [LINE Developers 콘솔](https://developers.line.biz)에서 **Messaging API 채널** 생성
2. **채널 액세스 토큰**(long-lived) 발급
3. `.env`에 작성:
   - `LINE_CHANNEL_ACCESS_TOKEN=<발급한 토큰>`
   - `LINE_TO=<기본 수신자 userId/groupId/roomId>` (선택 — 인자로 덮어쓰기 가능)

> 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth line` 단계는 없다(토큰을 env로 직접 받는다).

## 도구
| 도구 | 설명 |
|------|------|
| `line_send_text(text, to?)` | 텍스트(≤5000자) push 1건. `to` 미지정 시 `LINE_TO` 사용 |

## 범위 / 제약
- MVP는 **텍스트 push 1건만**. 멀티캐스트/브로드캐스트/리플라이, 그 외 메시지 타입(이미지·스티커 등)은 v2로 분리.

### push 요청/텍스트 필드 (공식 계약)
| 필드 | 필수 | 비고 |
|------|------|------|
| `to` | 필수 | 수신자 `userId`/`groupId`/`roomId` |
| `messages` | 필수 | 메시지 배열, 최대 **5개** |
| `notificationDisabled` | 선택 | `true`면 푸시 알림 미수신 |
| `messages[].type` | 필수 | `"text"` 고정 |
| `messages[].text` | 필수 | 최대 **5000자**(UTF-16 코드 유닛 기준) |

## 확장 포인트
- 다른 메시지 타입(image / sticker / location / template 등): `contract.py`에 모델 추가 → `tools.py`에 도구 추가.
- 멀티캐스트(`/v2/bot/message/multicast`) / 브로드캐스트(`/v2/bot/message/broadcast`): 동일 패턴으로 엔드포인트·도구 추가.
- `customAggregationUnits`, `emojis`, `quoteToken` 등 선택 필드 노출.
