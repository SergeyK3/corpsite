import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderHeaderEditor from "./PersonnelOrderHeaderEditor";
import type {
  PersonnelOrderDetailResponse,
  PersonnelOrderHeader,
} from "../_lib/personnelOrdersApi.client";

const onSaved = vi.fn();

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return {
    ...actual,
    getPersonnelOrderSignatoryDefault: vi.fn(),
    updatePersonnelOrder: vi.fn(),
  };
});

import {
  getPersonnelOrderSignatoryDefault,
  updatePersonnelOrder,
} from "../_lib/personnelOrdersApi.client";

function sampleOrder(
  overrides?: Partial<PersonnelOrderHeader>,
): PersonnelOrderHeader {
  return {
    order_id: 42,
    order_type_code: "HIRE",
    order_class: "SIMPLE",
    status: "DRAFT",
    source_mode: "PAPER",
    created_by: 1,
    ...overrides,
  };
}

function savedDetail(
  order: PersonnelOrderHeader,
): PersonnelOrderDetailResponse {
  return {
    order,
    items: [],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelOrderHeaderEditor signatory requisites", () => {
  it("prefills resolved values as controlled input state and auto-patches once", async () => {
    vi.mocked(getPersonnelOrderSignatoryDefault).mockResolvedValue({
      signed_by_employee_id: 7,
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
      warning: null,
      source: "platform_role",
    });
    vi.mocked(updatePersonnelOrder).mockResolvedValue(
      savedDetail(
        sampleOrder({
          signed_by_name: "М. Тулеутаев",
          signed_by_position: "Директор",
          signed_by_employee_id: 7,
        }),
      ),
    );

    render(<PersonnelOrderHeaderEditor order={sampleOrder()} onSaved={onSaved} />);

    await waitFor(() => {
      expect(
        (screen.getByTestId("personnel-order-header-signatory-position") as HTMLInputElement).value,
      ).toBe("Директор");
    });

    await waitFor(() => {
      expect(updatePersonnelOrder).toHaveBeenCalledTimes(1);
    });
  });

  it("does not auto-patch for non-draft statuses", async () => {
    vi.mocked(getPersonnelOrderSignatoryDefault).mockResolvedValue({
      signed_by_employee_id: 7,
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
      warning: null,
      source: "platform_role",
    });

    render(
      <PersonnelOrderHeaderEditor
        order={sampleOrder({ status: "SIGNED" })}
        disabled
        onSaved={onSaved}
      />,
    );

    await waitFor(() => {
      expect(getPersonnelOrderSignatoryDefault).not.toHaveBeenCalled();
    });
    expect(updatePersonnelOrder).not.toHaveBeenCalled();
  });

  it("manual input wins against late resolver response", async () => {
    let resolveDefault!: (value: Awaited<ReturnType<typeof getPersonnelOrderSignatoryDefault>>) => void;
    vi.mocked(getPersonnelOrderSignatoryDefault).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDefault = resolve;
        }),
    );

    render(<PersonnelOrderHeaderEditor order={sampleOrder()} onSaved={onSaved} />);

    fireEvent.change(screen.getByTestId("personnel-order-header-signatory-name"), {
      target: { value: "К. Замещающий" },
    });
    fireEvent.change(screen.getByTestId("personnel-order-header-signatory-position"), {
      target: { value: "И. о. директора" },
    });

    resolveDefault({
      signed_by_employee_id: 7,
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
      warning: null,
      source: "platform_role",
    });

    await waitFor(() => {
      expect(
        (screen.getByTestId("personnel-order-header-signatory-name") as HTMLInputElement).value,
      ).toBe("К. Замещающий");
    });
    expect(updatePersonnelOrder).not.toHaveBeenCalled();
  });

  it("shows soft notice when auto-patch fails but keeps manual path", async () => {
    vi.mocked(getPersonnelOrderSignatoryDefault).mockResolvedValue({
      signed_by_employee_id: 7,
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
      warning: null,
      source: "platform_role",
    });
    vi.mocked(updatePersonnelOrder).mockRejectedValue(new Error("network"));

    render(<PersonnelOrderHeaderEditor order={sampleOrder()} onSaved={onSaved} />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-header-signatory-autopersist-notice")).toBeInTheDocument();
    });

    expect(
      (screen.getByTestId("personnel-order-header-signatory-name") as HTMLInputElement).value,
    ).toBe("М. Тулеутаев");
  });

  it("does not overwrite saved signatory on reopen", async () => {
    render(
      <PersonnelOrderHeaderEditor
        order={sampleOrder({
          signed_by_name: "К. Замещающий",
          signed_by_position: "И. о. директора",
        })}
        onSaved={onSaved}
      />,
    );

    expect(getPersonnelOrderSignatoryDefault).not.toHaveBeenCalled();
    expect(
      (screen.getByTestId("personnel-order-header-signatory-name") as HTMLInputElement).value,
    ).toBe("К. Замещающий");
  });

  it("resets prefill guard when orderId changes", async () => {
    vi.mocked(getPersonnelOrderSignatoryDefault).mockResolvedValue({
      signed_by_employee_id: null,
      signed_by_name: null,
      signed_by_position: null,
      warning: "Действующий директор не найден. Заполните должность и ФИО подписанта вручную.",
      source: "hr_director_assignment",
    });

    const { rerender } = render(
      <PersonnelOrderHeaderEditor order={sampleOrder({ order_id: 1 })} onSaved={onSaved} />,
    );

    await waitFor(() => {
      expect(getPersonnelOrderSignatoryDefault).toHaveBeenCalledTimes(1);
    });

    rerender(
      <PersonnelOrderHeaderEditor order={sampleOrder({ order_id: 2 })} onSaved={onSaved} />,
    );

    await waitFor(() => {
      expect(getPersonnelOrderSignatoryDefault).toHaveBeenCalledTimes(2);
    });
  });

  it("rejects partial signatory on save", async () => {
    vi.mocked(getPersonnelOrderSignatoryDefault).mockResolvedValue({
      signed_by_employee_id: null,
      signed_by_name: null,
      signed_by_position: null,
      warning: "Действующий директор не найден. Заполните должность и ФИО подписанта вручную.",
      source: "hr_director_assignment",
    });

    render(<PersonnelOrderHeaderEditor order={sampleOrder()} onSaved={onSaved} />);

    await waitFor(() => {
      expect(getPersonnelOrderSignatoryDefault).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByTestId("personnel-order-header-signatory-position"), {
      target: { value: "Директор" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить заголовок" }));

    expect(await screen.findByText("Укажите и должность, и ФИО подписанта.")).toBeInTheDocument();
    expect(updatePersonnelOrder).not.toHaveBeenCalled();
  });
});
