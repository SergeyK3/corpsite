import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TaskDetailPanel from "./TaskDetailPanel";
import { isTaskRowEditable } from "@/lib/taskEditPolicy";
import { taskActionsLabel } from "@/lib/i18n";
import {
  parseTaskIdFromSearchParams,
  resolveTaskDrawerCloseTarget,
  RETURN_TO_QUERY_PARAM,
  TASK_ID_QUERY_PARAM,
} from "@/lib/taskNav";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("TasksPageClient drawer close navigation", () => {
  it("returns to journal when return_to is present", () => {
    const replace = vi.fn();
    const sp = new URLSearchParams(
      `${TASK_ID_QUERY_PARAM}=9001&${RETURN_TO_QUERY_PARAM}=%2Fregular-task-runs%3Frun_id%3D39`,
    );

    replace(resolveTaskDrawerCloseTarget(sp));

    expect(replace).toHaveBeenCalledWith("/regular-task-runs?run_id=39");
  });

  it("clears task_id and stays on /tasks when return_to is absent", () => {
    const replace = vi.fn();
    const sp = new URLSearchParams(`${TASK_ID_QUERY_PARAM}=9001&org_unit_id=5`);

    replace(resolveTaskDrawerCloseTarget(sp));

    expect(replace).toHaveBeenCalledWith("/tasks?org_unit_id=5");

    const after = new URL(String(replace.mock.calls[0]?.[0]), "http://localhost");
    expect(parseTaskIdFromSearchParams(after.searchParams)).toBeNull();
  });

  it("does not leave deep-link task_id after close without return_to", () => {
    const sp = new URLSearchParams(`${TASK_ID_QUERY_PARAM}=123`);
    const target = resolveTaskDrawerCloseTarget(sp);
    const after = new URL(target, "http://localhost");

    expect(parseTaskIdFromSearchParams(after.searchParams)).toBeNull();
    expect(target).toBe("/tasks");
  });
});

const REGULAR_TASK_DESCRIPTION = `Отчёт по амбулаторной экспертизе
---
Источник: Догоняющий запуск регулярной задачи
ID запуска: 33
Дата возникновения задачи: 2026-06-11
Тип запуска: догоняющий
Период: Прошлая неделя
---`;

const WAITING_APPROVAL_TASK = {
  task_id: 10019,
  task_kind: "regular",
  status_code: "WAITING_APPROVAL",
  status_name_ru: "Ожидает согласование",
  requires_report: true,
  allowed_actions: ["approve", "reject"],
  report_link: "https://example.com/report",
  report_submitted_at: "2026-06-24T03:53:05+05:00",
  description: REGULAR_TASK_DESCRIPTION,
};

function renderDrawerPanel(options: {
  taskScope: "team" | "mine";
  isSystemAdmin?: boolean;
  task?: Record<string, unknown>;
}) {
  const isSystemAdmin = options.isSystemAdmin ?? false;
  const readOnlyTeamMode = options.taskScope === "team" && !isSystemAdmin;
  const task = options.task ?? WAITING_APPROVAL_TASK;
  const selectedEditable = isTaskRowEditable(task, { readOnlyTeamMode, isSystemAdmin });

  render(
    <TaskDetailPanel
      drawerLoading={false}
      drawerError={null}
      uiNotice=""
      showExecutorColumn={options.taskScope === "team"}
      selectedEditable={selectedEditable}
      showDeleteButtons={isSystemAdmin}
      isSystemAdmin={isSystemAdmin}
      saving={false}
      reportLink=""
      reason=""
      onReportLinkChange={vi.fn()}
      onReasonChange={vi.fn()}
      onEdit={vi.fn()}
      onDelete={vi.fn()}
      onRunAction={vi.fn()}
      selectedItem={task}
    />,
  );
}

describe("TasksPageClient review UX regression", () => {
  it("team/all-tasks drawer for non-admin hides scheduler metadata and action duplicates", () => {
    renderDrawerPanel({ taskScope: "team", isSystemAdmin: false });

    expect(screen.getByText("Отчёт по амбулаторной экспертизе")).toBeInTheDocument();
    expect(screen.queryByText(/Догоняющий запуск регулярной задачи/)).not.toBeInTheDocument();
    expect(screen.queryByText("Доступные действия")).not.toBeInTheDocument();
    expect(screen.queryByText(taskActionsLabel(["approve", "reject"]))).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Изменить" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Согласовать" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отклонить" })).toBeInTheDocument();
  });

  it("mine-tasks drawer for non-admin hides scheduler metadata and edit button", () => {
    renderDrawerPanel({ taskScope: "mine", isSystemAdmin: false });

    expect(screen.getByText("Отчёт по амбулаторной экспертизе")).toBeInTheDocument();
    expect(screen.queryByText(/Догоняющий запуск регулярной задачи/)).not.toBeInTheDocument();
    expect(screen.queryByText("Доступные действия")).not.toBeInTheDocument();
    expect(screen.queryByText(taskActionsLabel(["approve", "reject"]))).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Изменить" })).not.toBeInTheDocument();
  });

  it("mine-tasks table row hides edit for WAITING_APPROVAL", () => {
    expect(
      isTaskRowEditable(WAITING_APPROVAL_TASK, { readOnlyTeamMode: false }),
    ).toBe(false);
  });

  it("team/all-tasks table row hides edit for non-admin even when task is editable by kind", () => {
    expect(
      isTaskRowEditable(
        { task_kind: "regular", status_code: "IN_PROGRESS" },
        { readOnlyTeamMode: true },
      ),
    ).toBe(false);
  });

  it("mine-tasks hides edit for regular WAITING_REPORT when non-admin", () => {
    expect(
      isTaskRowEditable(
        { task_kind: "regular", status_code: "WAITING_REPORT" },
        { readOnlyTeamMode: false, isSystemAdmin: false },
      ),
    ).toBe(false);
  });

  it("mine-tasks shows edit for regular WAITING_REPORT when system admin", () => {
    expect(
      isTaskRowEditable(
        { task_kind: "regular", status_code: "WAITING_REPORT" },
        { readOnlyTeamMode: false, isSystemAdmin: true },
      ),
    ).toBe(true);
  });

  it("system admin sees collapsed service metadata block", () => {
    renderDrawerPanel({ taskScope: "team", isSystemAdmin: true });

    expect(screen.getByText("Служебная информация")).toBeInTheDocument();
    expect(screen.getByText(/Догоняющий запуск регулярной задачи/)).toBeInTheDocument();
    expect(screen.queryByText("Доступные действия")).not.toBeInTheDocument();
    expect(screen.queryByText(taskActionsLabel(["approve", "reject"]))).not.toBeInTheDocument();
  });
});
