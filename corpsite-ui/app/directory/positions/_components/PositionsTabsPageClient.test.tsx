import * as React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import PositionsTabsPageClient from "./PositionsTabsPageClient";

vi.mock("./PositionsPageClient", () => ({
  default: function MockPositionsPageClient() {
    const [filter, setFilter] = React.useState("");
    return <input aria-label="Фильтр справочника" value={filter} onChange={(event) => setFilter(event.target.value)} />;
  },
}));
vi.mock("./PositionAssignmentReport", () => ({
  default: () => <div>Сверка должностей с назначениями сотрудников</div>,
}));

test("catalog is the default tab and keeps its state after viewing reports", () => {
  render(<PositionsTabsPageClient />);
  const catalog = screen.getByRole("tab", { name: "Справочник" });
  const reports = screen.getByRole("tab", { name: "Отчёты" });
  expect(catalog.getAttribute("aria-selected")).toBe("true");
  const filter = screen.getByRole("textbox", { name: "Фильтр справочника" }) as HTMLInputElement;
  fireEvent.change(filter, { target: { value: "врач" } });

  fireEvent.click(reports);
  expect(reports.getAttribute("aria-selected")).toBe("true");
  expect(screen.getByText("Сверка должностей с назначениями сотрудников")).toBeTruthy();
  fireEvent.click(catalog);
  expect(screen.getByRole("textbox", { name: "Фильтр справочника" })).toBe(filter);
  expect(filter.value).toBe("врач");
});
