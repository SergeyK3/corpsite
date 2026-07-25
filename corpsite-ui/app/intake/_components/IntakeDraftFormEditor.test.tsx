import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import { emptyIntakeDraftPayload, formatIntakeStepHeaderTitle, INTAKE_STEPS } from "../_lib/intakeApi.client";

vi.mock("./IntakeDictionaryCombobox", () => ({
  default: ({ label, testId }: { label: string; testId?: string }) => (
    <input aria-label={label} data-testid={testId} readOnly />
  ),
}));

vi.mock("./IntakeMilitaryCombobox", () => ({
  default: ({ label, testId }: { label: string; testId?: string }) => (
    <input aria-label={label} data-testid={testId} readOnly />
  ),
}));

const personalStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "personal");
const educationStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "education");
const trainingStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "training");
const contactsStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "contacts");
const additionalStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "additional");

function expandEducationRow(index = 0) {
  const desktop = screen.getByTestId("intake-education-desktop-view");
  fireEvent.click(within(desktop).getByTestId(`intake-education-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-education-row-edit-${index}`));
}

const reviewStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "review");

function renderEditor(
  payload = emptyIntakeDraftPayload(),
  stepIndex = personalStepIndex,
  onChange = vi.fn(),
) {
  return render(
    <IntakeDraftFormEditor
      payload={payload}
      onChange={onChange}
      stepIndex={stepIndex}
      onStepIndexChange={vi.fn()}
      compact
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function expandTrainingRow(index = 0) {
  const desktop = screen.getByTestId("intake-training-desktop-view");
  fireEvent.click(within(desktop).getByTestId(`intake-training-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-training-row-edit-${index}`));
}

describe("IntakeDraftFormEditor period validation", () => {
  it("shows reversed training period error on the record editor", () => {
    const payload = emptyIntakeDraftPayload();
    payload.training = [
      {
        institution: "Учебный центр охраны труда",
        course_name: "Охрана труда и техника безопасности",
        year_from: "2024-07-10",
        year_to: "2024-06-01",
        document_type: "certificate",
        document_number: "ОТ-178-01",
        hours: "40",
        hours_is_manual: true,
      },
    ];

    renderEditor(payload, trainingStepIndex);

    expect(
      within(screen.getByTestId("intake-training-desktop-view")).getByTestId("intake-training-period-error-0"),
    ).toHaveTextContent("Дата окончания не может быть раньше даты начала");
  });

  it("shows reversed training period error in expanded editor after edit", () => {
    const payload = emptyIntakeDraftPayload();
    payload.training = [
      {
        institution: "Центр",
        course_name: "Первая помощь",
        year_from: "2024-06-01",
        year_to: "2024-05-10",
        hours: "",
        hours_is_manual: false,
      },
    ];

    renderEditor(payload, trainingStepIndex);
    expandTrainingRow(0);

    expect(within(screen.getByTestId("intake-training-desktop-view")).getByTestId("intake-training-editor-period-error-0")).toHaveTextContent(
      "Дата окончания не может быть раньше даты начала",
    );
  });

  it("shows reversed education period error on the record editor", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2022-09-01",
        year_to: "2022-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
      },
    ];

    renderEditor(payload, educationStepIndex);
    expandEducationRow(0);

    expect(within(screen.getByTestId("intake-education-desktop-view")).getByTestId("intake-education-period-error-0")).toHaveTextContent(
      "Дата окончания не может быть раньше даты начала",
    );
  });
});

describe("IntakeDraftFormEditor step headers", () => {
  INTAKE_STEPS.forEach((step, index) => {
    it(`shows unified header for step ${index + 1} (${step.id})`, () => {
      renderEditor(emptyIntakeDraftPayload(), index);
      expect(
        screen.getByRole("heading", { name: formatIntakeStepHeaderTitle(index) }),
      ).toBeInTheDocument();
    });
  });
});

