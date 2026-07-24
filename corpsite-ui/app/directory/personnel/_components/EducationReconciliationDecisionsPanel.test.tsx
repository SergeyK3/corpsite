import { describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import EducationReconciliationDecisionsPanel from "./EducationReconciliationDecisionsPanel";
import type {
  ApplyEducationReconciliationDecisionResponse,
  IntakeReconciliationDecision,
} from "../_lib/personnelApplicationsApi.client";
import * as personnelApplicationsApi from "../_lib/personnelApplicationsApi.client";

vi.mock("../_lib/personnelApplicationsApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/personnelApplicationsApi.client")>();
  return {
    ...actual,
    listIntakeReconciliationDecisions: vi.fn(),
    applyEducationReconciliationDecision: vi.fn(),
  };
});

const listMock = vi.mocked(personnelApplicationsApi.listIntakeReconciliationDecisions);
const applyMock = vi.mocked(personnelApplicationsApi.applyEducationReconciliationDecision);

const pendingDecision: IntakeReconciliationDecision = {
  decision_id: 101,
  application_id: 42,
  person_id: 7,
  section_code: "education",
  proposal_index: 0,
  action: "add",
  reason_code: "MATCH_NONE_CONFIDENT",
  apply_status: "pending",
  target_canonical_record_id: null,
  expected_row_version: null,
  failure_evidence: null,
  row_version: 1,
};

const educationPayload = [
  {
    education_type: "basic",
    institution: "КазНУ",
    year_from: "2015-09-01",
    year_to: "2019-06-30",
  },
];

const singleEducationPayload = {
  education_type: "basic",
  institution: "Медуни",
  year_from: "1987-09-01",
  year_to: "1993-06-30",
  specialty: "Лечебное дело",
  qualification: "Врач",
  document_type: "diploma",
  diploma_number: "123",
};

function appliedResponse(
  overrides: Partial<ApplyEducationReconciliationDecisionResponse> = {},
): ApplyEducationReconciliationDecisionResponse {
  return {
    application_id: 42,
    decision_id: 101,
    section_code: "education",
    action: "add",
    apply_status: "applied",
    reason_code: "MATCH_NONE_CONFIDENT",
    result_status: "applied",
    idempotent_replay: false,
    redecide_required: false,
    ppr_command_id: "recon-apply:x",
    section_record_id: 9,
    failure_evidence: null,
    expected_row_version: null,
    target_canonical_record_id: null,
    ...overrides,
  };
}

