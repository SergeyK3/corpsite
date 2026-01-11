# ADR-005: Events Poller and Events Contract (v1)

## Status
Accepted

## Context

The Corpsite system uses business events to reflect task state transitions
(report submitted, approved, rejected, etc.).

The Telegram bot retrieves events from the backend using polling.
Originally, the poller and events API lacked a formally fixed contract,
which caused ambiguity in:
- polling parameters,
- ordering guarantees,
- retry behavior,
- failure handling.

During implementation and testing, these ambiguities resulted in:
- unstable bot behavior,
- repeated connection errors,
- unclear delivery guarantees.

This ADR fixes the events polling model and the `/tasks/me/events` contract.

## Goals

- Define a stable and minimal events API contract.
- Ensure deterministic polling behavior.
- Prevent event loss and duplication.
- Decouple bot lifecycle from backend availability.

## Events API Contract

### Endpoint

GET /tasks/me/events

### Headers

- X-User-Id: integer (required)

### Query Parameters

- limit: integer, optional, default 50
- after_id: integer, optional

### Response

Array of event objects ordered by ascending `event_id`.

Each event contains at least:
- event_id
- task_id
- event_type
- actor_user_id
- actor_role_id
- created_at
- payload (object)

## Ordering and Idempotency

- Events are strictly ordered by `event_id`.
- `event_id` is monotonic and unique.
- Client must use `after_id` to resume polling.
- Re-fetching the same `after_id` must not produce duplicates.

## Polling Model

### Polling Loop

- The bot polls events per user context.
- Each poll uses the last processed `after_id`.
- Only new events are retrieved.

### Startup Behavior

On bot startup:
1. Perform a single backend healthcheck via `/tasks/me/events`.
2. If backend is unreachable, polling is not started.
3. Polling starts only after a successful healthcheck.

### Healthcheck Rules

- Healthcheck failure prevents poller startup.
- Healthcheck success does not guarantee event presence.
- Healthcheck is performed once per startup.

## Failure Handling

### Backend Unreachable

- Poller does not start.
- Errors are logged once.
- No retry storm is allowed.

### Temporary Errors During Polling

- Errors are logged.
- Polling continues on the next iteration.
- `after_id` is not advanced on failure.

## Guarantees

### Guaranteed

- No event duplication.
- No event loss while backend is reachable.
- Deterministic ordering of events.

### Not Guaranteed

- Real-time delivery.
- Polling when backend is unavailable.
- Immediate recovery after backend restart.

## Responsibilities

### Backend

- Event generation.
- Event ordering.
- ACL enforcement.
- Stable `/tasks/me/events` contract.

### Bot

- Polling logic.
- Healthcheck handling.
- Persistence of `after_id`.
- Delivery of events to Telegram.

## Testing

The contract is validated by:
- Events contract tests.
- Poller startup tests.
- Failure and recovery scenarios.

## Rejected Alternatives

1. Backend push notifications  
   Rejected due to increased coupling and operational complexity.

2. Webhooks instead of polling  
   Rejected due to infrastructure and reliability constraints.

3. Polling without ordering guarantees  
   Rejected due to duplicate and missing event risks.

## Related ADRs

- ADR-003: Error semantics (403 and 409)
- ADR-004: ACL invariants
- ADR-006: Events routing and delivery policy

ADR-005 formalizes the events polling model and ensures predictable,
testable behavior of the Corpsite notification system.
