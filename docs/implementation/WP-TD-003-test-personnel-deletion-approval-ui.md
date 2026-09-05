# WP-TD-003 — Test Personnel Deletion Approval UI

## Scope

WP-TD-003 adds two read/approval interfaces over the existing WP-TD foundation API:

* `/admin/system/test-personnel-data` — preview, exact target selection, request creation,
  submit and cancel for `can_request_test_personnel_deletion`;
* `/directory/personnel/test-data-deletion-approvals` — pending queue, exact manifest and
  approve/reject for `can_approve_test_personnel_deletion`.

The UI contains no execution action, execution endpoint client, or physical-delete logic.
Backend RBAC, organizational scope, manifest completeness, drift and stage policy remain
authoritative.

## Capability and identity contract

Navigation, page gates and actions use only the exact server projections introduced by
WP-TD-003A: the ADMIN panel uses `can_request_test_personnel_deletion`, while the HR_HEAD
panel uses `can_approve_test_personnel_deletion`. The audit projection remains available to
future read-only consumers; this work package does not add a separate audit panel.
The UI does not infer access from `role_id`, role names, `has_sysadmin_api` or
`has_hr_governance`.

Target identity is rendered only as `subject` and `masked_iin`. Full IIN is neither typed nor
rendered. The exact immutable manifest is loaded from request/approval detail after creation;
the search mask is used only by preview.

## Commands and concurrency

Create submits a structured `reason_code`, the exact selected Person/Application pairs and no
free comment. Submit, cancel, approve and reject send the displayed request `version`. Each
distinct command payload receives one idempotency key; an uncertain transport retry reuses that
key, and a confirmed result retires it. A synchronous in-flight guard and disabled controls
prevent duplicate clicks.

Preview responses and request details are sequence-guarded. Editing the mask invalidates both
the prior preview and its selection, while detail actions are unavailable during request
switching. A `409` triggers a fresh detail read so `EXPIRED` and `REAPPROVAL_REQUIRED` are shown
from current server state.

`BLOCK` targets cannot be selected. Approval is disabled until HR_HEAD explicitly confirms the
synthetic nature of any target requiring `SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED`.
Approve/reject retain the optional PII-validated backend comment contract.

## Failure and state presentation

The pages render loading and empty states, explicit text for `EXPIRED` and
`REAPPROVAL_REQUIRED`, and safe Russian messages for HTTP 403, 409, 410, 422 and transport
failures. Raw exception messages are not rendered. Status is
always displayed as text rather than color alone. Approved requests show the approving actor,
decision timestamp/comment, target count, shortened manifest hash and approval expiry.
