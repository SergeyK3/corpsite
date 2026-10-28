import * as React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Page from "./page";
import { apiFetchJson } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const rows = [
  { qualification_category_id: 1, code: 1, name: "Без категории", name_kk: "Санаты жоқ" },
  { qualification_category_id: 2, code: 2, name: "Вторая категория", name_kk: "Екінші санат" },
  { qualification_category_id: 3, code: 3, name: "Первая категория", name_kk: "Бірінші санат" },
  { qualification_category_id: 4, code: 4, name: "Высшая категория", name_kk: "Жоғары санат" },
];

it("renders the four bilingual rows and searches in RU and KK", async () => {
  vi.mocked(apiFetchJson).mockImplementation(async (_path, options) => {
    const q = String(options?.query?.q ?? "").toLowerCase();
    const items = rows.filter(row => row.name.toLowerCase().includes(q) || row.name_kk.toLowerCase().includes(q));
    return { items, total: items.length } as never;
  });
  render(<Page />);
  await screen.findByText("Всего: 4");
  expect(screen.getAllByRole("row")).toHaveLength(5);
  expect(screen.getAllByRole("columnheader").map(cell => cell.textContent)).toEqual(["ID", "Код", "На русском языке", "Қазақша атауы"]);
  for (const row of rows) expect(screen.getByText(row.name_kk)).toBeInTheDocument();
  for (const q of ["ПЕРВАЯ", "БІРІНШІ"]) {
    fireEvent.change(screen.getByLabelText("Поиск по RU / KK"), { target: { value: q } });
    await waitFor(() => expect(apiFetchJson).toHaveBeenLastCalledWith("/directory/medical-qualification-categories", { query: { q } }));
    await screen.findByText("Всего: 1");
    expect(screen.getByText("Первая категория")).toBeInTheDocument();
  }
  fireEvent.change(screen.getByLabelText("Поиск по RU / KK"), { target: { value: "Нет совпадений" } });
  await screen.findByText("Категории не найдены.");
});

it("shows API errors without reporting an empty classifier", async () => {
  vi.mocked(apiFetchJson).mockRejectedValue(new Error("Сбой API"));
  render(<Page />);
  await screen.findByRole("alert");
  expect(screen.queryByText("Всего: 0")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Выгрузить в Excel" })).toBeDisabled();
});
