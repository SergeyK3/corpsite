import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PprCardVersionedSectionEditor from "./PprCardVersionedSectionEditor";

const create = vi.fn();
const supersede = vi.fn();

vi.mock("../_lib/pprQueryApi.client", () => ({
  createPprCardRecord: (...args: unknown[]) => create(...args),
  supersedePprCardRecord: (...args: unknown[]) => supersede(...args),
  voidPprCardRecord: vi.fn(),
}));

afterEach(() => {
  cleanup();
  create.mockReset();
  supersede.mockReset();
});

describe("PprCardVersionedSectionEditor education selects", () => {
  it("creates education with Russian labels and canonical enum codes", async () => {
    create.mockResolvedValue({});
    render(<PprCardVersionedSectionEditor personId={7} section="education" active={[]} onSaved={vi.fn()} />);

    fireEvent.click(screen.getByText("Добавить запись"));
    expect(screen.getByRole("option", { name: "Основное образование" })).toHaveValue("basic");
    expect(screen.getByRole("option", { name: "ВУЗ (университет, академия, институт)" })).toHaveValue("university");
    expect(screen.getByRole("option", { name: "Не указано" })).toHaveValue("unknown");
    fireEvent.change(screen.getByLabelText("Вид образования"), { target: { value: "masters" } });
    fireEvent.change(screen.getByLabelText("Тип учреждения"), { target: { value: "university" } });
    fireEvent.change(screen.getByLabelText("Учебное заведение"), { target: { value: "КазНУ" } });
    fireEvent.click(screen.getByText("Сохранить"));

    await waitFor(() => expect(create).toHaveBeenCalledWith(7, "education", expect.objectContaining({
      record: expect.objectContaining({ education_kind: "masters", institution_type: "university", institution_name: "КазНУ" }),
    })));
  });

  it("edits a canonical record and keeps unknown as its canonical code", async () => {
    supersede.mockResolvedValue({});
    render(<PprCardVersionedSectionEditor personId={7} section="education" active={[{
      record_id: 42, education_kind: "other", institution_type: "unknown", institution_name: "Архивная запись",
      specialty: null, qualification: null, started_at: null, completed_at: null, diploma_number: null,
      document_date: null, verification_status: "pending", lifecycle_status: "active", updated_at: "2026-01-01T00:00:00Z",
    }]} onSaved={vi.fn()} />);

    fireEvent.click(screen.getByText("Редактировать"));
    expect(screen.getByLabelText("Вид образования")).toHaveValue("other");
    expect(screen.getByLabelText("Тип учреждения")).toHaveValue("unknown");
    fireEvent.click(screen.getByText("Сохранить"));

    await waitFor(() => expect(supersede).toHaveBeenCalledWith(7, "education", 42, expect.objectContaining({
      replacement: expect.objectContaining({ education_kind: "other", institution_type: "unknown" }),
    })));
  });
});