describe("EducationReconciliationDecisionsPanel", () => {
  beforeEach(() => {
    cleanup();
    listMock.mockReset();
    applyMock.mockReset();
  });

  it("applies pending decision and shows applied status", async () => {
    listMock.mockResolvedValue({
      application_id: 42,
      section_code: "education",
      items: [pendingDecision],
      total: 1,
    });
    applyMock.mockResolvedValue(appliedResponse());
    const onReviewDataChanged = vi.fn().mockResolvedValue(undefined);

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
        onReviewDataChanged={onReviewDataChanged}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    await waitFor(() => {
      expect(applyMock).toHaveBeenCalledWith(42, 101, { records: educationPayload });
    });
    expect(await screen.findByTestId("education-recon-decisions-notice")).toHaveTextContent(
      "Решение применено",
    );
    expect(onReviewDataChanged).toHaveBeenCalled();
  });

  it("wraps single education object when applying", async () => {
    listMock.mockResolvedValue({
      application_id: 178,
      section_code: "education",
      items: [{ ...pendingDecision, application_id: 178, decision_id: 201 }],
      total: 1,
    });
    applyMock.mockResolvedValue(appliedResponse({ application_id: 178, decision_id: 201 }));

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={178}
        educationPayload={singleEducationPayload}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-201"));

    await waitFor(() => {
      expect(applyMock).toHaveBeenCalledWith(178, 201, { records: [singleEducationPayload] });
    });
  });

  it("shows blocked message requiring redecide", async () => {
    listMock
      .mockResolvedValueOnce({
        application_id: 42,
        section_code: "education",
        items: [pendingDecision],
        total: 1,
      })
      .mockResolvedValue({
        application_id: 42,
        section_code: "education",
        items: [
          {
            ...pendingDecision,
            apply_status: "blocked",
            reason_code: "APPLY_STALE_ROW_VERSION",
            failure_evidence: { reason_code: "APPLY_STALE_ROW_VERSION" },
          },
        ],
        total: 1,
      });
    applyMock.mockResolvedValue(
      appliedResponse({
        action: "update_version",
        apply_status: "blocked",
        reason_code: "APPLY_STALE_ROW_VERSION",
        result_status: "blocked_new_decide_required",
        redecide_required: true,
        ppr_command_id: null,
        section_record_id: null,
        failure_evidence: { reason_code: "APPLY_STALE_ROW_VERSION" },
        expected_row_version: "2026-07-24T10:00:00",
        target_canonical_record_id: 5,
      }),
    );

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    expect(await screen.findByTestId("education-recon-decisions-notice")).toHaveTextContent(
      "Данные изменились. Решение необходимо принять повторно",
    );
    expect(await screen.findByTestId("education-recon-blocked-101")).toHaveTextContent(
      "APPLY_STALE_ROW_VERSION",
    );
  });

  it("shows blocked message on idempotent replay", async () => {
    listMock
      .mockResolvedValueOnce({
        application_id: 42,
        section_code: "education",
        items: [pendingDecision],
        total: 1,
      })
      .mockResolvedValue({
        application_id: 42,
        section_code: "education",
        items: [
          {
            ...pendingDecision,
            apply_status: "blocked",
            reason_code: "APPLY_STALE_ROW_VERSION",
          },
        ],
        total: 1,
      });
    applyMock.mockResolvedValue(
      appliedResponse({
        apply_status: "blocked",
        reason_code: "APPLY_STALE_ROW_VERSION",
        result_status: "blocked_new_decide_required",
        idempotent_replay: true,
        redecide_required: true,
        ppr_command_id: null,
        section_record_id: null,
        failure_evidence: { reason_code: "APPLY_STALE_ROW_VERSION" },
      }),
    );

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    expect(await screen.findByTestId("education-recon-decisions-notice")).toHaveTextContent(
      "Данные изменились. Решение необходимо принять повторно",
    );
    expect(screen.getByTestId("education-recon-decisions-notice")).not.toHaveTextContent(
      "Решение применено",
    );
  });

  it("shows failed evidence on idempotent replay", async () => {
    listMock
      .mockResolvedValueOnce({
        application_id: 42,
        section_code: "education",
        items: [pendingDecision],
        total: 1,
      })
      .mockResolvedValue({
        application_id: 42,
        section_code: "education",
        items: [
          {
            ...pendingDecision,
            apply_status: "failed",
            failure_evidence: { reason_code: "PPR_WRITE_FAILED", detail: "section unavailable" },
          },
        ],
        total: 1,
      });
    applyMock.mockResolvedValue(
      appliedResponse({
        apply_status: "failed",
        reason_code: "PPR_WRITE_FAILED",
        result_status: "failed",
        idempotent_replay: true,
        ppr_command_id: null,
        section_record_id: null,
        failure_evidence: { reason_code: "PPR_WRITE_FAILED", detail: "section unavailable" },
      }),
    );

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    expect(await screen.findByTestId("education-recon-decisions-notice")).toHaveTextContent(
      "PPR_WRITE_FAILED: section unavailable",
    );
    expect(screen.getByTestId("education-recon-decisions-notice")).not.toHaveTextContent(
      "Решение применено",
    );
  });

  it("handles PROPOSAL_DIGEST_MISMATCH 422 and refreshes data", async () => {
    listMock.mockResolvedValue({
      application_id: 42,
      section_code: "education",
      items: [pendingDecision],
      total: 1,
    });
    applyMock.mockRejectedValue({
      status: 422,
      details: { detail: { code: "PROPOSAL_DIGEST_MISMATCH", message: "mismatch" } },
    });
    const onReviewDataChanged = vi.fn().mockResolvedValue(undefined);

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
        onReviewDataChanged={onReviewDataChanged}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    expect(await screen.findByTestId("education-recon-decisions-error")).toHaveTextContent(
      "Предложение устарело",
    );
    expect(onReviewDataChanged).toHaveBeenCalled();
  });

  it("keeps stale proposal message when review refresh fails after digest mismatch", async () => {
    listMock.mockResolvedValue({
      application_id: 42,
      section_code: "education",
      items: [pendingDecision],
      total: 1,
    });
    applyMock.mockRejectedValue({
      status: 422,
      details: { detail: { code: "PROPOSAL_DIGEST_MISMATCH", message: "mismatch" } },
    });
    const onReviewDataChanged = vi.fn().mockRejectedValue(new Error("review refresh failed"));

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
        onReviewDataChanged={onReviewDataChanged}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    expect(await screen.findByTestId("education-recon-decisions-error")).toHaveTextContent(
      "Предложение устарело",
    );
    expect(await screen.findByTestId("education-recon-decisions-refresh-error")).toHaveTextContent(
      "review refresh failed",
    );
    expect(onReviewDataChanged).toHaveBeenCalled();
  });

  it("keeps stale proposal message when decisions reload fails after digest mismatch", async () => {
    listMock
      .mockResolvedValueOnce({
        application_id: 42,
        section_code: "education",
        items: [pendingDecision],
        total: 1,
      })
      .mockRejectedValueOnce(new Error("decisions reload failed"));
    applyMock.mockRejectedValue({
      status: 422,
      details: { detail: { code: "PROPOSAL_DIGEST_MISMATCH", message: "mismatch" } },
    });
    const onReviewDataChanged = vi.fn().mockResolvedValue(undefined);

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
        onReviewDataChanged={onReviewDataChanged}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    expect(await screen.findByTestId("education-recon-decisions-error")).toHaveTextContent(
      "Предложение устарело",
    );
    expect(await screen.findByTestId("education-recon-decisions-refresh-error")).toHaveTextContent(
      "decisions reload failed",
    );
    expect(onReviewDataChanged).toHaveBeenCalled();
  });

  it("shows empty state for application 178 when GET returns no education decisions", async () => {
    listMock.mockResolvedValue({
      application_id: 178,
      section_code: "education",
      items: [],
      total: 0,
    });

    render(
      <EducationReconciliationDecisionsPanel applicationId={178} educationPayload={educationPayload} />,
    );

    expect(await screen.findByTestId("education-recon-decisions-panel")).toBeInTheDocument();
    expect(screen.getByText("Решения сверки (образование)")).toBeInTheDocument();
    expect(screen.getByTestId("education-recon-decisions-empty")).toHaveTextContent("Решений сверки нет");
    expect(listMock).toHaveBeenCalledWith(178, "education");
    expect(screen.queryByRole("button", { name: /применить/i })).not.toBeInTheDocument();
  });

  it("keeps apply notice when review refresh fails after success", async () => {
    listMock.mockResolvedValue({
      application_id: 42,
      section_code: "education",
      items: [pendingDecision],
      total: 1,
    });
    applyMock.mockResolvedValue(appliedResponse());
    const onReviewDataChanged = vi.fn().mockRejectedValue(new Error("review refresh failed"));

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
        onReviewDataChanged={onReviewDataChanged}
      />,
    );

    fireEvent.click(await screen.findByTestId("education-recon-apply-101"));

    expect(await screen.findByTestId("education-recon-decisions-notice")).toHaveTextContent(
      "Решение применено",
    );
    expect(await screen.findByTestId("education-recon-decisions-refresh-error")).toHaveTextContent(
      "review refresh failed",
    );
    expect(screen.queryByTestId("education-recon-decisions-error")).not.toBeInTheDocument();
  });

  it("blocks double click while apply is in flight", async () => {
    listMock.mockResolvedValue({
      application_id: 42,
      section_code: "education",
      items: [pendingDecision],
      total: 1,
    });
    let resolveApply: (value: ApplyEducationReconciliationDecisionResponse) => void = () => {};
    const applyPromise = new Promise<ApplyEducationReconciliationDecisionResponse>((resolve) => {
      resolveApply = resolve;
    });
    applyMock.mockReturnValue(applyPromise);

    render(
      <EducationReconciliationDecisionsPanel
        applicationId={42}
        educationPayload={educationPayload}
      />,
    );

    const button = await screen.findByTestId("education-recon-apply-101");
    fireEvent.click(button);
    await waitFor(() => expect(button).toHaveTextContent("Применение…"));
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(applyMock).toHaveBeenCalledTimes(1);

    resolveApply(appliedResponse());

    await waitFor(() => {
      expect(screen.getByTestId("education-recon-decisions-notice")).toHaveTextContent(
        "Решение применено",
      );
    });
  });
});
