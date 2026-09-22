import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AccessManagementClient from "./AccessManagementClient";

const apiFetchJson = vi.fn();
vi.mock("@/lib/api", () => ({ apiFetchJson: (...args: unknown[]) => apiFetchJson(...args) }));

describe("AccessManagementClient", () => {
  it("searches users and confirms reset before showing a one-time password", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    apiFetchJson.mockResolvedValueOnce({ items: [{ user_id: 7, login: "staff.login", is_active: true, role: "DIRECTOR", lock_active: false, lock_reason: null, locked_until: null, employee_id: null, has_linked_employee: false }] });
    apiFetchJson.mockResolvedValueOnce({ temporary_password: "one-time-test-password", must_change_password: true, token_version: 2 });
    render(<AccessManagementClient />);
    fireEvent.change(screen.getByLabelText("Поиск учётной записи"), { target: { value: "staff" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(await screen.findByText("staff.login")).toBeInTheDocument();
    expect(screen.getByText("Не связан с сотрудником")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Выдать временный пароль" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenLastCalledWith("/directory/access/users/7/password-reset", { method: "POST" }));
    expect(screen.getByTestId("access-reset-password")).toHaveTextContent("one-time-test-password");
    expect(screen.getByText(/Передайте пароль сотруднику безопасным каналом/)).toBeInTheDocument();
  });
});
