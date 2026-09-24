import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MyOrdersPageClient from "./MyOrdersPageClient";

const list = vi.fn();
const detail = vi.fn();
const replace = vi.fn();
let search = "";

vi.mock("../_lib/myOrdersApi.client", () => ({
  getMyOrders: (...args: unknown[]) => list(...args),
  getMyOrder: (...args: unknown[]) => detail(...args),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/profile/orders",
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("@/components/PositionCabinetSectionShell", () => ({
  default: ({ title, children }: { title: string; children: React.ReactNode }) => <main><h1>{title}</h1>{children}</main>,
}));

const kkOrder = {
  order_id: 1, order_number: "125-к", order_date: "2026-07-10",
  title: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
  item_text: "Қазақша жеке тармақ", confirmation_status: "UNCONFIRMED" as const,
};
const ruOrder = {
  ...kkOrder,
  title: "О выходе на работу из отпуска по уходу за ребёнком",
  item_text: "Русский личный пункт",
};

beforeEach(() => { search = ""; window.print = vi.fn(); });
afterEach(() => { cleanup(); list.mockReset(); detail.mockReset(); replace.mockReset(); });

describe("MyOrdersPageClient", () => {
  it("fully localizes the list, detail, and preliminary print chrome in Kazakh", async () => {
    list.mockResolvedValue({ status: "READY", orders: [kkOrder] });
    detail.mockResolvedValue({ ...kkOrder, preamble: null, basis: null, warning: null });
    render(<MyOrdersPageClient />);

    expect(await screen.findByRole("heading", { name: "Менің бұйрықтарым" })).toBeInTheDocument();
    expect(screen.getByText("Сіз қызметкер ретінде көрсетілген кадрлық бұйрықтар")).toBeInTheDocument();
    expect(screen.getByText("Жыл")).toBeInTheDocument();
    expect(screen.getByText("Мәртебе")).toBeInTheDocument();
    expect(screen.getAllByText("Барлығы")).toHaveLength(2);
    expect(screen.getByText("Кадр қызметімен расталмаған")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ашу" }));
    expect(await screen.findByText("Бұйрық кадр қызметімен әлі расталмаған. Мәліметтер түпнұсқамен салыстырып тексерілгеннен кейін нақтылануы мүмкін.")).toBeInTheDocument();
    expect(screen.getByTestId("my-order-unconfirmed-watermark")).toHaveTextContent("РАСТАЛМАҒАН");
    expect(screen.getByRole("button", { name: "Жабу" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Алдын ала нұсқаны басып шығару" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Алдын ала нұсқаны басып шығару" }));
    expect(window.print).toHaveBeenCalledOnce();

    for (const russianServiceText of [
      "Мои приказы", "Год", "Статус", "Все", "Открыть", "Закрыть",
      "Распечатать предварительную версию", "Не подтверждено кадровой службой",
      "Подтверждено кадровой службой", "НЕ ПОДТВЕРЖДЕНО",
      "Приказ ещё не подтверждён кадровой службой. Сведения могут быть уточнены после сверки с оригиналом.",
    ]) {
      expect(screen.queryByText(russianServiceText, { exact: true })).not.toBeInTheDocument();
    }
  });

  it("defaults to Kazakh, normalizes the URL, and keeps year/status filters", async () => {
    list.mockResolvedValue({ status: "READY", orders: [] });
    render(<MyOrdersPageClient />);
    expect(await screen.findByTestId("my-orders-empty")).toBeInTheDocument();
    expect(list).toHaveBeenLastCalledWith(undefined, "all", "kk");
    expect(replace).toHaveBeenCalledWith("/profile/orders?lang=kk", { scroll: false });
    fireEvent.change(screen.getAllByRole("combobox")[1], { target: { value: "unconfirmed" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(undefined, "unconfirmed", "kk"));
  });

  it("switches title and content to Russian and preserves lang in the URL", async () => {
    list.mockImplementation((_year: unknown, _confirmation: unknown, locale: string) => Promise.resolve({ status: "READY", orders: locale === "ru" ? [ruOrder] : [kkOrder] }));
    render(<MyOrdersPageClient />);
    expect(await screen.findByText(kkOrder.title)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Русский" }));
    expect(replace).toHaveBeenCalledWith("/profile/orders?lang=ru", { scroll: false });

    // The router refresh supplies the URL parameter after navigation.
    search = "lang=ru";
    cleanup();
    render(<MyOrdersPageClient />);
    expect(await screen.findByText(ruOrder.title)).toBeInTheDocument();
    expect(list).toHaveBeenLastCalledWith(undefined, "all", "ru");
  });

  it("uses the selected language for detail, close, and preliminary print", async () => {
    search = "lang=ru";
    list.mockResolvedValue({ status: "READY", orders: [ruOrder] });
    detail.mockResolvedValue({ ...ruOrder, preamble: "Русская преамбула", basis: "Русское основание", warning: "Предупреждение" });
    render(<MyOrdersPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Открыть" }));
    expect(await screen.findByText("Русская преамбула")).toBeInTheDocument();
    expect(screen.getByText("Русское основание")).toBeInTheDocument();
    expect(detail).toHaveBeenCalledWith(1, "ru");
    fireEvent.click(screen.getByRole("button", { name: "Распечатать предварительную версию" }));
    expect(window.print).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Русский" })).toHaveAttribute("aria-pressed", "true");
  });

  it("does not silently substitute Russian content when Kazakh blocks are absent", async () => {
    list.mockResolvedValue({ status: "READY", orders: [{ ...kkOrder, item_text: null }] });
    detail.mockResolvedValue({ ...kkOrder, item_text: null, preamble: null, basis: null, warning: null });
    render(<MyOrdersPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Ашу" }));
    expect(await screen.findByText("Бұйрық тармағының мәтіні электрондық нұсқада жоқ")).toBeInTheDocument();
    expect(screen.getByText("Бұйрықтың кіріспе мәтіні электрондық нұсқада жоқ")).toBeInTheDocument();
    expect(screen.queryByText("RETURN_FROM_CHILDCARE_LEAVE")).not.toBeInTheDocument();
    expect(screen.queryByText("COMPOSITE")).not.toBeInTheDocument();
  });
});
