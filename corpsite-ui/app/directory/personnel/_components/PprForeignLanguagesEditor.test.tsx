import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PprForeignLanguagesEditor from "./PprForeignLanguagesEditor";

const save = vi.fn();
vi.mock("../_lib/pprQueryApi.client", () => ({ savePprForeignLanguages: (...args: unknown[]) => save(...args) }));
afterEach(cleanup);

describe("PprForeignLanguagesEditor", () => {
  it("selects a standard language and proficiency", () => {
    render(<PprForeignLanguagesEditor personId={1} items={[{ language: "Английский", proficiency: "" }]} version="v" onSaved={vi.fn()} />);
    fireEvent.click(screen.getByText("Редактировать"));
    expect(screen.getByLabelText("Язык 1")).toHaveValue("Английский");
    fireEvent.change(screen.getByLabelText("Уровень владения 1"), { target: { value: "Владеет свободно" } });
    expect(screen.getByLabelText("Уровень владения 1")).toHaveValue("Владеет свободно");
  });
  it("uses Other for legacy values and requires its text input", () => {
    render(<PprForeignLanguagesEditor personId={1} items={[{ language: "Italian", proficiency: "Со словарём" }]} version="v" onSaved={vi.fn()} />);
    fireEvent.click(screen.getByText("Редактировать"));
    expect(screen.getByLabelText("Язык 1")).toHaveValue("Другой");
    expect(screen.getByLabelText("Укажите язык 1")).toHaveValue("Italian");
  });
  it("adds and removes a row", () => {
    render(<PprForeignLanguagesEditor personId={1} items={[]} version="v" onSaved={vi.fn()} />);
    fireEvent.click(screen.getByText("Редактировать")); fireEvent.click(screen.getByText("Добавить язык"));
    expect(screen.getByLabelText("Язык 1")).toBeInTheDocument(); fireEvent.click(screen.getByText("Удалить"));
    expect(screen.queryByLabelText("Язык 1")).not.toBeInTheDocument();
  });
});
