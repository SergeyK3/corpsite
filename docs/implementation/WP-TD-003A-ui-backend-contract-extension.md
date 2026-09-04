# WP-TD-003A — UI Backend Contract Extension

## Scope

WP-TD-003A minimally extends the existing approval foundation for future ADMIN and HR_HEAD
panels. It adds no UI, migration, execution endpoint, execution capability projection, or
physical deletion logic.

## Exact `/auth/me` capabilities

The backend projects three booleans from one shared endpoint policy:

* `can_request_test_personnel_deletion`: active primary role `ADMIN` plus the exact
  `TEST_PERSONNEL_DELETION_REQUEST` permission;
* `can_approve_test_personnel_deletion`: active primary role `HR_HEAD` plus the exact
  `TEST_PERSONNEL_DELETION_APPROVE` permission;
* `can_read_test_personnel_deletion_audit`: active primary role `ADMIN` or `HR_HEAD` plus the
  exact `TEST_PERSONNEL_DELETION_AUDIT_READ` permission.

The same resolver protects the endpoints. Broad sysadmin/HR capabilities, `role_id`, role-name
fallback and cross-role personal grants do not create these capabilities. The existing
`TEST_PERSONNEL_DELETION_EXECUTE` permission is deliberately not projected.

## Read-only safe projections

Preview and manifest target reads expose `subject` and `masked_iin`. Identity is read from
`persons` in one batch and is never copied to the immutable target rows or append-only history.
Missing identity returns a non-PII technical fallback and `masked_iin=null`. There is no
service-level full-IIN parameter.

Request lists/details expose `initiated_by_display_name`, and decision reads expose
`actor_display_name`. Names come from canonical `users.full_name` in one batch per response;
missing users render as `Пользователь #<id>`. Technical IDs remain present. Display names are
read projections and are not stored in history or immutable command results.

## Comment decision

MVP create keeps its existing structured `reason_code` contract and rejects an unknown
`comment` field. A PII-validated optional decision comment remains available for
approve/reject. Future UI must not request a free create comment.
