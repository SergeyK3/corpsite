import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { buildDocumentLifecycleTimeline } from "../_lib/documentTimeline";
import { baseDocumentDetail, baseWorkspaceDetail } from "../_lib/testFixtures";
import { buildWorkspaceTimeline } from "../_lib/workspaceTimeline";
import AuditSections from "./AuditSections";
import BilingualReconciliationsSection from "./BilingualReconciliationsSection";
import CompactFingerprint from "./CompactFingerprint";
import ContentConfirmationsSection from "./ContentConfirmationsSection";
import DocumentLifecycleTimeline from "./DocumentLifecycleTimeline";
import FrozenWorkspaceBanner from "./FrozenWorkspaceBanner";
import TranslationAssignmentsSection from "./TranslationAssignmentsSection";
import ValidationPanel from "./ValidationPanel";
import WorkspaceProgressTimeline from "./WorkspaceProgressTimeline";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

afterEach(() => cleanup());

const fullPerms = {
  intake_create: true,
  intake_read: true,
  intake_operate: true,
  translation_assign: true,
  translation_work: true,
  content_confirm: true,
  reconcile: true,
  editorial_ready: true,
  promote: true,
  signature_readiness_read: true,
  assign_signing_authority: true,
  mark_ready_for_signature: true,
  return_from_signature: true,
};

