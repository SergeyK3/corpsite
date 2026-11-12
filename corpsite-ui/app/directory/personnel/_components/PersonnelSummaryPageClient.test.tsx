import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import PersonnelSummaryPageClient from "./PersonnelSummaryPageClient";

let params = new URLSearchParams("view=reports&report=cards&universe_id=7");
vi.mock("next/navigation", () => ({ useSearchParams: () => params }));
vi.mock("./MigrationStatusMatrixPageClient", () => ({ default: () => <div data-testid="existing-summary">Прежняя сводка</div> }));

afterEach(() => { cleanup(); params = new URLSearchParams("view=reports&report=cards&universe_id=7"); });

it("keeps only the card summary inside personal cards", () => {
  render(<PersonnelSummaryPageClient />);
  expect(screen.getByTestId("existing-summary")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Сводка по карточкам" })).toHaveAttribute("href", "/directory/personnel/lk?view=reports&report=cards&universe_id=7");
  expect(screen.queryByRole("link", { name: "Квалиф. категории" })).not.toBeInTheDocument();
});
