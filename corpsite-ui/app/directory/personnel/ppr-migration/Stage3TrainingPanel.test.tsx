import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Stage3TrainingPanel from "./Stage3TrainingPanel";
import { apiFetchJson } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));
const api = vi.mocked(apiFetchJson);

const run = (status = "DRY_RUN_COMPLETED", pausedOperation?: string) => ({
  run: { stage_run_id: 73, stage0_cohort_run_id: 9, status, current_position: 1, paused_operation: pausedOperation },
  counts: { COMPLETED: 0, SKIPPED_BY_DECISION: 0 },
  participants: [{
    stage_run_participant_id: 11, position: 1, employee_id: 101, person_id: 201, status: "PENDING",
    fragments: [{ fragment_index: 0, source: { title: "ACLS", provider_name: "Provider" }, current: {}, proposal: { title: "ACLS", training_kind: "course" }, outcome: "READY_TO_ADD", reason_code: "STAGE3_READY" }],
  }],
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Stage3TrainingPanel", () => {
  it("keeps dry-run and explicit run creation separate", async () => {
    const preview = { stage0_cohort_run_id: 9, preview_fingerprint: "a".repeat(64), participant_count: 1 };
    api.mockResolvedValueOnce(preview as never).mockResolvedValueOnce(run() as never);
    render(<Stage3TrainingPanel cohortRunId={9} />);
    fireEvent.click(screen.getByRole("button", { name: "Выполнить dry-run preview" }));
    expect(await screen.findByText(/личные карточки не изменялись/)).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-3/training/preview", { method: "POST", body: { stage0_cohort_run_id: 9 } });
    fireEvent.click(screen.getByRole("button", { name: "Создать запуск" }));
    await screen.findByText("Сотрудник #101");
    expect(api).toHaveBeenLastCalledWith("/personnel/ppr-migration/stage-3/training/runs", { method: "POST", body: { stage0_cohort_run_id: 9, preview_fingerprint: "a".repeat(64) } });
    expect(screen.queryByText("safe_snapshot")).not.toBeInTheDocument();
  });

  it("does not render a redacted certificate and requires a skip reason", async () => {
    api.mockResolvedValueOnce(run() as never).mockResolvedValueOnce(run() as never);
    render(<Stage3TrainingPanel cohortRunId={9} />);
    fireEvent.change(screen.getByLabelText("ID запуска Stage 3"), { target: { value: "73" } });
    fireEvent.click(screen.getByRole("button", { name: "Открыть запуск" }));
    const card = await screen.findByRole("article", { name: "Участник 1" });
    expect(card).not.toHaveTextContent("сертификат:");
    expect(screen.getByRole("button", { name: "Исключить участника" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Причина исключения 1"), { target: { value: "Неоднозначный источник" } });
    fireEvent.click(screen.getByRole("button", { name: "Исключить участника" }));
    await waitFor(() => expect(api).toHaveBeenLastCalledWith("/personnel/ppr-migration/stage-3/training/runs/73/participants/11/skip", { method: "POST", body: { reason: "Неоднозначный источник" } }));
  });

  it("explains FastAPI disabled, stale and forbidden responses", async () => {
    api.mockRejectedValueOnce({ status: 403, details: { detail: { code: "STAGE3_COHORT_OUT_OF_SCOPE" } } })
      .mockRejectedValueOnce({ status: 409, details: { detail: { code: "STAGE3_PREVIEW_STALE" } } })
      .mockRejectedValueOnce({ status: 409, details: { detail: { code: "STAGE3_PREVIEW_DISABLED" } } });
    render(<Stage3TrainingPanel cohortRunId={9} />);
    fireEvent.click(screen.getByRole("button", { name: "Выполнить dry-run preview" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Нет права Stage 3");
    fireEvent.click(screen.getByRole("button", { name: "Выполнить dry-run preview" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Исходные данные изменились");
    fireEvent.click(screen.getByRole("button", { name: "Выполнить dry-run preview" }));
    expect(await screen.findByRole("status")).toHaveTextContent("отключена feature flag");
  });

  it("invalidates approval on skip and allows a new approval", async () => {
    const approved = run("APPROVED");
    const invalidated = run("DRY_RUN_COMPLETED"); invalidated.participants[0].status = "SKIPPED_BY_DECISION";
    api.mockResolvedValueOnce(run() as never).mockResolvedValueOnce(approved as never)
      .mockResolvedValueOnce(invalidated as never).mockResolvedValueOnce(approved as never);
    render(<Stage3TrainingPanel cohortRunId={9} />);
    fireEvent.change(screen.getByLabelText("ID запуска Stage 3"), { target: { value: "73" } });
    fireEvent.click(screen.getByRole("button", { name: "Открыть запуск" }));
    fireEvent.click(await screen.findByRole("button", { name: "Утвердить запуск" }));
    await screen.findByRole("button", { name: "Исключить участника" });
    fireEvent.change(screen.getByLabelText("Причина исключения 1"), { target: { value: "Решение HR" } });
    fireEvent.click(screen.getByRole("button", { name: "Исключить участника" }));
    expect(await screen.findByRole("button", { name: "Утвердить запуск" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Утвердить запуск" }));
    await waitFor(() => expect(api).toHaveBeenLastCalledWith("/personnel/ppr-migration/stage-3/training/runs/73/approve", { method: "POST", body: {} }));
  });

  it("uses execute, resume, cancel and retry-accept only for their allowed states", async () => {
    const pausedExecution = run("PAUSED_ON_ERROR", "PARTICIPANT_EXECUTION");
    pausedExecution.run.stopped_participant_id = 11; pausedExecution.participants[0].status = "ERROR";
    const running = run("RUNNING");
    const pausedAcceptance = run("PAUSED_ON_ERROR", "ACCEPTANCE");
    api.mockResolvedValueOnce(run("APPROVED") as never).mockResolvedValueOnce(pausedExecution as never)
      .mockResolvedValueOnce(running as never).mockResolvedValueOnce(run("CANCELLED") as never)
      .mockResolvedValueOnce(pausedAcceptance as never)
      .mockResolvedValueOnce({ stage_run_id: 73, employee_count: 1, records_by_kind: { course: 1 }, skipped_count: 0, acceptance_fingerprint: "c".repeat(64) } as never)
      .mockResolvedValueOnce(run("ACCEPTED") as never);
    render(<Stage3TrainingPanel cohortRunId={9} />);
    fireEvent.change(screen.getByLabelText("ID запуска Stage 3"), { target: { value: "73" } });
    fireEvent.click(screen.getByRole("button", { name: "Открыть запуск" }));
    fireEvent.click(await screen.findByRole("button", { name: "Обработать следующего" }));
    expect(await screen.findByRole("button", { name: "Продолжить обработку" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Продолжить обработку" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-3/training/runs/73/resume", { method: "POST", body: {} }));
    expect(screen.queryByRole("button", { name: "Исключить участника" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Причина отмены Stage 3"), { target: { value: "Отмена HR" } });
    fireEvent.click(screen.getByRole("button", { name: "Отменить запуск" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-3/training/runs/73/cancel", { method: "POST", body: { reason: "Отмена HR" } }));
    // Re-open an acceptance pause and confirm the retry endpoint uses the current summary fingerprint.
    fireEvent.click(screen.getByRole("button", { name: "Открыть запуск" }));
    fireEvent.click(await screen.findByRole("button", { name: "Повторить принятие" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Повторить принятие" }));
    await waitFor(() => expect(api).toHaveBeenLastCalledWith("/personnel/ppr-migration/stage-3/training/runs/73/retry-accept", { method: "POST", body: { stage_run_id: 73, acceptance_fingerprint: "c".repeat(64) } }));
  });

  it("uses permitted controls and server acceptance summary", async () => {
    const complete = run("COMPLETED_PENDING_REVIEW");
    expect(complete.run.status).toBe("COMPLETED_PENDING_REVIEW");
    complete.counts.COMPLETED = 1;
    complete.participants[0].status = "COMPLETED";
    const accepted = run("ACCEPTED"); accepted.participants[0].status = "COMPLETED";
    api.mockResolvedValueOnce(complete as never)
      .mockResolvedValueOnce({ stage_run_id: 73, employee_count: 1, records_by_kind: { course: 1 }, skipped_count: 0, acceptance_fingerprint: "b".repeat(64) } as never)
      .mockResolvedValueOnce(accepted as never);
    render(<Stage3TrainingPanel cohortRunId={9} />);
    fireEvent.change(screen.getByLabelText("ID запуска Stage 3"), { target: { value: "73" } });
    fireEvent.click(screen.getByRole("button", { name: "Открыть запуск" }));
    fireEvent.click(await screen.findByRole("button", { name: "Показать итог принятия" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("course: 1");
    fireEvent.click(within(dialog).getByRole("button", { name: "Принять этап" }));
    await screen.findByText("Этап принят: данные записаны через PPR bridge.");
    expect(api).toHaveBeenLastCalledWith("/personnel/ppr-migration/stage-3/training/runs/73/accept", { method: "POST", body: { stage_run_id: 73, acceptance_fingerprint: "b".repeat(64) } });
  });
});
