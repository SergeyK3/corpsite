import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/testSystemIdentityDeletion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/testSystemIdentityDeletion")>();
  return {
    ...actual,
    probeSystemIdentityDeletionAccess: vi.fn(),
    searchSystemIdentities: vi.fn(),
    previewSystemIdentities: vi.fn(),
  };
});

import {
  previewSystemIdentities,
  probeSystemIdentityDeletionAccess,
  searchSystemIdentities,
} from "@/lib/testSystemIdentityDeletion";
import TestSystemIdentityDeletionPanel from "./TestSystemIdentityDeletionPanel";

const user = { object_type: "USER" as const, object_id: 104, label: "Тестовый сервис", secondary_label: "test.service" };
const role = { object_type: "ROLE" as const, object_id: 27, label: "Тестовая роль", secondary_label: "TEST_ROLE" };

beforeEach(() => {
  vi.mocked(probeSystemIdentityDeletionAccess).mockReset().mockResolvedValue({} as never);
  vi.mocked(searchSystemIdentities).mockReset().mockResolvedValue({ items: [], count: 0 } as never);
  vi.mocked(previewSystemIdentities).mockReset();
});

afterEach(cleanup);

describe("TestSystemIdentityDeletionPanel", () => {
  it("is hidden for HR_HEAD and never probes the protected workflow", () => {
    render(<TestSystemIdentityDeletionPanel me={{ user_id: 2, role_code: "HR_HEAD", can_request_test_personnel_deletion: true, can_request_test_system_identity_deletion: true }} />);
    expect(screen.queryByText("Системные пользователи и роли")).not.toBeInTheDocument();
    expect(probeSystemIdentityDeletionAccess).not.toHaveBeenCalled();
  });

  it("fails closed when the exact backend permission probe returns 403", async () => {
    vi.mocked(probeSystemIdentityDeletionAccess).mockRejectedValue({ status: 403 });
    render(<TestSystemIdentityDeletionPanel me={{ user_id: 1, role_code: "ADMIN", can_request_test_personnel_deletion: true }} />);
    await waitFor(() => expect(probeSystemIdentityDeletionAccess).toHaveBeenCalled());
    expect(screen.queryByText("Системные пользователи и роли")).not.toBeInTheDocument();
  });

  it("switches type and searches by safe mask or exact ID", async () => {
    render(<TestSystemIdentityDeletionPanel me={{ user_id: 1, role_code: "ADMIN", can_request_test_system_identity_deletion: true }} />);
    expect(screen.getByText("Введите от 3 до 100 символов. Поддерживаются маски * и ?")).toBeInTheDocument();
    expect(screen.getByLabelText("Маска */? или точный технический ID")).toHaveAttribute("placeholder", "Например: test* или 104");
    expect(screen.queryByPlaceholderText(/test\.\*/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Маска */? или точный технический ID"), { target: { value: "test*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    await waitFor(() => expect(searchSystemIdentities).toHaveBeenLastCalledWith({ objectType: "USER", field: "full_name", selector: "test*" }));

    fireEvent.click(screen.getByRole("button", { name: "Роли" }));
    fireEvent.change(screen.getByLabelText("Поле поиска"), { target: { value: "code" } });
    fireEvent.change(screen.getByLabelText("Маска */? или точный технический ID"), { target: { value: "27" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    await waitFor(() => expect(searchSystemIdentities).toHaveBeenLastCalledWith({ objectType: "ROLE", field: "code", selector: "27" }));
  });

  it("shows the backend mask length validation in Russian", async () => {
    vi.mocked(searchSystemIdentities).mockRejectedValue({
      details: { detail: { message: "Mask length must be between 3 and 100." } },
    });
    render(<TestSystemIdentityDeletionPanel me={{ user_id: 1, role_code: "ADMIN", can_request_test_system_identity_deletion: true }} />);
    fireEvent.change(screen.getByLabelText("Маска */? или точный технический ID"), { target: { value: "ab" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Маска должна содержать от 3 до 100 символов");
    expect(screen.queryByText("Mask length must be between 3 and 100.")).not.toBeInTheDocument();
  });

  it("selects exact results and renders provenance, relations, blockers, text and icons", async () => {
    vi.mocked(searchSystemIdentities).mockResolvedValue({ items: [user, role], count: 2 } as never);
    vi.mocked(previewSystemIdentities).mockResolvedValue({
      items: [
        { ...user, has_test_provenance: true, ready_for_deletion: true, blocking_codes: [], relationships: [], relationship_fingerprint: "a".repeat(64) },
        { ...role, has_test_provenance: true, ready_for_deletion: false, blocking_codes: ["ACTIVE_ROLE_PROTECTED"], relationship_fingerprint: "b".repeat(64), relationships: [{ relation_code: "LOGICAL:report_catalog.owner_role_code", table: "report_catalog", columns: ["owner_role_code"], classification: "BLOCKING", count: 3, state_digest: "c".repeat(64), on_delete: null }] },
      ],
      count: 2, ready_count: 1, typed_ids: [user, role], target_list_hash: "d".repeat(64), relationship_fingerprint: "e".repeat(64), fingerprint_version: "v1", policy_version: "v2",
    } as never);
    render(<TestSystemIdentityDeletionPanel me={{ user_id: 1, role_code: "ADMIN", can_request_test_system_identity_deletion: true }} />);
    fireEvent.change(screen.getByLabelText("Маска */? или точный технический ID"), { target: { value: "test*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    fireEvent.click(await screen.findByLabelText("Выбрать Тестовый сервис, USER #104"));
    fireEvent.click(screen.getByLabelText("Выбрать Тестовая роль, ROLE #27"));
    fireEvent.click(screen.getByRole("button", { name: "Предварительная проверка" }));

    await waitFor(() => expect(previewSystemIdentities).toHaveBeenCalledWith([
      { object_type: "USER", object_id: 104 }, { object_type: "ROLE", object_id: 27 },
    ]));
    expect(screen.getByText("Можно включить в запрос")).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument();
    expect(screen.getByText("Удаление заблокировано")).toBeInTheDocument();
    expect(screen.getByText("⛔")).toBeInTheDocument();
    expect(screen.getAllByText(/Provenance:/)).toHaveLength(2);
    expect(screen.getByText("Активная роль защищена")).toBeInTheDocument();
    expect(screen.getByText(/report_catalog\.owner_role_code — строк: 3/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Создать запрос/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Удалить/ })).not.toBeInTheDocument();
  });
});
