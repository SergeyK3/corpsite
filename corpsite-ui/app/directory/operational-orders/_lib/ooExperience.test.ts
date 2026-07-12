import { describe, expect, it } from "vitest";

import { auditActionLabel } from "./actionLabels";
import { buildDocumentLifecycleTimeline } from "./documentTimeline";
import { fingerprintShort } from "../_components/CompactFingerprint";
import { baseDocumentDetail } from "./testFixtures";
import {
  confirmationRoleLabel,
  confirmationStatusLabel,
  reconciliationStatusLabel,
  translationStatusLabel,
} from "./status";
import { buildWorkspaceTimeline } from "./workspaceTimeline";

describe("OO-UI-001A experience utilities", () => {
  it("maps translation status labels to Russian", () => {
    expect(translationStatusLabel("REQUESTED")).toBe("Назначен");
    expect(translationStatusLabel("COMPLETED")).toBe("Завершён");
    expect(translationStatusLabel("SUPERSEDED")).toBe("Утратил актуальность");
  });

  it("maps confirmation role and status labels", () => {
    expect(confirmationRoleLabel("CONTENT_AUTHOR")).toBe("Автор содержания");
    expect(confirmationStatusLabel("CONFIRMED")).toBe("Подтверждено");
    expect(confirmationStatusLabel("REVOKED")).toBe("Отозвано");
  });

  it("maps reconciliation status labels", () => {
    expect(reconciliationStatusLabel("PENDING")).toBe("Ожидает согласования");
    expect(reconciliationStatusLabel("RECONCILED")).toBe("Согласовано");
  });

  it("maps audit actions to human-readable labels", () => {
    expect(auditActionLabel("TRANSLATION_REQUESTED")).toBe("Запрошен перевод");
    expect(auditActionLabel("DOCUMENT_READY_FOR_SIGNATURE")).toBe("Документ передан на подпись");
    expect(auditActionLabel("UNKNOWN_CODE")).toBe("UNKNOWN_CODE");
  });

  it("builds workspace timeline with completed and current stages", () => {
    const steps = buildWorkspaceTimeline("TRANSLATION_IN_PROGRESS");
    expect(steps.find((s) => s.id === "submitted")?.state).toBe("completed");
    expect(steps.find((s) => s.id === "translation")?.state).toBe("current");
    expect(steps.find((s) => s.id === "promoted")?.state).toBe("future");
  });

  it("marks review step blocked during clarification", () => {
    const steps = buildWorkspaceTimeline("CLARIFICATION_REQUIRED");
    expect(steps.find((s) => s.id === "reviewed")?.state).toBe("blocked");
  });

  it("builds document lifecycle timeline with deferred signing steps", () => {
    const steps = buildDocumentLifecycleTimeline(baseDocumentDetail());
    expect(steps.find((s) => s.id === "created")?.state).toBe("current");
    expect(steps.find((s) => s.id === "signed")?.state).toBe("deferred");
    expect(steps.find((s) => s.id === "registered")?.state).toBe("deferred");
  });

  it("shows ready for signature as completed when status matches", () => {
    const steps = buildDocumentLifecycleTimeline(
      baseDocumentDetail({
        document: {
          ...baseDocumentDetail().document,
          status: "READY_FOR_SIGNATURE",
          ready_for_signature_at: "2026-01-12T10:00:00Z",
        },
        signing_authority: {
          id: 1,
          document_id: 42,
          document_version_id: 1,
          authority_party_type: "PERSON",
          authority_party_reference: "300",
          authority_display_name: "Director",
          authority_position_id: null,
          authority_org_unit_id: null,
          authority_basis: null,
          assigned_by_user_id: 100,
          status: "ACTIVE",
          assigned_at: "2026-01-11T10:00:00Z",
          superseded_at: null,
          version: 1,
        },
        readiness_validation: { is_valid: true, has_errors: false, has_warnings: false, issues: [] },
      }),
    );
    expect(steps.find((s) => s.id === "ready_for_signature")?.state).toBe("completed");
    expect(steps.find((s) => s.id === "signed")?.state).toBe("deferred");
  });

  it("shortens fingerprint for compact display", () => {
    expect(fingerprintShort("a91f1234567890e42c")).toBe("a91f…e42c");
    expect(fingerprintShort(null)).toBe("—");
  });
});
