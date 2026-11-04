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
  it.each(['PERSONAL_DATA_CHANGE','EDUCATION_INFORMATION_CHANGE','HIRE','COMPOSITE'])('hides header basis/comment and never sends hidden values when saving the available type (%s)',async type=>{
    const order=sampleOrder({order_type_code:type,basis_summary:'TEST основание заголовка',comment:'TEST сохранённый комментарий',signed_by_name:'TEST',signed_by_position:'DIRECTOR'});
    vi.mocked(updatePersonnelOrder).mockResolvedValue(savedDetail({...order,order_type_code:'TRANSFER'}));
    render(<PersonnelOrderHeaderEditor order={order} onSaved={onSaved}/>);
    expect(screen.queryByText('Основание',{exact:true})).not.toBeInTheDocument();
    expect(screen.queryByText('Комментарий',{exact:true})).not.toBeInTheDocument();
    fireEvent.change(screen.getByTestId('personnel-order-type-select'),{target:{value:'TRANSFER'}});
    fireEvent.click(screen.getByRole('button',{name:'Сохранить заголовок',exact:true}));
    await waitFor(()=>expect(updatePersonnelOrder).toHaveBeenCalledExactlyOnceWith(order.order_id,{order_type_code:'TRANSFER'}));
    expect(order.basis_summary).toBe('TEST основание заголовка');
    expect(order.comment).toBe('TEST сохранённый комментарий');
  });
  it("detects number-only changes, saves only that number, and resets after reading the saved header", async () => {
    const order = sampleOrder({order_number:"118 тест",order_date:"2026-10-30",signed_by_name:"Тестовый подписант",signed_by_position:"DIRECTOR"});
    const saved = savedDetail({...order,order_number:"116 тест"});
    vi.mocked(updatePersonnelOrder).mockResolvedValue(saved);
    const {rerender}=render(<PersonnelOrderHeaderEditor order={order} onSaved={onSaved}/>);
    const input=screen.getByLabelText("№ приказа (из журнала)");
    const button=screen.getByTestId("personnel-order-header-save-signatory");
    fireEvent.change(input,{target:{value:"1118 тест"}});
    expect(input).toHaveValue("1118 тест");
    expect(button).toBeEnabled();
    fireEvent.change(input,{target:{value:"118 тест"}});
    expect(button).toBeDisabled();
    fireEvent.change(input,{target:{value:"116 тест"}});
    fireEvent.click(button);
    await waitFor(()=>expect(onSaved).toHaveBeenCalledWith(saved));
    expect(updatePersonnelOrder).toHaveBeenCalledExactlyOnceWith(order.order_id,{order_number:"116 тест"});
    rerender(<PersonnelOrderHeaderEditor order={saved.order} onSaved={onSaved}/>);
    expect(input).toHaveValue("116 тест");
    expect(button).toBeDisabled();
  });

  it("saves date-only and combined requisites through the same action", async () => {
    const order=sampleOrder({order_number:"118 тест",order_date:"2026-10-30",signed_by_name:"Тестовый подписант",signed_by_position:"DIRECTOR"});
    vi.mocked(updatePersonnelOrder).mockResolvedValue(savedDetail(order));
    render(<PersonnelOrderHeaderEditor order={order} onSaved={onSaved}/>);
    fireEvent.change(screen.getByTestId("personnel-order-header-order-date"),{target:{value:"2026-10-29"}});
    fireEvent.click(screen.getByTestId("personnel-order-header-save-signatory"));
    await waitFor(()=>expect(updatePersonnelOrder).toHaveBeenCalledWith(order.order_id,{order_date:"2026-10-29"}));
    await waitFor(()=>expect(screen.getByTestId("personnel-order-header-save-signatory")).toBeEnabled());
    fireEvent.change(screen.getByLabelText("№ приказа (из журнала)"),{target:{value:"116 тест"}});
    fireEvent.change(screen.getByTestId("personnel-order-header-signatory-position"),{target:{value:"ACTING_DIRECTOR"}});
    fireEvent.click(screen.getByTestId("personnel-order-header-save-signatory"));
    await waitFor(()=>expect(updatePersonnelOrder).toHaveBeenLastCalledWith(order.order_id,{order_number:"116 тест",order_date:"2026-10-29",signed_by_position:"ACTING_DIRECTOR",signed_by_name:"Тестовый подписант"}));
  });

  it("preserves an unsaved number after an API error and permits retry", async () => {
    const order=sampleOrder({order_number:"118 тест",signed_by_name:"Тестовый подписант",signed_by_position:"DIRECTOR"});
    vi.mocked(updatePersonnelOrder).mockRejectedValue(new Error("number save failed"));
    render(<PersonnelOrderHeaderEditor order={order} onSaved={onSaved}/>);
    fireEvent.change(screen.getByLabelText("№ приказа (из журнала)"),{target:{value:"116 тест"}});
    fireEvent.click(screen.getByTestId("personnel-order-header-save-signatory"));
    expect(await screen.findByText("number save failed")).toBeInTheDocument();
    expect(screen.getByLabelText("№ приказа (из журнала)")).toHaveValue("116 тест");
    expect(screen.getByTestId("personnel-order-header-save-signatory")).toBeEnabled();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("does not submit requisites when editing is disabled", () => {
    render(<PersonnelOrderHeaderEditor order={sampleOrder({order_number:"118 тест",status:"SIGNED",signed_by_name:"Тестовый подписант",signed_by_position:"DIRECTOR"})} disabled onSaved={onSaved}/>);
    expect(screen.getByLabelText("№ приказа (из журнала)")).toBeDisabled();
    expect(screen.getByTestId("personnel-order-header-save-signatory")).toBeDisabled();
    fireEvent.click(screen.getByTestId("personnel-order-header-save-signatory"));
    expect(updatePersonnelOrder).not.toHaveBeenCalled();
  });

  it("keeps signatory edits local and enables the explicit save only when changed", () => {
    const order = sampleOrder({ signed_by_name: "М. Тулеутаев", signed_by_position: "DIRECTOR" });
    render(<PersonnelOrderHeaderEditor order={order} onSaved={onSaved} />);
    const save = screen.getByTestId("personnel-order-header-save-signatory");
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByTestId("personnel-order-header-signatory-position"), {
      target: { value: "ACTING_DIRECTOR" },
    });
    expect(save).toBeEnabled();
    expect(updatePersonnelOrder).not.toHaveBeenCalled();
  });

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
      ).toBe("DIRECTOR");
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

  it("stores a language-independent acting-director role while preserving the FIO", async () => {
    const order = sampleOrder({ signed_by_name: "М. Тулеутаев", signed_by_position: "Директор" });
    vi.mocked(updatePersonnelOrder).mockResolvedValue(savedDetail({ ...order, signed_by_position: "ACTING_DIRECTOR" }));
    render(<PersonnelOrderHeaderEditor order={order} onSaved={onSaved} />);

    fireEvent.change(screen.getByTestId("personnel-order-header-signatory-position"), {
      target: { value: "ACTING_DIRECTOR" },
    });
    fireEvent.click(screen.getByTestId("personnel-order-header-save-signatory"));

    await waitFor(() => {
      expect(updatePersonnelOrder).toHaveBeenCalledWith(order.order_id, expect.objectContaining({
        signed_by_position: "ACTING_DIRECTOR",
        signed_by_name: "М. Тулеутаев",
      }));
    });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({
      order: expect.objectContaining({ signed_by_position: "ACTING_DIRECTOR" }),
    }));
  });

  it("keeps the local draft after a requisites save error", async () => {
    const order = sampleOrder({ signed_by_name: "М. Тулеутаев", signed_by_position: "DIRECTOR" });
    vi.mocked(updatePersonnelOrder).mockRejectedValue(new Error("network"));
    render(<PersonnelOrderHeaderEditor order={order} onSaved={onSaved} />);
    fireEvent.change(screen.getByTestId("personnel-order-header-signatory-name"), {
      target: { value: "Л. Козгамбаева" },
    });
    fireEvent.click(screen.getByTestId("personnel-order-header-save-signatory"));
    expect(await screen.findByText("network")).toBeInTheDocument();
    expect((screen.getByTestId("personnel-order-header-signatory-name") as HTMLInputElement).value)
      .toBe("Л. Козгамбаева");
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
      target: { value: "ACTING_DIRECTOR" },
    });
    fireEvent.click(screen.getByTestId("personnel-order-header-save-signatory"));

    expect(await screen.findByText("Укажите ФИО подписанта.")).toBeInTheDocument();
    expect(updatePersonnelOrder).not.toHaveBeenCalled();
  });
});