describe("OO-UI-001A section components", () => {
  it("renders translation assignment cards with Russian status", () => {
    const detail = baseWorkspaceDetail({
      translation_assignments: [
        {
          id: 7,
          workspace_id: 1,
          source_locale: "ru",
          target_locale: "kk",
          assigned_to_type: "PERSON",
          assigned_to_reference: "500",
          assigned_to_display_name: "Translator",
          assigned_by_user_id: 100,
          status: "IN_PROGRESS",
          requested_at: "2026-01-03T10:00:00Z",
          accepted_at: "2026-01-03T11:00:00Z",
          completed_at: null,
          cancelled_at: null,
          due_at: "2026-01-05T10:00:00Z",
          source_block_version: 2,
          target_block_version: 1,
          source_content_fingerprint: "a91f1234567890e42c",
          produced_content_fingerprint: null,
          notes: "Priority",
          version: 2,
          created_at: "2026-01-03T10:00:00Z",
          updated_at: "2026-01-03T11:00:00Z",
        },
      ],
    });

    render(
      <TranslationAssignmentsSection
        detail={detail}
        frozen={false}
        perms={fullPerms}
        me={{ user_id: 500 } as never}
        pending={false}
        onUpdated={() => {}}
        onError={() => {}}
      />,
    );

    expect(screen.getByTestId("translation-assignment-7")).toBeTruthy();
    expect(screen.getByText("RU → KK")).toBeTruthy();
    expect(screen.getByText("Выполняется")).toBeTruthy();
    expect(screen.getByText("Priority")).toBeTruthy();
  });

  it("shows translation empty state", () => {
    render(
      <TranslationAssignmentsSection
        detail={baseWorkspaceDetail()}
        frozen={false}
        perms={fullPerms}
        me={null}
        pending={false}
        onUpdated={() => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByTestId("translations-empty").textContent).toContain("Перевод не назначен");
  });

  it("hides translation assign button when workspace frozen", () => {
    render(
      <TranslationAssignmentsSection
        detail={baseWorkspaceDetail()}
        frozen
        perms={fullPerms}
        me={null}
        pending={false}
        onUpdated={() => {}}
        onError={() => {}}
      />,
    );
    expect(screen.queryByText("Назначить перевод")).toBeNull();
  });

  it("renders confirmation role and status labels", () => {
    const detail = baseWorkspaceDetail({
      content_confirmations: [
        {
          id: 3,
          workspace_id: 1,
          locale: "ru",
          block_id: 1,
          block_version: 2,
          content_fingerprint: "a91f1234567890e42c",
          confirmer_party_type: "PERSON",
          confirmer_party_reference: "200",
          confirmer_display_name: "Author",
          confirmer_user_id: 200,
          confirmation_role: "CONTENT_AUTHOR",
          status: "CONFIRMED",
          confirmed_at: "2026-01-04T10:00:00Z",
          revoked_at: null,
          revocation_reason: null,
          version: 1,
          created_at: "2026-01-04T10:00:00Z",
        },
      ],
    });

    render(
      <ContentConfirmationsSection detail={detail} frozen={false} perms={fullPerms} pending={false} onUpdated={() => {}} onError={() => {}} />,
    );

    const card = screen.getByTestId("confirmation-3");
    expect(card.textContent).toContain("Автор содержания");
    expect(card.textContent).toContain("Подтверждено");
  });

  it("shows confirmations empty state", () => {
    render(
      <ContentConfirmationsSection detail={baseWorkspaceDetail()} frozen={false} perms={fullPerms} pending={false} onUpdated={() => {}} onError={() => {}} />,
    );
    expect(screen.getByTestId("confirmations-empty").textContent).toContain("Подтверждений пока нет");
  });

  it("renders reconciliation RU/KK pair", () => {
    const detail = baseWorkspaceDetail({
      bilingual_reconciliations: [
        {
          id: 9,
          workspace_id: 1,
          ru_block_id: 1,
          kk_block_id: 2,
          ru_block_version: 2,
          kk_block_version: 1,
          ru_content_fingerprint: "a91f1234567890e42c",
          kk_content_fingerprint: "b82e1234567890f53d",
          status: "RECONCILED",
          reconciled_by_user_id: 100,
          reconciled_at: "2026-01-05T10:00:00Z",
          invalidation_reason: null,
          invalidated_at: null,
          version: 1,
          notes: null,
          created_at: "2026-01-05T10:00:00Z",
        },
      ],
    });

    render(
      <BilingualReconciliationsSection detail={detail} frozen={false} perms={fullPerms} pending={false} onUpdated={() => {}} onError={() => {}} />,
    );

    expect(screen.getByTestId("reconciliation-9")).toBeTruthy();
    expect(screen.getByText("Русский текст")).toBeTruthy();
    expect(screen.getByText("Казахский текст")).toBeTruthy();
    expect(screen.getByText("↔")).toBeTruthy();
    expect(screen.getByText("Согласовано")).toBeTruthy();
  });

  it("shows reconciliation empty state", () => {
    render(
      <BilingualReconciliationsSection detail={baseWorkspaceDetail()} frozen={false} perms={fullPerms} pending={false} onUpdated={() => {}} onError={() => {}} />,
    );
    expect(screen.getByTestId("reconciliations-empty").textContent).toContain("Двуязычное согласование ещё не выполнено");
  });

  it("renders frozen banner with document link and revision advisory", () => {
    render(
      <FrozenWorkspaceBanner documentId={42} promotedAt="2026-01-10T10:00:00Z" workspaceDriftDetected revisionRecommended />,
    );

    expect(screen.getByTestId("workspace-frozen-banner")).toBeTruthy();
    expect(screen.getByText("Официальный проект создан")).toBeTruthy();
    const link = screen.getByRole("link", { name: "#42" });
    expect(link.getAttribute("href")).toBe("/directory/operational-orders/documents/42");
    expect(screen.getByTestId("revision-advisory")).toBeTruthy();
  });

  it("renders workspace progress timeline states", () => {
    render(<WorkspaceProgressTimeline steps={buildWorkspaceTimeline("EDITORIAL_PACKAGE_READY")} />);
    expect(screen.getByTestId("workspace-progress-timeline")).toBeTruthy();
    expect(screen.getByTestId("workspace-timeline-step-editorial_ready").getAttribute("data-state")).toBe("current");
    expect(screen.getByTestId("workspace-timeline-step-promoted").getAttribute("data-state")).toBe("future");
  });

  it("renders document lifecycle timeline with deferred steps", () => {
    render(<DocumentLifecycleTimeline steps={buildDocumentLifecycleTimeline(baseDocumentDetail())} />);
    expect(screen.getByTestId("document-lifecycle-timeline")).toBeTruthy();
    expect(screen.getByTestId("document-timeline-step-signed").getAttribute("data-state")).toBe("deferred");
    expect(screen.getAllByText("Ещё не реализовано").length).toBeGreaterThan(0);
  });

  it("renders audit entries with human-readable labels", () => {
    render(
      <AuditSections
        audit={[{ audit_id: 1, action: "PROMOTION_COMPLETED", actor_user_id: 100, created_at: "2026-01-10T10:00:00Z" }]}
        provenance={[]}
      />,
    );
    expect(screen.getByText("Promotion завершён")).toBeTruthy();
    expect(screen.queryByTestId("audit-empty")).toBeNull();
  });

  it("shows audit empty state", () => {
    render(<AuditSections audit={[]} provenance={[]} />);
    expect(screen.getByTestId("audit-empty").textContent).toContain("История пока отсутствует");
  });

  it("groups validation issues by severity with summary", () => {
    render(
      <ValidationPanel
        title="Test Validation"
        validation={{
          is_valid: false,
          has_errors: true,
          has_warnings: true,
          issues: [
            { code: "W001", severity: "WARNING", message: "Optional field", field_path: "notes" },
            { code: "E001", severity: "ERROR", message: "Required field", field_path: "title" },
            { code: "I001", severity: "INFO", message: "Hint", field_path: null },
          ],
        }}
      />,
    );

    expect(screen.getByTestId("validation-summary").textContent).toContain("Требуется исправление");
    expect(screen.getByTestId("validation-group-ERROR")).toBeTruthy();
    expect(screen.getByTestId("validation-group-WARNING")).toBeTruthy();
    expect(screen.getByTestId("validation-group-INFO")).toBeTruthy();
  });

  it("expands and copies compact fingerprint", async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    render(<CompactFingerprint value="a91f1234567890e42c" label="fp" />);
    expect(screen.getByText("a91f…e42c")).toBeTruthy();

    fireEvent.click(screen.getByText("Показать"));
    expect(screen.getByText("a91f1234567890e42c")).toBeTruthy();

    fireEvent.click(screen.getByText("Копировать"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("a91f1234567890e42c");
  });
});
