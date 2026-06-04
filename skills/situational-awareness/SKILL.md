---
name: situational-awareness
description: Assembles a real-time situational picture for a place in Korea by orchestrating ArcSolve MCP weather, air-quality, and emergency-room tools — geocoding the location, then reading current/forecast weather (Open-Meteo), real-time fine-dust/air quality (AirKorea), and emergency-room bed availability or severe-case acceptance (E-Gen). Use when a user asks what conditions are like right now in a Korean place, combines weather with air quality, needs the nearest available ER, or wants an at-a-glance outdoor/safety readout — whenever one domain alone is not enough.
allowed-tools:
  - openmeteo_geocode
  - openmeteo_forecast
  - airkorea_realtime_by_region
  - airkorea_realtime_by_station
  - airkorea_forecast
  - egen_realtime_beds
  - egen_severe_acceptance
  - egen_list
---

# Situational awareness (Korea)

Give a person a single, current picture of a place: **what's the weather, is the air safe to
breathe, and — if it matters — where is the nearest emergency room with open beds.** No single
service answers all three, so this skill geocodes the location once and fans out to three
complementary ArcSolve services, then reconciles them into one readout.

This skill **orchestrates ArcSolve MCP tools** — it does not call any API directly. The MCP
server must expose the `openmeteo`, `airkorea`, and `egen` services (see "필요 MCP 도구" in
[README](README.md)). Scope is **Korea** (AirKorea and E-Gen are Korean public data).

## When to use
- "How are things in <Korean place> right now?" — weather + air quality at a glance.
- "Is it okay to go outside / exercise in <place> today?" — temperature + wind + fine dust (PM10/PM2.5).
- "Where's the nearest ER with open beds near <place>?" — real-time emergency-room availability.
- Pre-trip or daily check-in for a region combining several live conditions.

## Service coverage (fan out by need)
| Domain | Service | Tools | Region key |
|--------|---------|-------|-----------|
| Weather | `openmeteo` | `openmeteo_geocode`, `openmeteo_forecast` | latitude/longitude |
| Air quality | `airkorea` | `airkorea_realtime_by_region`, `airkorea_realtime_by_station`, `airkorea_forecast` | `sidoName` (시도) / `stationName` (측정소) |
| Emergency rooms | `egen` | `egen_realtime_beds`, `egen_severe_acceptance`, `egen_list` | `stage1` (시도) + `stage2` (시군구) |

Each service keys regions differently (coordinates vs. 시도명 vs. 시도/시군구). Resolving the
place to all three forms is the core glue — see step 1.

## Workflow
1. **Resolve the place once.** `openmeteo_geocode(name=...)` → latitude/longitude plus the
   administrative names (e.g. admin1 = 시도, admin2 = 시군구). Use the coordinates for weather,
   the 시도 name for AirKorea's `sidoName`, and 시도/시군구 for E-Gen's `stage1`/`stage2`.
   Confirm with the user when the place name is ambiguous (multiple geocoding hits).
2. **Weather** — `openmeteo_forecast(latitude, longitude, current=..., daily=..., timezone="Asia/Seoul")`.
   Pull `current` for the now-cast and `daily`/`hourly` only as far as the question needs.
3. **Air quality** — `airkorea_realtime_by_region(sidoName=<시도>)` for a city-wide read, or
   `airkorea_realtime_by_station(stationName=...)` when a specific station is better. Report
   PM10/PM2.5 with their grade, not just raw numbers. `airkorea_forecast(searchDate=YYYY-MM-DD)`
   for the day's dust outlook.
4. **Emergency rooms (only when relevant).** `egen_realtime_beds(stage1=<시도>, stage2=<시군구>)`
   for available beds; `egen_severe_acceptance(stage1, stage2)` when the need is a specific
   severe condition; `egen_list(stage1, stage2)` to enumerate institutions in the area.
5. **Reconcile & present.** One compact readout: weather now → air quality (with grade) →
   (if asked) nearest ER with open beds. Lead with anything that affects safety (high dust grade,
   severe weather, no open beds). Always note the **observation time / freshness** of each source.

## Boundary (what this skill does NOT do)
- **Read-only and informational.** It surfaces live data; it does **not** give medical triage,
  diagnosis, or "go to this hospital" instructions — present ER availability as facts and tell the
  user to call **119** in an emergency.
- **No outdoor-activity prescription beyond the data.** Report fine-dust grade and weather; let the
  user decide. No invented thresholds.
- **Korea-scoped.** AirKorea/E-Gen are Korean data. For US weather alerts use `nws_*` instead; this
  skill does not cover non-Korean air/emergency data.
- **Hand-offs (mention, don't perform).** To push an alert to someone, hand off to a messaging skill
  / `telegram_*` · `discord_*` · `kakao_*` — *mention it, don't perform it here.*

## Etiquette
Geocode once and reuse the result; don't re-query per service. Keep AirKorea/E-Gen result sets
small (`numOfRows`) and respect each service's rate limits. AirKorea realtime is a periodic
snapshot and E-Gen bed counts update on a delay — always pass the freshness through to the user.
