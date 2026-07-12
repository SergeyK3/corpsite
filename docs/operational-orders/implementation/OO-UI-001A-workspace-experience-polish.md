# OO-UI-001A — Workspace Experience Polish

## Scope

Polish the OO-UI-001 developer/tester interface into a clearer working UI for internal demo and pilot use. **Frontend-only** — no backend domain model changes.

Routes unchanged:

- `/directory/operational-orders`
- `/directory/operational-orders/workspaces/{workspaceId}`
- `/directory/operational-orders/documents/{documentId}`

## Before / After

| Area | OO-UI-001 | OO-UI-001A |
|---|---|---|
| Translation assignments | Raw JSON in `WorkflowListSection` | Cards: direction, status, assignee, dates, versions, fingerprints; active vs history |
| Content confirmations | Raw JSON | Cards/table fields with role/status labels; create/revoke forms |
| Bilingual reconciliation | Raw JSON | RU ↔ KK pair cards; create/invalidate forms from block selectors |
| Frozen workspace | Minimal text | Banner with document link, promotion date, drift, revision advisory |
| Workspace progress | Stage badge only | 8-step visual timeline from `stage` |
| Document lifecycle | Latest transition only | Timeline with deferred SIGNED/REGISTERED |
| Audit / provenance | Mixed raw lists | Separate sections; human-readable action labels; JSON under «Технические данные» |
| Validation | Flat issue list | ERROR/WARNING/INFO groups, summary, blocker count |
| Fingerprints | Full strings or absent | Compact `a91f…e42c` with expand/copy |
| Empty states | `[]` or empty containers | Russian empty-state messages |

## Component changes

### New `_lib/`

- `actionLabels.ts` — audit/provenance human-readable labels
- `workspaceTimeline.ts` — workspace progress step builder
- `documentTimeline.ts` — document lifecycle step builder
- `status.ts` — extended translation/confirmation/reconciliation labels and helpers
- `testFixtures.ts` — shared test fixtures

### New `_components/`

- `CompactFingerprint.tsx`
- `WorkspaceProgressTimeline.tsx`
- `DocumentLifecycleTimeline.tsx`
- `FrozenWorkspaceBanner.tsx` (rewritten)
- `ValidationPanel.tsx` (rewritten)
- `TranslationAssignmentsSection.tsx`
- `ContentConfirmationsSection.tsx`
- `BilingualReconciliationsSection.tsx`
- `AuditSections.tsx`

### Updated page clients

- `WorkspaceDetailPageClient.tsx` — wires all sections; loads linked document when frozen for banner enrichment
- `DocumentDetailPageClient.tsx` — lifecycle timeline, audit labels, compact fingerprints

## Translation presentation

Per assignment: RU → KK / KK → RU, Russian status labels, assignee, assigner, request/accept/complete/due dates, block versions, fingerprints, notes. Active assignments separate from history (`details`).

## Translation actions

Forms/buttons when permitted: assign, accept, start, complete, cancel. Uses existing API client mutations with `expected_version`. Permission + frozen + assignee checks on UI. PartyReference text inputs (no directory selector).

## Confirmation presentation

Language, block, role (Автор содержания / Переводчик / Оператор документа), confirmer, version, fingerprint, status, confirmed/revoked dates, revocation reason. Current vs historical split.

## Confirmation actions

Create confirmation form (block selector, role, PERSON reference). Revoke action on active confirmations. `OO_CONFIRMATION_PARTY_MISMATCH` mapped via existing `mapOoApiError`.

## Reconciliation presentation

Block type/sequence, RU/KK versions, fingerprints, status, reconciler, dates, invalidation reason. Visual RU ↔ KK pair layout.

## Reconciliation actions

Create from RU/KK block dropdowns; invalidate on RECONCILED items. Block versions from detail — no manual JSON.

## Workspace timeline

Eight steps: Передан → Принят → Проверен → Перевод → Подтверждение → Согласование RU/KK → Редакционный пакет готов → Официальный проект создан. States: completed / current / blocked / future from `stage` only.

## Document timeline

Created → Signing authority → Readiness → Ready for signature (from status + audit). SIGNED/REGISTERED shown as deferred with «Ещё не реализовано».

## Frozen banner

Title «Официальный проект создан», explanation text, document link, promotion date (from linked document), drift flag, revision advisory warning.

## Audit mapping

Centralized in `actionLabels.ts` for SUBMISSION_CREATED, WORKSPACE_ACCEPTED, TRANSLATION_*, CONFIRMATION_*, RECONCILIATION_*, PROMOTION_*, SIGNING_AUTHORITY_*, DOCUMENT_READY_FOR_SIGNATURE, DOCUMENT_RETURNED_TO_CREATED, etc.

## Validation UX

Summary: Готово / Есть предупреждения / Требуется исправление. ERROR first, then WARNING, INFO. Rule codes and field_path secondary.

## Permissions

All mutation sections: `!frozen && permission`. Translation: assign vs work vs assignee match. Backend remains authoritative.

## Tests

- `_lib/ooExperience.test.ts` — labels, timelines, fingerprint
- `_components/ooExperienceComponents.test.tsx` — section rendering, empty states, frozen banner, validation grouping, fingerprint copy
- Updated `ValidationPanel.test.tsx`

## Backend changes

**None** for OO-UI-001A.

## Deferred

Signing, EDS, registration, PDF, revision command, translator dashboard, semantic RU/KK comparison, production UX, mobile-first, OO-IMP-005.

## Readiness

Ready for commit after review. Not deployed.