describe("IntakeDraftFormEditor date fields", () => {
  it("renders birth date with full-day birth editor on personal step", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.birth_date = "1990-05-20";

    renderEditor(payload, personalStepIndex);

    const birthInput = screen.getByTestId("intake-birth-date");
    expect(birthInput).toHaveAttribute("placeholder", "ДД.ММ.ГГГГ");
    expect(birthInput).toHaveValue("20.05.1990");
  });

  it("stores edited birth date as canonical ISO", () => {
    const payload = emptyIntakeDraftPayload();
    const onChange = vi.fn();
    renderEditor(payload, personalStepIndex, onChange);

    fireEvent.change(screen.getByTestId("intake-birth-date"), {
      target: { value: "15.09.2018" },
    });

    expect(onChange).toHaveBeenCalled();
    const nextPayload = onChange.mock.calls.at(-1)?.[0];
    expect(nextPayload.personal.birth_date).toBe("2018-09-15");
  });

  it("renders period date fields with full-day period editor on education step", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018",
        specialty: "",
        qualification: "",
        document_type: "diploma",
        diploma_number: "",
      },
    ];

    renderEditor(payload, educationStepIndex);

    expandEducationRow(0);

    const desktop = screen.getByTestId("intake-education-desktop-view");
    const fromInput = within(desktop).getByTestId("intake-education-year-from-0");
    const toInput = within(desktop).getByTestId("intake-education-year-to-0");

    expect(fromInput).toHaveAttribute("placeholder", "ДД.ММ.ГГГГ");
    expect(fromInput).toHaveValue("01.09.2014");
    expect(toInput).toHaveValue("2018 (уточните дату)");
    expect(within(desktop).getByTestId("intake-education-year-to-0-hint")).toHaveTextContent(
      "Укажите полную дату в формате ДД.ММ.ГГГГ",
    );
  });

  it("stores edited period date as canonical ISO", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "",
        year_to: "",
        specialty: "",
        qualification: "",
        document_type: "diploma",
        diploma_number: "",
      },
    ];
    const onChange = vi.fn();
    renderEditor(payload, educationStepIndex, onChange);

    expandEducationRow(0);

    fireEvent.change(within(screen.getByTestId("intake-education-desktop-view")).getByTestId("intake-education-year-from-0"), {
      target: { value: "01.09.2014" },
    });

    expect(onChange).toHaveBeenCalled();
    const nextPayload = onChange.mock.calls.at(-1)?.[0];
    expect(nextPayload.education[0].year_from).toBe("2014-09-01");
  });

  it("renders additional step sections", () => {
    renderEditor(emptyIntakeDraftPayload(), additionalStepIndex);
    expect(screen.getByTestId("intake-additional-step")).toBeInTheDocument();
    expect(screen.getByTestId("intake-foreign-languages-section")).toBeInTheDocument();
    expect(screen.getByTestId("intake-awards-section")).toBeInTheDocument();
    expect(screen.getByTestId("intake-academic-degrees-section")).toBeInTheDocument();
  });

  it("renders personal card fields on personal step", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.last_name = "Иванов";
    payload.personal.birth_place = "г. Алматы";

    renderEditor(payload, personalStepIndex);

    expect(screen.getByTestId("intake-birth-place")).toHaveValue("г. Алматы");
    expect(screen.getByTestId("intake-alphabet")).toHaveValue("И");
    expect(screen.queryByTestId("intake-personnel-number")).not.toBeInTheDocument();
  });

  it("shows personnel number field for HR on-behalf even when empty", () => {
    render(
      <IntakeDraftFormEditor
        payload={emptyIntakeDraftPayload()}
        onChange={vi.fn()}
        stepIndex={personalStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
      />,
    );

    expect(screen.getByTestId("intake-personnel-number")).toBeInTheDocument();
  });

  it("shows generate PDF button on review step", () => {
    const onGeneratePdf = vi.fn();
    render(
      <IntakeDraftFormEditor
        payload={emptyIntakeDraftPayload()}
        onChange={vi.fn()}
        stepIndex={reviewStepIndex}
        onStepIndexChange={vi.fn()}
        compact
        onGeneratePdf={onGeneratePdf}
      />,
    );
    const button = screen.getByTestId("intake-generate-pdf-button");
    expect(button).toHaveTextContent("Сформировать PDF");
    fireEvent.click(button);
    expect(onGeneratePdf).toHaveBeenCalledTimes(1);
  });
});

