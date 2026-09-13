import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PprAdditionalStatusFactsEditor from "./PprAdditionalStatusFactsEditor";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn().mockResolvedValue({}) }));

describe("PprAdditionalStatusFactsEditor", () => {
  it("renders separate editable pension and disability tables", () => {
    render(<PprAdditionalStatusFactsEditor personId={1} facts={[{
      status_fact_id: 4, fact_kind: "PENSION", pension_kind: "AGE", effective_date: "2020-01-01",
      disability_group: null, icd10_code: null, review_status: "AUTO_READY", review_reason: null, version: 1, created_at: "2020-01-01T00:00:00Z",
    }]} onSaved={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Пенсионный статус" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Инвалидность" })).toBeInTheDocument();
    expect(screen.getByLabelText("Вид пенсионного статуса 1")).toHaveValue("AGE");
    fireEvent.click(screen.getByRole("button", { name: "Добавить запись об инвалидности" }));
    expect(screen.getByLabelText("Группа инвалидности 1")).toBeInTheDocument();
  });
});
