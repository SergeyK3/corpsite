import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Stage2EducationPanel from "./Stage2EducationPanel";
import { apiFetchJson } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));
const api = vi.mocked(apiFetchJson);

const baseRun = (status = "DRY_RUN_COMPLETED", pausedOperation?: string) => ({
  run: { stage_run_id: 44, status, current_position: 2, paused_operation: pausedOperation },
  counts: { COMPLETED: 1, SKIPPED_BY_DECISION: 1 },
  participants: [
    { stage_run_participant_id: 5, position: 2, employee_id: 202, status: "PENDING", fragments: [{ fragment_index: 1, source: { institution_name: "Колледж Б" }, current: {}, proposal: { institution_name: "Колледж Б" }, outcome: "READY_TO_ADD", reason_code: "STAGE2_KIND_BASIC" }] },
    { stage_run_participant_id: 4, position: 1, employee_id: 101, status: "COMPLETED", fragments: [{ fragment_index: 0, source: { institution_name: "Университет А" }, current: { institution_name: "Университет А" }, proposal: {}, outcome: "ALREADY_APPLIED", reason_code: "STAGE2_EXACT_PROVENANCE_MATCH" }, { fragment_index: 2, source: { institution_name: "Магистратура" }, current: { institution_name: "Другая" }, proposal: { institution_name: "Магистратура" }, outcome: "CANONICAL_CONFLICT", reason_code: "STAGE2_CANONICAL_VALUE_CONFLICT" }] },
  ],
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Stage2EducationPanel", () => {
  it("opens preview, keeps frozen participant order and groups several fragments", async () => {
    api.mockResolvedValueOnce(baseRun() as never);
    render(<Stage2EducationPanel cohortRunId={9} />);
    fireEvent.click(screen.getByRole("button", { name: "Проверить образование" }));
    await screen.findByText("Сотрудник #101");
    expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-2/education/preview", { method: "POST", body: { stage0_cohort_run_id: 9 } });
    expect(screen.getAllByText("Фрагмент")).toHaveLength(2);
    expect(screen.getByText("Уже записано")).toBeInTheDocument();
    expect(screen.getByText("Конфликт — требуется решение")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("990101123456");
    const cards = screen.getAllByRole("article");
    expect(cards[0]).toHaveTextContent("Сотрудник #101");
    expect(cards[0]).toHaveTextContent("#1");
    expect(cards[0]).toHaveTextContent("#3");
  });

  it("sends approve, execute, skip and cancel actions once", async () => {
    api.mockResolvedValueOnce(baseRun()).mockResolvedValueOnce(baseRun("APPROVED")).mockResolvedValueOnce(baseRun("RUNNING")).mockResolvedValueOnce(baseRun("RUNNING")).mockResolvedValueOnce(baseRun("CANCELLED"));
    render(<Stage2EducationPanel cohortRunId={9} />);
    fireEvent.click(screen.getByRole("button", { name: "Проверить образование" }));
    await screen.findByRole("button", { name: "Утвердить запуск" });
    fireEvent.click(screen.getByRole("button", { name: "Утвердить запуск" }));
    await screen.findByRole("button", { name: "Обработать следующего" });
    fireEvent.click(screen.getByRole("button", { name: "Обработать следующего" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-2/education/runs/44/execute-next", { method: "POST", body: {} }));
    fireEvent.change(screen.getByLabelText("Причина исключения 2"), { target: { value: "Проверено" } });
    fireEvent.click(screen.getByRole("button", { name: "Исключить участника" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-2/education/runs/44/participants/5/skip", { method: "POST", body: { reason: "Проверено" } }));
    fireEvent.change(screen.getByLabelText("Причина отмены"), { target: { value: "Тест" } });
    fireEvent.click(screen.getByRole("button", { name: "Отменить прогон" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-2/education/runs/44/cancel", { method: "POST", body: { reason: "Тест" } }));
  });

  it("shows the correct resume action for each pause and stale guidance", async () => {
    const stale = baseRun("PAUSED_ON_ERROR", "PARTICIPANT_EXECUTION");
    stale.run.stage0_cohort_run_id = 9;
    stale.participants[0].error_code = "STAGE2_RESUME_STALE";
    api.mockResolvedValueOnce(stale as never);
    render(<Stage2EducationPanel cohortRunId={9} />);
    fireEvent.click(screen.getByRole("button", { name: "Проверить образование" }));
    expect(await screen.findByRole("button", { name: "Создать новый PREVIEW" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Продолжить обработку" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("status").map((node) => node.textContent).join(" ")).toContain("Требуется новый PREVIEW");
    expect(screen.getAllByRole("status").map((node) => node.textContent).join(" ")).toContain("Текущий прогон продолжить нельзя");
    fireEvent.click(screen.getByRole("button", { name: "Создать новый PREVIEW" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/personnel/ppr-migration/stage-2/education/preview", { method: "POST", body: { stage0_cohort_run_id: 9 } }));
    api.mockClear(); api.mockResolvedValueOnce(baseRun("PAUSED_ON_ERROR", "ACCEPTANCE") as never).mockResolvedValueOnce({ stage_run_id: 44, employee_count: 2, records_by_kind: { basic: 1 }, skipped_count: 1, acceptance_fingerprint: "a".repeat(64) } as never);
    fireEvent.change(screen.getByLabelText("ID прогона"), { target: { value: "44" } });
    fireEvent.click(screen.getByRole("button", { name: "Открыть прогон" }));
    expect(await screen.findByRole("button", { name: "Повторить принятие" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторить принятие" }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("Будет записано");
  });

  it("disables approval while a review-required or conflict fragment remains", async () => {
    const blocked = baseRun();
    blocked.participants[0].fragments[0].outcome = "REVIEW_REQUIRED";
    api.mockResolvedValueOnce(blocked as never);
    render(<Stage2EducationPanel cohortRunId={9} />);
    fireEvent.click(screen.getByRole("button", { name: "Проверить образование" }));
    expect(await screen.findByRole("button", { name: "Утвердить запуск" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Утверждение недоступно");
  });

  it("uses server acceptance summary and shows accepted replay", async () => {
    const accepted = baseRun("ACCEPTED");
    api.mockResolvedValueOnce(baseRun("COMPLETED_PENDING_REVIEW") as never).mockResolvedValueOnce({ stage_run_id: 44, employee_count: 2, records_by_kind: { basic: 1 }, skipped_count: 1, acceptance_fingerprint: "b".repeat(64) } as never).mockResolvedValueOnce(accepted as never);
    render(<Stage2EducationPanel cohortRunId={9} />);
    fireEvent.click(screen.getByRole("button", { name: "Проверить образование" }));
    fireEvent.click(await screen.findByRole("button", { name: "Принять этап" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("basic: 1");
    fireEvent.click(within(dialog).getByRole("button", { name: "Принять этап" }));
    await screen.findByText("Принятие завершено. Повторное открытие показывает сохранённый результат без повторной записи.");
    expect(api).toHaveBeenLastCalledWith("/personnel/ppr-migration/stage-2/education/runs/44/accept", { method: "POST", body: { stage_run_id: 44, acceptance_fingerprint: "b".repeat(64) } });
  });
});
