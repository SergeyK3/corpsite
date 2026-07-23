import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import {
  INTAKE_CITIZENSHIP_CATALOG,
  INTAKE_CITIZENSHIP_POPULAR,
  INTAKE_NATIONALITY_CATALOG,
  INTAKE_NATIONALITY_POPULAR,
} from "../_lib/intakePersonalDictionary";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("IntakeDictionaryCombobox", () => {
  it("shows chevron and popular citizenship options when opened", () => {
    render(
      <IntakeDictionaryCombobox
        label="Гражданство"
        value=""
        onChange={vi.fn()}
        popular={INTAKE_CITIZENSHIP_POPULAR}
        catalog={INTAKE_CITIZENSHIP_CATALOG}
        testId="intake-citizenship"
      />,
    );

    expect(screen.getByTestId("intake-citizenship-chevron")).toHaveTextContent("▼");
    fireEvent.click(screen.getByTestId("intake-citizenship"));
    expect(screen.getByTestId("intake-citizenship-list")).toBeInTheDocument();
    expect(screen.getByTestId("intake-citizenship-option-0")).toHaveTextContent("Казахстан");
  });

  it("commits selected nationality through onChange", () => {
    const onChange = vi.fn();
    render(
      <IntakeDictionaryCombobox
        label="Национальность"
        value=""
        onChange={onChange}
        popular={INTAKE_NATIONALITY_POPULAR}
        catalog={INTAKE_NATIONALITY_CATALOG}
        testId="intake-nationality"
      />,
    );

    fireEvent.click(screen.getByTestId("intake-nationality"));
    fireEvent.click(screen.getByTestId("intake-nationality-option-0"));
    expect(onChange).toHaveBeenCalledWith("казахи");
  });

  it("shows full popular list when opened with legacy saved citizenship value", () => {
    render(
      <IntakeDictionaryCombobox
        label="Гражданство"
        value="Республика Казахстан"
        onChange={vi.fn()}
        popular={INTAKE_CITIZENSHIP_POPULAR}
        catalog={INTAKE_CITIZENSHIP_CATALOG}
        testId="intake-citizenship"
      />,
    );

    expect(screen.getByTestId("intake-citizenship")).toHaveValue("Республика Казахстан");
    fireEvent.click(screen.getByTestId("intake-citizenship"));
    const options = screen.getAllByRole("option").map((node) => node.textContent);
    expect(options).toContain("Россия");
    expect(options).toContain("Кыргызстан");
    expect(options.length).toBeGreaterThanOrEqual(10);
  });

  it("hides chevron in read-only mode", () => {
    render(
      <IntakeDictionaryCombobox
        label="Гражданство"
        value="Казахстан"
        onChange={vi.fn()}
        readOnly
        popular={INTAKE_CITIZENSHIP_POPULAR}
        catalog={INTAKE_CITIZENSHIP_CATALOG}
        testId="intake-citizenship"
      />,
    );

    expect(screen.queryByTestId("intake-citizenship-chevron")).not.toBeInTheDocument();
    expect(screen.getByTestId("intake-citizenship")).toHaveValue("Казахстан");
  });
});
