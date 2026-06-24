import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TaskDetailPanel from "./TaskDetailPanel";
import {
  REPORT_LINK_EMPTY_LABEL,
  REPORT_LINK_NETWORK_HINT,
} from "@/lib/taskReportLink";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const baseProps = {
  drawerLoading: false,
  drawerError: null,
  uiNotice: "",
  showExecutorColumn: false,
  selectedEditable: false,
  showDeleteButtons: false,
  isSystemAdmin: false,
  saving: false,
  reportLink: "",
  reason: "",
  onReportLinkChange: vi.fn(),
  onReasonChange: vi.fn(),
  onEdit: vi.fn(),
  onDelete: vi.fn(),
  onRunAction: vi.fn(),
};

function renderPanel(selectedItem: Record<string, unknown>) {
  render(<TaskDetailPanel {...baseProps} selectedItem={selectedItem} />);
}

describe("TaskDetailPanel report link", () => {
  it("report_link=null shows fallback and hides copy button", () => {
    renderPanel({
      task_id: 10019,
      requires_report: true,
      report_link: null,
      report_submitted_at: "2026-06-24T03:53:05+05:00",
    });

    expect(screen.getByText("Отчёт")).toBeInTheDocument();
    expect(screen.getByText(REPORT_LINK_EMPTY_LABEL)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Скопировать путь" })).toBeNull();
  });

  it("report_link=https shows clickable link and copies URL", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    const link = "https://example.com/report";
    renderPanel({
      task_id: 10019,
      requires_report: true,
      report_link: link,
      report_submitted_at: "2026-06-24T03:53:05+05:00",
    });

    const anchor = screen.getByRole("link", { name: link });
    expect(anchor).toHaveAttribute("href", link);

    fireEvent.click(screen.getByRole("button", { name: "Скопировать путь" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(link);
    });
  });

  it("report_link UNC shows path text, network hint, and copies UNC path", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    const link = "\\\\192.168.103.88\\obmen\\Отчеты\\report";
    renderPanel({
      task_id: 10019,
      requires_report: true,
      report_link: link,
      report_submitted_at: "2026-06-24T03:53:05+05:00",
    });

    expect(screen.getByText(link)).toBeInTheDocument();
    expect(screen.getByText(REPORT_LINK_NETWORK_HINT)).toBeInTheDocument();
    expect(screen.queryByText("Ссылка не является http(s).")).toBeNull();
    expect(screen.queryByText(REPORT_LINK_EMPTY_LABEL)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Скопировать путь" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(link);
    });
  });
});

describe("TaskDetailPanel review UX cleanup", () => {
  it("hides duplicate available-actions card and footer action text", () => {
    render(
      <TaskDetailPanel
        {...baseProps}
        selectedItem={{
          task_id: 10019,
          status_code: "WAITING_APPROVAL",
          requires_report: true,
          allowed_actions: ["approve", "reject"],
          report_link: "https://example.com/report",
          report_submitted_at: "2026-06-24T03:53:05+05:00",
        }}
      />,
    );

    expect(screen.queryByText("Доступные действия")).not.toBeInTheDocument();
    expect(screen.queryByText("Согласовать / Отклонить")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Согласовать" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отклонить" })).toBeInTheDocument();
  });

  it("hides edit button when selectedEditable is false", () => {
    render(
      <TaskDetailPanel
        {...baseProps}
        selectedEditable={false}
        selectedItem={{
          task_id: 10019,
          status_code: "WAITING_APPROVAL",
          allowed_actions: ["approve", "reject"],
        }}
      />,
    );

    expect(screen.queryByRole("button", { name: "Изменить" })).not.toBeInTheDocument();
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

describe("TaskDetailPanel scheduler metadata visibility", () => {
  it("hides origin metadata for non-admin users", () => {
    render(
      <TaskDetailPanel
        {...baseProps}
        isSystemAdmin={false}
        selectedItem={{
          task_id: 10019,
          task_kind: "regular",
          description: REGULAR_TASK_DESCRIPTION,
        }}
      />,
    );

    expect(screen.getByText("Отчёт по амбулаторной экспертизе")).toBeInTheDocument();
    expect(screen.queryByText(/Догоняющий запуск регулярной задачи/)).not.toBeInTheDocument();
    expect(screen.queryByText("ID запуска:")).not.toBeInTheDocument();
    expect(screen.queryByText("Тип запуска:")).not.toBeInTheDocument();
    expect(screen.queryByText("Служебная информация")).not.toBeInTheDocument();
  });

  it("shows origin metadata in admin-only service section", () => {
    render(
      <TaskDetailPanel
        {...baseProps}
        isSystemAdmin={true}
        selectedItem={{
          task_id: 10019,
          task_kind: "regular",
          description: REGULAR_TASK_DESCRIPTION,
        }}
      />,
    );

    expect(screen.getByText("Отчёт по амбулаторной экспертизе")).toBeInTheDocument();
    expect(screen.getByText("Служебная информация")).toBeInTheDocument();
    expect(screen.getByText(/Догоняющий запуск регулярной задачи/)).toBeInTheDocument();
    expect(screen.getByText("33")).toBeInTheDocument();
    expect(screen.getByText("догоняющий")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Журнал запусков" })).toHaveAttribute(
      "href",
      "/regular-task-runs?run_id=33",
    );
  });
});
