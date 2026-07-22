import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeMilitaryCombobox from "./IntakeMilitaryCombobox";
import {
  applyIntakeMilitaryCompositionChange,
  getIntakeMilitaryRankOptions,
  INTAKE_MILITARY_COMPOSITION_CATALOG,
} from "@/lib/militaryDictionary";

afterEach(() => {
  cleanup();
});

function renderCompositionRankPair(initialComposition = "", initialRank = "") {
  function Harness() {
    const [composition, setComposition] = React.useState(initialComposition);
    const [rank, setRank] = React.useState(initialRank);
    const rankOptions = getIntakeMilitaryRankOptions(composition);

    return (
      <>
        <IntakeMilitaryCombobox
          label="Состав"
          value={composition}
          onChange={(nextComposition) => {
            const next = applyIntakeMilitaryCompositionChange(nextComposition, rank);
            setComposition(next.composition);
            setRank(next.rank);
          }}
          options={INTAKE_MILITARY_COMPOSITION_CATALOG}
          testId="military-composition"
        />
        <IntakeMilitaryCombobox
          label="Воинское звание"
          value={rank}
          onChange={setRank}
          options={rankOptions}
          disabled={!composition}
          testId="military-rank"
        />
      </>
    );
  }

  render(<Harness />);
}

async function pickOption(testId: string, optionLabel: string, query = "") {
  const input = screen.getByTestId(testId);
  fireEvent.click(input);
  if (query) {
    fireEvent.change(input, { target: { value: query } });
  }
  const list = await screen.findByTestId(`${testId}-list`);
  const options = Array.from(list.querySelectorAll('[role="option"]'));
  const target = options.find((option) => option.textContent === optionLabel);
  if (!target) {
    throw new Error(`Combobox option not found: ${optionLabel}`);
  }
  fireEvent.click(target);
}

describe("IntakeMilitaryCombobox", () => {
  it("shows chevron indicator on the trigger", () => {
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value=""
        onChange={() => {}}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    expect(screen.getByTestId("military-composition-chevron")).toHaveTextContent("▼");
  });

  it("does not open the dropdown on focus alone", () => {
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value="soldiers"
        onChange={() => {}}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    fireEvent.focus(screen.getByTestId("military-composition"));
    expect(screen.queryByTestId("military-composition-list")).not.toBeInTheDocument();
  });

  it("opens the full option list on click without filtering by the current value", async () => {
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value="soldiers"
        onChange={() => {}}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    fireEvent.click(screen.getByTestId("military-composition"));

    const list = await screen.findByTestId("military-composition-list");
    expect(list.querySelectorAll('[role="option"]')).toHaveLength(5);
  });

  it("opens the dropdown on ArrowDown, Enter, and Space", async () => {
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value=""
        onChange={() => {}}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    const input = screen.getByTestId("military-composition");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(await screen.findByTestId("military-composition-list")).toBeInTheDocument();
    fireEvent.blur(input);
    await waitFor(() => {
      expect(screen.queryByTestId("military-composition-list")).not.toBeInTheDocument();
    });

    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByTestId("military-composition-list")).toBeInTheDocument();
    fireEvent.blur(input);
    await waitFor(() => {
      expect(screen.queryByTestId("military-composition-list")).not.toBeInTheDocument();
    });

    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: " " });
    expect(await screen.findByTestId("military-composition-list")).toBeInTheDocument();
  });

  it("replaces the current value when another option is selected without clearing first", () => {
    const onChange = vi.fn();
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value="soldiers"
        onChange={onChange}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    fireEvent.click(screen.getByTestId("military-composition"));
    fireEvent.click(screen.getByText("Офицерский состав"));

    expect(onChange).toHaveBeenCalledWith("officers");
  });

  it("reopens the list on repeated click while the input stays focused", () => {
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value="soldiers"
        onChange={() => {}}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    const input = screen.getByTestId("military-composition");
    fireEvent.click(input);
    fireEvent.click(screen.getByText("Офицерский состав"));
    expect(screen.queryByTestId("military-composition-list")).not.toBeInTheDocument();

    fireEvent.click(input);
    expect(screen.getByTestId("military-composition-list")).toBeInTheDocument();
  });

  it("opens the dropdown when clicking the trigger area outside the input", () => {
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value=""
        onChange={() => {}}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    fireEvent.mouseDown(screen.getByTestId("military-composition-trigger"));
    expect(screen.getByTestId("military-composition-list")).toBeInTheDocument();
  });

  it("keeps confirmed value on blur without calling onChange", async () => {
    const onChange = vi.fn();
    render(
      <IntakeMilitaryCombobox
        label="Состав"
        value="officers"
        onChange={onChange}
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        testId="military-composition"
      />,
    );

    const input = screen.getByTestId("military-composition");
    fireEvent.focus(input);
    fireEvent.blur(input);

    await waitFor(() => {
      expect(onChange).not.toHaveBeenCalled();
    });
    expect(input).toHaveValue("Офицерский состав");
  });
});

describe("IntakeMilitaryCombobox composition and rank interaction", () => {
  it("keeps composition after Tab and leaves rank dropdown closed", async () => {
    renderCompositionRankPair();

    await pickOption("military-composition", "Офицерский состав");
    expect(screen.getByTestId("military-composition")).toHaveValue("Офицерский состав");

    fireEvent.keyDown(screen.getByTestId("military-composition"), { key: "Tab" });
    fireEvent.focus(screen.getByTestId("military-rank"));

    await waitFor(() => {
      expect(screen.getByTestId("military-composition")).toHaveValue("Офицерский состав");
    });
    expect(screen.queryByTestId("military-rank-list")).not.toBeInTheDocument();
  });

  it("keeps composition when selecting and changing rank", async () => {
    renderCompositionRankPair();

    await pickOption("military-composition", "Офицерский состав");
    await pickOption("military-rank", "Капитан");
    expect(screen.getByTestId("military-composition")).toHaveValue("Офицерский состав");
    expect(screen.getByTestId("military-rank")).toHaveValue("Капитан");

    await pickOption("military-rank", "Старший лейтенант");
    expect(screen.getByTestId("military-composition")).toHaveValue("Офицерский состав");
    expect(screen.getByTestId("military-rank")).toHaveValue("Старший лейтенант");
  });

  it("clears incompatible rank when composition changes but keeps the new composition", async () => {
    renderCompositionRankPair("officers", "Капитан");

    await pickOption("military-composition", "Сержантский состав");
    expect(screen.getByTestId("military-composition")).toHaveValue("Сержантский состав");
    expect(screen.getByTestId("military-rank")).toHaveValue("");
  });

  it("does not clear confirmed values on blur for either combobox", async () => {
    renderCompositionRankPair("officers", "Капитан");

    fireEvent.blur(screen.getByTestId("military-composition"));
    fireEvent.blur(screen.getByTestId("military-rank"));

    await waitFor(() => {
      expect(screen.getByTestId("military-composition")).toHaveValue("Офицерский состав");
      expect(screen.getByTestId("military-rank")).toHaveValue("Капитан");
    });
  });
});
