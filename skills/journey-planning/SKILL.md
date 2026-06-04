---
name: journey-planning
description: Plans a real-time, multi-modal trip across Korea by orchestrating ArcSolve MCP transit tools — subway and bus arrivals, intercity/express bus and rail schedules, airport flight status, public-bike availability, and (at the destination) parking vacancy and EV-charger status. Use when a user asks how to get somewhere in Korea, when the next bus/subway/train arrives, whether there's parking or an open EV charger at the destination, or to assemble an at-a-glance door-to-door plan combining several live sources.
allowed-tools:
  - seoul_subway_arrivals
  - seoul_bike_status
  - tago_search_bus_stops
  - tago_bus_arrivals
  - tago_bus_route
  - tago_express_bus
  - tago_intercity_bus
  - tago_train
  - tago_city_codes
  - airport_arrivals
  - airport_departures
  - parking_search
  - parking_realtime
  - ev_charger_status
  - ev_charger_info
---

# Journey planning (Korea)

Assemble a **door-to-door, real-time** picture of a trip in Korea: when the next bus/subway/train
leaves, the intercity/rail option for longer legs, and — at the destination — where to park or
charge. No single service covers a whole journey, so this skill routes each leg to the right
source and reconciles them into one plan.

This skill **orchestrates ArcSolve MCP tools** — it does not call any API directly. The MCP server
must expose the `seoul_transit`, `tago_transit`, `airport`, `parking`, and `ev_charger` services
(see "필요 MCP 도구" in [README](README.md)). Scope is **Korea**.

## When to use
- "When's the next bus/subway at <stop/station>?" — real-time arrivals.
- "How do I get from <A> to <B> in Korea?" — multi-modal leg planning (local + intercity).
- "Is there parking / an open EV charger near <destination>?" — destination logistics.
- "What's the status of flight / arrivals at Incheon?" — air leg.

## Service coverage (route each leg)
| Leg | Service | Tools |
|-----|---------|-------|
| Seoul metro / bikeshare | `seoul_transit` | `seoul_subway_arrivals`, `seoul_bike_status` |
| Nationwide bus / rail | `tago_transit` | `tago_search_bus_stops`, `tago_bus_arrivals`, `tago_bus_route`, `tago_express_bus`, `tago_intercity_bus`, `tago_train`, `tago_city_codes` |
| Air (Incheon) | `airport` | `airport_arrivals`, `airport_departures` |
| Park at destination | `parking` | `parking_search`, `parking_realtime` |
| Charge at destination | `ev_charger` | `ev_charger_status`, `ev_charger_info` |

## Workflow
1. **Frame the legs.** Split the trip into local (subway/bus), intercity (express/intercity bus, rail),
   and air. Identify origin/destination region — TAGO is keyed by city code (`tago_city_codes`) and
   stop (`tago_search_bus_stops`); Seoul metro is station-keyed.
2. **Local arrivals.** `seoul_subway_arrivals(station)` or `tago_bus_arrivals(...)` for the next
   departures. `seoul_bike_status` for a first/last-mile bike option.
3. **Intercity / rail.** For longer legs use `tago_express_bus` / `tago_intercity_bus` /
   `tago_train`. For flights, `airport_departures` / `airport_arrivals`.
4. **Destination logistics (only if asked).** `parking_search` + `parking_realtime` for vacancy;
   `ev_charger_status` (+ `ev_charger_info`) if the user drives an EV.
5. **Present** one ordered plan per leg with the **freshness** of each real-time value (arrivals and
   vacancy are periodic snapshots), and note when data is unavailable rather than guessing.

## Boundary (what this skill does NOT do)
- **Read-only / informational.** It surfaces live transit data; it does **not** book, pay, or reserve.
- **No routing engine.** It reports arrivals/schedules from the official sources; it does not compute
  optimal paths or fares beyond what the tools return. No invented travel times.
- **Korea-scoped.** These are Korean public-data services.
- **Hand-offs (mention, don't perform).** To check weather/air along the route, hand off to
  `situational-awareness`; to send the plan to someone, hand off to a messaging skill — *mention, don't perform*.

## Etiquette
Resolve the city code / stop once and reuse it. Keep result sets small (`numOfRows`) and respect each
service's rate limits. Always pass each value's observation time through to the user.