describe("IntakeDraftFormEditor step navigation", () => {
  function renderAtStep(stepIndex: number, onStepIndexChange = vi.fn(), onChange = vi.fn()) {
    render(
      <IntakeDraftFormEditor
        payload={emptyIntakeDraftPayload()}
        onChange={onChange}
        stepIndex={stepIndex}
        onStepIndexChange={onStepIndexChange}
        compact
      />,
    );
    return { onStepIndexChange, onChange };
  }

  it("navigates to the first step via Начало", () => {
    const onStepIndexChange = vi.fn();
    const onChange = vi.fn();
    renderAtStep(educationStepIndex, onStepIndexChange, onChange);

    fireEvent.click(screen.getByTestId("intake-nav-start"));

    expect(onStepIndexChange).toHaveBeenCalledWith(personalStepIndex);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ current_step: "personal" }),
    );
  });

  it("navigates to the review step via Конец", () => {
    const onStepIndexChange = vi.fn();
    const onChange = vi.fn();
    renderAtStep(personalStepIndex, onStepIndexChange, onChange);

    fireEvent.click(screen.getByTestId("intake-nav-end"));

    expect(onStepIndexChange).toHaveBeenCalledWith(reviewStepIndex);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ current_step: "review" }),
    );
  });

  it("keeps Назад working to the previous step", () => {
    const onStepIndexChange = vi.fn();
    const onChange = vi.fn();
    renderAtStep(educationStepIndex, onStepIndexChange, onChange);

    fireEvent.click(screen.getByTestId("intake-nav-back"));

    expect(onStepIndexChange).toHaveBeenCalledWith(educationStepIndex - 1);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ current_step: INTAKE_STEPS[educationStepIndex - 1].id }),
    );
  });

  it("keeps Далее working to the next step", () => {
    const onStepIndexChange = vi.fn();
    const onChange = vi.fn();
    renderAtStep(educationStepIndex, onStepIndexChange, onChange);

    fireEvent.click(screen.getByTestId("intake-nav-next"));

    expect(onStepIndexChange).toHaveBeenCalledWith(educationStepIndex + 1);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ current_step: INTAKE_STEPS[educationStepIndex + 1].id }),
    );
  });

  it("works in HR on-behalf mode", () => {
    const onStepIndexChange = vi.fn();
    render(
      <IntakeDraftFormEditor
        payload={emptyIntakeDraftPayload()}
        onChange={vi.fn()}
        stepIndex={educationStepIndex}
        onStepIndexChange={onStepIndexChange}
        mode="hr-on-behalf"
        compact
      />,
    );

    fireEvent.click(screen.getByTestId("intake-nav-start"));
    expect(onStepIndexChange).toHaveBeenCalledWith(personalStepIndex);

    fireEvent.click(screen.getByTestId("intake-nav-end"));
    expect(onStepIndexChange).toHaveBeenCalledWith(reviewStepIndex);
  });
});

