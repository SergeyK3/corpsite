import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import MyOrdersPageClient from "./MyOrdersPageClient";

const list = vi.fn(); const detail = vi.fn();
vi.mock("../_lib/myOrdersApi.client", () => ({ getMyOrders: (...args: unknown[]) => list(...args), getMyOrder: (...args: unknown[]) => detail(...args) }));
vi.mock("@/components/PositionCabinetSectionShell", () => ({ default: ({ title, children }: { title: string; children: React.ReactNode }) => <main><h1>{title}</h1>{children}</main> }));
afterEach(() => { cleanup(); list.mockReset(); detail.mockReset(); });

describe("MyOrdersPageClient", () => {
  it("shows an empty state and sends year/status filters", async () => {
    list.mockResolvedValue({ status: "READY", orders: [] }); render(<MyOrdersPageClient />);
    expect(await screen.findByTestId("my-orders-empty")).toBeInTheDocument();
    fireEvent.change(screen.getAllByRole("combobox")[1], { target: { value: "unconfirmed" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(undefined, "unconfirmed"));
  });
  it("marks a draft document as unconfirmed, including the printable watermark", async () => {
    const order = { order_id: 1, order_number: "125-к", order_date: "2026-07-10", title: "Выход из отпуска по уходу за ребёнком; Совмещение (начало)", item_text: "Только мой пункт", confirmation_status: "UNCONFIRMED" as const };
    list.mockResolvedValue({ status: "READY", orders: [order] }); detail.mockResolvedValue({ ...order, warning: "Приказ ещё не подтверждён кадровой службой. Сведения могут быть уточнены после сверки с оригиналом." });
    render(<MyOrdersPageClient />); fireEvent.click(await screen.findByRole("button", { name: "Открыть" }));
    expect(screen.getAllByText(order.title)).not.toHaveLength(0);
    expect(screen.queryByText("RETURN_FROM_CHILDCARE_LEAVE")).not.toBeInTheDocument();
    expect(screen.queryByText("COMPOSITE")).not.toBeInTheDocument();
    expect(await screen.findByTestId("my-order-unconfirmed-watermark")).toHaveTextContent("НЕ ПОДТВЕРЖДЕНО");
    expect(screen.getByRole("button", { name: "Распечатать предварительную версию" })).toBeInTheDocument();
  });
  it("shows a confirmed document without a watermark", async () => {
    const order = { order_id: 1, order_number: "1-К", order_date: "2026-01-01", title: "О приёме", item_text: "Только мой пункт", confirmation_status: "CONFIRMED" as const };
    list.mockResolvedValue({ status: "READY", orders: [order] }); detail.mockResolvedValue({ ...order, warning: null });
    render(<MyOrdersPageClient />); fireEvent.click(await screen.findByRole("button", { name: "Открыть" }));
    expect(await screen.findByRole("button", { name: "Распечатать" })).toBeInTheDocument();
    expect(screen.queryByTestId("my-order-unconfirmed-watermark")).not.toBeInTheDocument();
  });
  it("uses the neutral electronic-version fallback when an item body is unavailable", async () => {
    const order = { order_id: 1, order_number: "125-к", order_date: "2026-07-10", title: "Приём на работу; Совмещение (начало)", item_text: null, confirmation_status: "CONFIRMED" as const };
    list.mockResolvedValue({ status: "READY", orders: [order] }); detail.mockResolvedValue({ ...order, warning: null });
    render(<MyOrdersPageClient />); fireEvent.click(await screen.findByRole("button", { name: "Открыть" }));
    expect(await screen.findByText("Текст пункта приказа отсутствует в электронной версии")).toBeInTheDocument();
    expect(screen.getAllByText("Подтверждено кадровой службой")).toHaveLength(2);
  });
});
