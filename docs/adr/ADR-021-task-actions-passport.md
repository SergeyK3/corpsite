# ADR-021: Task Actions Passport (allowed_actions as single source of truth)

Status: Accepted  
Date: 2026-02-08  
Scope: Tasks / FSM / Events / UI / Bot  
Related: ADR-020 Regular Tasks Contract

## Decision

The system adopts `allowed_actions` as the **single source of truth** for all task-related business actions.

Clients (UI, Bot, integrations):
- MUST rely only on `allowed_actions`
- MUST NOT infer permissions from `status_code`

Backend:
- MUST compute `allowed_actions` for each task
- MUST enforce action guards on every action endpoint

## Rationale

- Prevents UI/backend desynchronization
- Enables safe FSM evolution
- Improves UX by eliminating forbidden actions before execution
- Centralizes business rules

## Task Contract (minimum)

```json
{
  "task_id": 246,
  "status_code": "IN_PROGRESS",
  "allowed_actions": ["archive", "reject"]
}
