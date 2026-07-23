import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeAdditionalStep from "./IntakeAdditionalStep";
import { emptyIntakeDraftPayload, type IntakeDraftPayload } from "../_lib/intakeApi.client";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function StatefulAdditionalStep({ initialPayload = emptyIntakeDraftPayload() }: { initialPayload?: IntakeDraftPayload }) {
  const [payload, setPayload] = React.useState(initialPayload);
  return (
    <>
      <IntakeAdditionalStep
        value={payload.additional}
        onChange={(additional) => setPayload((current) => ({ ...current, additional }))}
      />
      <pre data-testid="additional-payload-json">{JSON.stringify(payload.additional)}</pre>
    </>
  );
}

describe("IntakeAdditionalStep", () => {
  it("saves foreign language row after add and edit", async () => {
    render(<StatefulAdditionalStep />);
    fireEvent.click(screen.getByTestId("intake-foreign-languages-add-button"));
    const languageSelect = await screen.findByTestId("intake-foreign-language-language-0");
    fireEvent.change(languageSelect, { target: { value: "Английский" } });
    fireEvent.change(screen.getByTestId("intake-foreign-language-proficiency-0"), {
      target: { value: "Выше среднего (B2)" },
    });

    await waitFor(() => {
      expect(JSON.parse(screen.getByTestId("additional-payload-json").textContent || "{}")).toMatchObject({
        foreign_languages: [{ language: "Английский", proficiency: "Выше среднего (B2)" }],
      });
    });
  });

  it("marks foreign languages as none and clears rows", async () => {
    render(<StatefulAdditionalStep />);
    fireEvent.click(screen.getByTestId("intake-foreign-languages-add-button"));
    await screen.findByTestId("intake-foreign-language-row-0");
    fireEvent.click(screen.getByTestId("intake-foreign-languages-none-checkbox"));

    await waitFor(() => {
      expect(JSON.parse(screen.getByTestId("additional-payload-json").textContent || "{}")).toMatchObject({
        foreign_languages_none: true,
        foreign_languages: [],
      });
    });
    expect(screen.getByTestId("intake-foreign-languages-none-message")).toBeInTheDocument();
  });

  it("saves award category, exact name, document number and date", async () => {
    render(<StatefulAdditionalStep />);
    fireEvent.click(screen.getByTestId("intake-awards-add-button"));
    const awardsDesktop = await screen.findByTestId("intake-awards-desktop-view");
    const categorySelect = within(awardsDesktop).getByTestId("intake-award-category-0");
    fireEvent.change(categorySelect, { target: { value: "Благодарность" } });
    const nameInput = within(awardsDesktop).getByTestId("intake-award-name-0");
    fireEvent.focus(nameInput);
    fireEvent.change(nameInput, { target: { value: "Благодарность Министерства здравоохранения" } });
    fireEvent.blur(nameInput);
    await waitFor(() => {
      expect(JSON.parse(screen.getByTestId("additional-payload-json").textContent || "{}").awards[0]?.name).toBe(
        "Благодарность Министерства здравоохранения",
      );
    });
    fireEvent.change(within(awardsDesktop).getByTestId("intake-award-document-number-0"), {
      target: { value: "MD-001" },
    });
    const dateInput = within(awardsDesktop).getByTestId("intake-award-awarded-at-0");
    fireEvent.focus(dateInput);
    fireEvent.change(dateInput, { target: { value: "10.05.2020" } });
    fireEvent.blur(dateInput);

    await waitFor(() => {
      expect(JSON.parse(screen.getByTestId("additional-payload-json").textContent || "{}")).toMatchObject({
        awards: [
          {
            category: "Благодарность",
            name: "Благодарность Министерства здравоохранения",
            document_number: "MD-001",
            awarded_at: "2020-05-10",
          },
        ],
      });
    });
  });

  it("saves academic degree and title with independent dates and document numbers", async () => {
    render(<StatefulAdditionalStep />);
    fireEvent.click(screen.getByTestId("intake-academic-degrees-add-button"));
    const degreesDesktop = await screen.findByTestId("intake-academic-degrees-desktop-view");
    fireEvent.change(within(degreesDesktop).getByTestId("intake-academic-degree-degree-0"), {
      target: { value: "PhD" },
    });
    const degreeFieldInput = within(degreesDesktop).getByTestId("intake-academic-degree-field-of-science-0");
    fireEvent.click(degreeFieldInput);
    fireEvent.click(await screen.findByTestId("intake-academic-degree-field-of-science-0-option-2"));
    fireEvent.change(within(degreesDesktop).getByTestId("intake-academic-degree-completed-at-0"), {
      target: { value: "30.06.2018" },
    });
    fireEvent.change(within(degreesDesktop).getByTestId("intake-academic-degree-document-number-0"), {
      target: { value: "DEG-1" },
    });

    fireEvent.click(screen.getByTestId("intake-academic-titles-add-button"));
    const titlesDesktop = await screen.findByTestId("intake-academic-titles-desktop-view");
    fireEvent.change(within(titlesDesktop).getByTestId("intake-academic-title-academic-title-0"), {
      target: { value: "Доцент" },
    });
    const titleFieldInput = within(titlesDesktop).getByTestId("intake-academic-title-field-of-science-0");
    fireEvent.click(titleFieldInput);
    fireEvent.click(await screen.findByTestId("intake-academic-title-field-of-science-0-option-2"));
    fireEvent.change(within(titlesDesktop).getByTestId("intake-academic-title-completed-at-0"), {
      target: { value: "01.05.2019" },
    });
    fireEvent.change(within(titlesDesktop).getByTestId("intake-academic-title-document-number-0"), {
      target: { value: "TTL-2" },
    });

    await waitFor(() => {
      expect(JSON.parse(screen.getByTestId("additional-payload-json").textContent || "{}")).toMatchObject({
        academic_degrees: [
          {
            degree: "PhD",
            field_of_science: "Экономика",
            completed_at: "2018-06-30",
            document_number: "DEG-1",
          },
        ],
        academic_titles: [
          {
            academic_title: "Доцент",
            field_of_science: "Экономика",
            completed_at: "2019-05-01",
            document_number: "TTL-2",
          },
        ],
      });
    });
  });

  it("renders compact inline table editors aligned with section columns", async () => {
    render(<StatefulAdditionalStep />);
    fireEvent.click(screen.getByTestId("intake-awards-add-button"));
    fireEvent.click(screen.getByTestId("intake-academic-degrees-add-button"));
    fireEvent.click(screen.getByTestId("intake-academic-titles-add-button"));

    const awardsDesktop = await screen.findByTestId("intake-awards-desktop-view");
    const degreesDesktop = screen.getByTestId("intake-academic-degrees-desktop-view");
    const titlesDesktop = screen.getByTestId("intake-academic-titles-desktop-view");

    expect(within(awardsDesktop).getByTestId("intake-award-expanded-0").querySelectorAll("td")).toHaveLength(6);
    expect(within(degreesDesktop).getByTestId("intake-academic-degree-expanded-0").querySelectorAll("td")).toHaveLength(5);
    expect(within(titlesDesktop).getByTestId("intake-academic-title-expanded-0").querySelectorAll("td")).toHaveLength(5);
  });
});
