import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CurrentUserProvider } from "@/lib/currentUser";
import type { MeInfo } from "@/lib/types";
import type { EmployeeDetails } from "../../employees/_lib/types";
import { getPositions } from "../../employees/_lib/api.client";
import { changeEmployeeAssignment } from "../_lib/manualAssignmentChangeApi.client";
import EmployeeAssignmentChangeForm from "./EmployeeAssignmentChangeForm";

vi.mock("../../employees/_lib/api.client", () => ({
  getPositions: vi.fn(),
}));

vi.mock("../_lib/manualAssignmentChangeApi.client", () => ({
  changeEmployeeAssignment: vi.fn(),
}));

const details: EmployeeDetails = {
  id: "16",
  person_id: 105,
  active_assignment_id: 107,
  fio: "Өсерова Айсара Асанқызы",
  department: { id: 73, name: "Отдел кадров" },
  org_unit: {
    unit_id: 73,
    name: "Отдел кадров",
    code: "HR",
    parent_unit_id: null,
    is_active: true,
  },
  position: { id: 86, name: "Старая должность" },
  rate: 1,
  status: "active",
  date_from: "2025-01-01",
  date_to: null,
};

function renderForm({
  permission = true,
  onChanged = vi.fn(),
}: {
  permission?: boolean;
  onChanged?: () => void | Promise<void>;
} = {}) {
  const me: MeInfo = { user_id: 8, has_hr_enrollment_manager: permission };
  render(
    <CurrentUserProvider value={me}>
      <EmployeeAssignmentChangeForm employeeId="16" details={details} onChanged={onChanged} />
    </CurrentUserProvider>,
  );
  return { onChanged };
}

async function openAndFill() {
  fireEvent.click(screen.getByTestId("assignment-change-open"));
  await waitFor(() => expect(screen.getByTestId("assignment-change-position")).not.toBeDisabled());
  fireEvent.change(screen.getByTestId("assignment-change-position"), { target: { value: "29" } });
  fireEvent.change(screen.getByTestId("assignment-change-start-date"), {
    target: { value: "2026-07-01" },
  });
}

beforeEach(() => {
  vi.mocked(getPositions).mockResolvedValue({
    items: [
      { position_id: 29, name: "Менеджер" },
      { position_id: 340, name: "Менеджер УЧР", is_active: false },
    ],
  });
  vi.mocked(changeEmployeeAssignment).mockResolvedValue({
    result: {
      employee_id: 16,
      person_id: 105,
      predecessor_assignment_id: 107,
      successor_assignment_id: 108,
      event_id: 501,
      audit_id: 601,
      already_applied: false,
    },
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("EmployeeAssignmentChangeForm", () => {
  it("shows the button only with exact permission", () => {
    renderForm({ permission: true });
    expect(screen.getByTestId("assignment-change-open")).toBeInTheDocument();
    cleanup();
    renderForm({ permission: false });
    expect(screen.queryByTestId("assignment-change-open")).not.toBeInTheDocument();
  });

  it("shows the current active assignment in the form", async () => {
    renderForm();
    fireEvent.click(screen.getByTestId("assignment-change-open"));
    expect(await screen.findByTestId("assignment-change-current-assignment")).toHaveTextContent("#107");
  });

  it("requests and displays only positions allowed for the current org unit", async () => {
    vi.mocked(getPositions).mockResolvedValue({
      items: [{ position_id: 29, name: "Менеджер" }],
    });
    renderForm();

    fireEvent.click(screen.getByTestId("assignment-change-open"));

    await waitFor(() =>
      expect(getPositions).toHaveBeenCalledWith({
        limit: 1000,
        offset: 0,
        org_unit_id: 73,
        scope: "allowed",
      }),
    );
    expect(await screen.findByRole("option", { name: "Менеджер" })).toHaveValue("29");
    expect(screen.queryByRole("option", { name: "Должность другого подразделения" })).not.toBeInTheDocument();
  });

  it("shows a clear message when the org unit has no allowed positions", async () => {
    vi.mocked(getPositions).mockResolvedValue({ items: [] });
    renderForm();

    fireEvent.click(screen.getByTestId("assignment-change-open"));

    expect(
      await screen.findByText("Для текущего подразделения нет доступных действующих должностей."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("assignment-change-submit")).toBeDisabled();
  });

  it("keeps saving disabled when loading positions fails", async () => {
    vi.mocked(getPositions).mockRejectedValue(new Error("Справочник должностей недоступен"));
    renderForm();

    fireEvent.click(screen.getByTestId("assignment-change-open"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Справочник должностей недоступен");
    expect(screen.getByTestId("assignment-change-submit")).toBeDisabled();
  });

  it("confirms before posting the complete command", async () => {
    renderForm();
    await openAndFill();
    fireEvent.change(screen.getByTestId("assignment-change-comment"), {
      target: { value: "Ручная смена" },
    });
    fireEvent.click(screen.getByTestId("assignment-change-submit"));

    await waitFor(() => expect(changeEmployeeAssignment).toHaveBeenCalledTimes(1));
    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringContaining("Прежняя должность: Старая должность"),
    );
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Новая должность: Менеджер"));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Дата начала: 2026-07-01"));
    expect(changeEmployeeAssignment).toHaveBeenCalledWith(
      "16",
      expect.objectContaining({
        expected_assignment_id: 107,
        org_unit_id: 73,
        position_id: 29,
        start_date: "2026-07-01",
        idempotency_key: expect.any(String),
        comment: "Ручная смена",
      }),
    );
    expect(vi.mocked(window.confirm).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(changeEmployeeAssignment).mock.invocationCallOrder[0],
    );
  });

  it("closes and rereads the card after success", async () => {
    const onChanged = vi.fn().mockResolvedValue(undefined);
    renderForm({ onChanged });
    await openAndFill();
    fireEvent.click(screen.getByTestId("assignment-change-submit"));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("assignment-change-form")).not.toBeInTheDocument();
  });

  it("shows a controlled stale error without success", async () => {
    vi.mocked(changeEmployeeAssignment).mockRejectedValue({
      status: 409,
      details: { detail: { code: "ACTIVE_ASSIGNMENT_STALE" } },
    });
    const onChanged = vi.fn();
    renderForm({ onChanged });
    await openAndFill();
    fireEvent.click(screen.getByTestId("assignment-change-submit"));

    expect(await screen.findByRole("alert")).toHaveTextContent("уже изменилось");
    expect(onChanged).not.toHaveBeenCalled();
    expect(screen.getByTestId("assignment-change-form")).toBeInTheDocument();
  });

  it("prevents a double submit while the request is pending", async () => {
    let resolveRequest!: (value: Awaited<ReturnType<typeof changeEmployeeAssignment>>) => void;
    vi.mocked(changeEmployeeAssignment).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    renderForm();
    await openAndFill();
    const submit = screen.getByTestId("assignment-change-submit");
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(changeEmployeeAssignment).toHaveBeenCalledTimes(1);
    resolveRequest({
      result: {
        employee_id: 16,
        person_id: 105,
        predecessor_assignment_id: 107,
        successor_assignment_id: 108,
        event_id: 501,
        audit_id: 601,
        already_applied: false,
      },
    });
    await waitFor(() => expect(screen.queryByTestId("assignment-change-form")).not.toBeInTheDocument());
  });
});
