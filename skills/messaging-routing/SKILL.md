---
name: messaging-routing
description: Routes a message or notification to the right chat channel by orchestrating ArcSolve MCP messaging tools — Kakao (note-to-self), Telegram (text/photo/document), Discord (message/embed), and LINE (push/multicast/broadcast). Use when a user wants to send or broadcast a notification, pick the appropriate channel for an audience, fan a message out to several channels, or format the same content correctly per platform — whenever delivery spans more than one messaging service.
allowed-tools:
  - kakao_send_text_to_me
  - kakao_send_link_to_me
  - telegram_send_message
  - telegram_send_photo
  - telegram_send_document
  - discord_send_message
  - discord_send_embed
  - line_send_text
  - line_multicast_text
  - line_broadcast_text
---

# Messaging routing

Deliver a notification to **the right channel(s)**, formatted per platform. Each service has a
different audience model (Kakao = note-to-self, Telegram = a chat/bot, Discord = a webhook channel,
LINE = push/multicast/broadcast to subscribers), so this skill picks the channel by intent and
adapts the message rather than blasting everywhere.

This skill **orchestrates ArcSolve MCP tools** — it does not call any API directly. The MCP server
must expose the `kakao`, `telegram`, `discord`, and/or `line` services (see "필요 MCP 도구" in
[README](README.md)). These tools **send** — see the boundary.

## When to use
- "Send me a reminder / send this to my Telegram" — route to one channel.
- "Notify the team on Discord" — channel-appropriate formatting (embed for rich content).
- "Broadcast this to our LINE subscribers" — audience-wide delivery.
- "Send the same update to Telegram and Discord" — controlled fan-out.

## Channel coverage (route by audience)
| Channel | Service | Tools | Audience model |
|---------|---------|-------|----------------|
| Kakao | `kakao` | `kakao_send_text_to_me`, `kakao_send_link_to_me` | **self only** (note-to-self) |
| Telegram | `telegram` | `telegram_send_message`, `telegram_send_photo`, `telegram_send_document` | a chat/bot |
| Discord | `discord` | `discord_send_message`, `discord_send_embed` | a webhook channel |
| LINE | `line` | `line_send_text`, `line_multicast_text`, `line_broadcast_text` | push / multicast / **broadcast (all subscribers)** |

## Workflow
1. **Pick the channel(s)** by audience and what's configured. Self-reminder → Kakao; a person/bot →
   Telegram; a team channel → Discord; subscriber base → LINE. Only use channels whose credentials
   are configured.
2. **Adapt the message** per platform: plain text vs. a Discord **embed** (title/description/url) for
   rich content; attach via `telegram_send_photo` / `telegram_send_document` for media; respect each
   platform's length limits (the tools enforce them).
3. **Confirm before broadcast.** `line_broadcast_text` reaches **all** subscribers — confirm intent
   and content with the user first. The same for any wide fan-out.
4. **Send**, then **report** delivery per channel (message id / result), and surface any per-channel
   error clearly instead of silently dropping it.

## Boundary (what this skill does NOT do)
- **Sends on the user's behalf — confirm first.** Always confirm the recipient/channel and content
   before sending, and **especially before any broadcast/multicast**. Never send unsolicited or
   bulk messages. No spam.
- **No reply-context flows.** Proactive sends only; it does not handle inbound webhooks / reply tokens.
- **Respects each platform's scope.** Kakao MVP is note-to-self only; it does not message friends.
- **No content creation beyond formatting** what the user provided. It routes and formats; it does not
   author marketing copy or invent recipients.

## Etiquette
Prefer the narrowest audience that satisfies the request. Reuse a single composed message across
channels with per-platform formatting. Treat broadcast as a deliberate, confirmed action.