describe("IntakeDraftFormEditor review and submit actions", () => {
  it("shows public submit label on review step", () => {
    render(
      <IntakeDraftFormEditor
        payload={emptyIntakeDraftPayload()}
        onChange={vi.fn()}
        stepIndex={reviewStepIndex}
        onStepIndexChange={vi.fn()}
        compact
        onPrimaryAction={vi.fn()}
      />,
    );

    expect(screen.getByTestId("intake-submit-button")).toHaveTextContent("Отправить в отдел кадров");
    expect(screen.queryByTestId("intake-on-behalf-save-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("intake-on-behalf-submit-button")).not.toBeInTheDocument();
  });

  it("shows HR save and submit buttons on review step", () => {
    render(
      <IntakeDraftFormEditor
        payload={emptyIntakeDraftPayload()}
        onChange={vi.fn()}
        stepIndex={reviewStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
        onPrimaryAction={vi.fn()}
        onSecondaryAction={vi.fn()}
      />,
    );

    expect(screen.getByTestId("intake-on-behalf-save-button")).toHaveTextContent(
      "Сохранить от имени претендента",
    );
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toHaveTextContent("Отправить анкету");
    expect(screen.queryByTestId("intake-submit-button")).not.toBeInTheDocument();
  });

  it("renders all eight review sections with edit actions", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.contacts.registration_address = "г. Алматы, ул. Абая 1";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
        specialty: "Медицина",
        qualification: "Бакалавр",
        diploma_number: "123",
      },
    ];
    payload.military.status = "Призывник";

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={reviewStepIndex}
        onStepIndexChange={vi.fn()}
        compact
      />,
    );

    expect(screen.getByTestId("intake-review-section-personal")).toHaveTextContent("Петров");
    expect(screen.getByTestId("intake-review-section-contacts")).toHaveTextContent("Абая");
    expect(screen.getByTestId("intake-review-education-item-0")).toHaveTextContent("КазНУ");
    expect(screen.getByTestId("intake-review-section-military")).toHaveTextContent("Призывник");
    expect(screen.getByTestId("intake-review-edit-personal")).toBeInTheDocument();
    expect(screen.getByTestId("intake-review-edit-contacts")).toBeInTheDocument();
    expect(screen.getByTestId("intake-review-edit-education")).toBeInTheDocument();
    expect(screen.getByTestId("intake-review-edit-training")).toBeInTheDocument();
    expect(screen.getByTestId("intake-review-edit-relatives")).toBeInTheDocument();
    expect(screen.getByTestId("intake-review-edit-employment")).toBeInTheDocument();
    expect(screen.getByTestId("intake-review-edit-military")).toBeInTheDocument();
    expect(screen.getByTestId("intake-review-edit-additional")).toBeInTheDocument();
  });

  it("navigates to the selected section via Изменить", () => {
    const onStepIndexChange = vi.fn();
    const onChange = vi.fn();
    const payload = emptyIntakeDraftPayload();
    payload.contacts.mobile_phone = "+77005554433";

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={onChange}
        stepIndex={reviewStepIndex}
        onStepIndexChange={onStepIndexChange}
        compact
      />,
    );

    fireEvent.click(screen.getByTestId("intake-review-edit-contacts"));

    expect(onStepIndexChange).toHaveBeenCalledWith(contactsStepIndex);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ current_step: "contacts" }),
    );
  });

  it("renders review summary sections and date issue navigation", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНМУ",
        year_from: "2014",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
      },
    ];
    const onStepIndexChange = vi.fn();

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={reviewStepIndex}
        onStepIndexChange={onStepIndexChange}
        compact
      />,
    );

    expect(screen.getByTestId("intake-review-summary")).toHaveTextContent("Петров");
    expect(screen.getByTestId("intake-review-date-issues")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Образование → КазНМУ → дата поступления"));
    expect(onStepIndexChange).toHaveBeenCalledWith(educationStepIndex);
  });

  it("blocks both HR review buttons when a reversed period remains", () => {
    const payload = emptyIntakeDraftPayload();
    payload.training = [
      {
        institution: "Учебный центр охраны труда",
        course_name: "Охрана труда и техника безопасности",
        year_from: "2024-07-10",
        year_to: "2024-06-01",
        document_type: "certificate",
        document_number: "ОТ-178-01",
        hours: "40",
        hours_is_manual: true,
      },
    ];

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={reviewStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
        onPrimaryAction={vi.fn()}
        onSecondaryAction={vi.fn()}
      />,
    );

    expect(screen.getByTestId("intake-on-behalf-save-button")).toBeDisabled();
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toBeDisabled();
    expect(
      screen.getByText(/Охрана труда и техника безопасности → Дата окончания не может быть раньше даты начала/i),
    ).toBeInTheDocument();
  });
});
