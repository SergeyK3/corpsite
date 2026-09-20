import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PersonnelDayDateField from "./PersonnelDayDateField";

describe("PersonnelDayDateField", () => {
  it("adds date separators while typing and keeps ISO as the submitted value", () => {
    const onChange = vi.fn();
    render(<PersonnelDayDateField label="Дата начала" value="" onChange={onChange} testId="date-field" />);

    const input = screen.getByTestId("date-field");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "20052024" } });

    expect(input).toHaveValue("20.05.2024");
    expect(onChange).toHaveBeenLastCalledWith("2024-05-20");
    expect(screen.getByRole("button", { name: "Открыть календарь для Дата начала" })).toBeInTheDocument();
  });
});
