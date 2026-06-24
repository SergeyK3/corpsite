import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TemplateDrawer from "./TemplateDrawer";
import TemplateAdvancedPlanningBlock, {
  ADVANCED_PLANNING_TITLE,
  CREATE_OFFSET_DAYS_HINT,
  DUE_OFFSET_DAYS_HINT,
} from "./TemplateAdvancedPlanningBlock";
import TemplateForm, { SCHEDULE_TYPE_FORM_OPTIONS } from "./TemplateForm";
import TemplateViewPanel from "./TemplateViewPanel";
import { TEMPLATE_FORM_ID } from "./templateDetailShared";
import { validateTemplateFormValues } from "@/lib/regularTaskTemplateFormValidation";
import { DEFAULT_SCHEDULE_PARAMS, resolveScheduleParamsOnTypeChange } from "@/lib/regularTaskScheduleParams";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const baseValues = {
  title: "Тестовый шаблон",
  description: "Описание",
  executor_role_id: "1",
  owner_unit_id: "10",
  schedule_type: "weekly",
  schedule_params: '{"byweekday":[3],"time":"10:00"}',
  create_offset_days: "0",
  due_offset_days: "0",
};

const ownerUnitOptions = [{ unit_id: 10, name: "Отделение A" }];
const executorRoleOptions = [
  { role_id: 1, name: "Госпитальный эксперт", code: "HOSP_EXPERT" },
  { role_id: 2, name: "Амбулаторный эксперт", code: "AMB_EXPERT" },
];

function renderTemplateForm(
  props: Partial<React.ComponentProps<typeof TemplateForm>> & {
    initialValues?: typeof baseValues;
    onSubmit?: ReturnType<typeof vi.fn>;
  } = {},
) {
  const { initialValues = baseValues, onSubmit = vi.fn(), ...rest } = props;
  return render(
    <TemplateForm
      mode="edit"
      initialValues={initialValues}
      onSubmit={onSubmit}
      ownerUnitOptions={ownerUnitOptions}
      executorRoleOptions={executorRoleOptions}
      {...rest}
    />,
  );
}

describe("TemplateForm schedule type select", () => {
  it("shows human-readable schedule type options", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    const select = screen.getByLabelText("Периодичность") as HTMLSelectElement;
    const options = within(select).getAllByRole("option");

    expect(options.map((option) => option.textContent)).toEqual(
      expect.arrayContaining(["Выберите периодичность", "Еженедельная", "Ежемесячная", "Ежегодная"]),
    );
    expect(SCHEDULE_TYPE_FORM_OPTIONS.map((option) => option.label)).toEqual([
      "Еженедельная",
      "Ежемесячная",
      "Ежегодная",
    ]);
  });

  it("submits schedule_type=monthly with monthly default params when monthly is selected", async () => {
    const onSubmit = vi.fn();

    render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        onSubmit={onSubmit}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "monthly" } });
    fireEvent.submit(document.getElementById(TEMPLATE_FORM_ID)!);

    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.schedule_type).toBe("monthly");
    expect(submitted.schedule_params).toContain('"bymonthday"');
    expect(submitted.schedule_params).not.toContain('"byweekday"');
  });

  it("weekly → monthly removes stale byweekday keys from schedule_params", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "monthly" } });

    const scheduleParamsField = screen.getByLabelText(/Параметры расписания/i) as HTMLTextAreaElement;
    const parsed = JSON.parse(scheduleParamsField.value);

    expect(parsed.bymonthday).toEqual([1]);
    expect(parsed).not.toHaveProperty("byweekday");
  });

  it("monthly → weekly removes stale bymonthday keys from schedule_params", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={{
          ...baseValues,
          schedule_type: "monthly",
          schedule_params: '{"bymonthday":[1],"time":"10:00"}',
        }}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "weekly" } });

    const scheduleParamsField = screen.getByLabelText(/Параметры расписания/i) as HTMLTextAreaElement;
    const parsed = JSON.parse(scheduleParamsField.value);

    expect(parsed.byweekday).toEqual([1]);
    expect(parsed).not.toHaveProperty("bymonthday");
  });

  it("submits schedule_type=yearly with yearly default params when yearly is selected", async () => {
    const onSubmit = vi.fn();

    renderTemplateForm({
      initialValues: {
        ...baseValues,
        schedule_type: "monthly",
        schedule_params: '{"bymonthday":[1],"time":"10:00"}',
      },
      onSubmit,
    });

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "yearly" } });
    fireEvent.submit(document.getElementById(TEMPLATE_FORM_ID)!);

    expect(onSubmit.mock.calls[0][0].schedule_params).toContain('"bymonth"');
    expect(onSubmit.mock.calls[0][0].schedule_params).toContain('"bymonthday"');
    expect(JSON.parse(onSubmit.mock.calls[0][0].schedule_params)).toEqual(DEFAULT_SCHEDULE_PARAMS.yearly);
  });

  it("monthly → weekly resets JSON to byweekday default (OPS-009.31)", () => {
    renderTemplateForm({
      initialValues: {
        ...baseValues,
        schedule_type: "monthly",
        schedule_params: '{"bymonthday":[15],"time":"08:00"}',
      },
    });

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "weekly" } });

    expect(JSON.parse((screen.getByLabelText(/Параметры расписания/i) as HTMLTextAreaElement).value)).toEqual(
      DEFAULT_SCHEDULE_PARAMS.weekly,
    );
  });
});

describe("TemplateForm validation feedback", () => {
  it("shows a visible validation reason for invalid monthly schedule_params", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={{
          ...baseValues,
          schedule_type: "monthly",
          schedule_params: '{"time":"10:00"}',
        }}
        validate={validateTemplateFormValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("bymonthday");
  });

  it("does not show validation alert for valid monthly schedule_params", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={{
          ...baseValues,
          schedule_type: "monthly",
          schedule_params: '{"bymonthday":[1],"time":"10:00"}',
        }}
        validate={validateTemplateFormValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps monthly default JSON valid after switching schedule type", () => {
    const onValidationChange = vi.fn();

    render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        validate={validateTemplateFormValues}
        onFormValidationChange={onValidationChange}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "monthly" } });

    const scheduleParamsField = screen.getByLabelText(/Параметры расписания/i) as HTMLTextAreaElement;

    expect(onValidationChange).toHaveBeenLastCalledWith(null);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(
      validateTemplateFormValues({
        ...baseValues,
        schedule_type: "monthly",
        schedule_params: scheduleParamsField.value,
      }),
    ).toBeNull();
  });

  it("preserves manual JSON edits until schedule_type changes again", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        validate={validateTemplateFormValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "monthly" } });

    const scheduleParamsField = screen.getByLabelText(/Параметры расписания/i) as HTMLTextAreaElement;
    const manualMonthly = '{"bymonthday":[15],"time":"11:00"}';
    fireEvent.change(scheduleParamsField, { target: { value: manualMonthly } });
    fireEvent.change(screen.getByLabelText(/^Отчёт/), { target: { value: "Updated title" } });

    expect(scheduleParamsField.value).toBe(manualMonthly);
    expect(validateTemplateFormValues({
      ...baseValues,
      title: "Updated title",
      schedule_type: "monthly",
      schedule_params: scheduleParamsField.value,
    })).toBeNull();

    fireEvent.change(screen.getByLabelText("Периодичность"), { target: { value: "yearly" } });

    const parsed = JSON.parse(scheduleParamsField.value);
    expect(parsed.bymonth).toEqual([1]);
    expect(parsed.bymonthday).toEqual([1]);
    expect(parsed.bymonthday).not.toEqual([15]);
  });
});

describe("TemplateForm executor role select", () => {
  it("renders executor_role_id as dropdown instead of numeric input", () => {
    renderTemplateForm();

    expect(screen.getByLabelText(/^Роль исполнителя/)).toBeTruthy();
    expect(screen.getByRole("combobox", { name: /^Роль исполнителя/ })).toBeTruthy();
    expect(screen.queryByPlaceholderText("Например: 60")).toBeNull();
  });

  it("preserves selected role id on edit", () => {
    renderTemplateForm({
      initialValues: { ...baseValues, executor_role_id: "2" },
    });

    expect((screen.getByLabelText(/^Роль исполнителя/) as HTMLSelectElement).value).toBe("2");
    expect(screen.getByRole("option", { name: "Амбулаторный эксперт (#2)" }).selected).toBe(true);
  });

  it("updates executor_role_id when role is changed", () => {
    const onSubmit = vi.fn();

    renderTemplateForm({ onSubmit });

    fireEvent.change(screen.getByLabelText(/^Роль исполнителя/), { target: { value: "2" } });
    fireEvent.submit(document.getElementById(TEMPLATE_FORM_ID)!);

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        executor_role_id: "2",
      }),
    );
  });

  it("shows fallback option when role id is missing from directory", () => {
    renderTemplateForm({
      initialValues: { ...baseValues, executor_role_id: "99" },
    });

    expect(screen.getByRole("option", { name: "ID роли: 99" }).selected).toBe(true);
  });
});

describe("OPS-009.31 schedule params reset", () => {
  it("weekly → monthly uses exact monthly default JSON", () => {
    const result = resolveScheduleParamsOnTypeChange(
      "weekly",
      "monthly",
      JSON.stringify({ byweekday: [3] }, null, 2),
    );

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.monthly);
  });

  it("monthly → yearly uses exact yearly default JSON", () => {
    const result = resolveScheduleParamsOnTypeChange(
      "monthly",
      "yearly",
      JSON.stringify({ bymonthday: [15], time: "08:00" }, null, 2),
    );

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.yearly);
  });

  it("monthly → weekly uses exact weekly default JSON", () => {
    const result = resolveScheduleParamsOnTypeChange(
      "monthly",
      "weekly",
      JSON.stringify({ bymonthday: [15], time: "08:00" }, null, 2),
    );

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.weekly);
  });
});

describe("TemplateForm owner unit field", () => {
  it("does not render manual owner unit id input", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    expect(screen.queryByLabelText(/owner_unit_id/i)).toBeNull();
    expect(screen.queryByText(/Можно выбрать из списка или ввести ID вручную/i)).toBeNull();
    expect(screen.queryByText("Подсказка")).toBeNull();
    expect(screen.getByLabelText(/^Подразделение/)).toBeTruthy();
  });
});

describe("Template advanced planning settings", () => {
  it("hides offset fields in edit mode until the block is expanded", () => {
    render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    expect(screen.getByRole("button", { name: new RegExp(ADVANCED_PLANNING_TITLE) })).toBeTruthy();
    expect(screen.queryByLabelText("Создать за N дней")).toBeNull();
    expect(screen.queryByLabelText("Срок +N дней")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: new RegExp(ADVANCED_PLANNING_TITLE) }));

    expect(screen.getByLabelText("Создать за N дней")).toBeTruthy();
    expect(screen.getByLabelText("Срок +N дней")).toBeTruthy();
    expect(screen.getByText(CREATE_OFFSET_DAYS_HINT)).toBeTruthy();
    expect(screen.getByText(DUE_OFFSET_DAYS_HINT)).toBeTruthy();
  });

  it("still submits offset values when the block stays collapsed", () => {
    const onSubmit = vi.fn();

    render(
      <TemplateForm
        mode="edit"
        initialValues={{ ...baseValues, create_offset_days: "2", due_offset_days: "3" }}
        onSubmit={onSubmit}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    fireEvent.submit(document.getElementById(TEMPLATE_FORM_ID)!);

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        create_offset_days: "2",
        due_offset_days: "3",
      }),
    );
  });

  it("does not show advanced planning block in view mode when offsets are zero", () => {
    render(
      <TemplateViewPanel
        template={{
          regular_task_id: 1,
          title: baseValues.title,
          description: baseValues.description,
          is_active: true,
          schedule_type: "weekly",
          schedule_params: { byweekday: [3], time: "10:00" },
          create_offset_days: 0,
          due_offset_days: 0,
          executor_role_id: 1,
          owner_unit_id: 10,
          owner_unit_name: "Отделение A",
        }}
        roleLabel="Роль 1"
        formatDateTime={() => "—"}
      />,
    );

    expect(screen.queryByText(ADVANCED_PLANNING_TITLE)).toBeNull();
  });

  it("shows advanced planning block in view mode when an offset is non-zero", () => {
    render(
      <TemplateViewPanel
        template={{
          regular_task_id: 1,
          title: baseValues.title,
          description: baseValues.description,
          is_active: true,
          schedule_type: "weekly",
          schedule_params: { byweekday: [3], time: "10:00" },
          create_offset_days: 2,
          due_offset_days: 0,
          executor_role_id: 1,
          owner_unit_id: 10,
          owner_unit_name: "Отделение A",
        }}
        roleLabel="Роль 1"
        formatDateTime={() => "—"}
      />,
    );

    expect(screen.getByText(ADVANCED_PLANNING_TITLE)).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText(CREATE_OFFSET_DAYS_HINT)).toBeTruthy();
  });
});

describe("Template view/edit layout consistency", () => {
  it("uses the same section titles in view and edit modes", () => {
    const { unmount } = render(
      <TemplateForm
        mode="edit"
        initialValues={baseValues}
        onSubmit={vi.fn()}
        ownerUnitOptions={ownerUnitOptions}
      />,
    );

    const editSections = ["Основные данные", "Расписание", "Параметры расписания", "Исполнитель", "Подразделение-владелец"];
    for (const title of editSections) {
      expect(screen.getByRole("heading", { name: title })).toBeTruthy();
    }

    unmount();

    render(
      <TemplateViewPanel
        template={{
          regular_task_id: 1,
          title: baseValues.title,
          description: baseValues.description,
          is_active: true,
          schedule_type: "weekly",
          schedule_params: { byweekday: [3], time: "10:00" },
          create_offset_days: 0,
          due_offset_days: 0,
          executor_role_id: 1,
          owner_unit_id: 10,
          owner_unit_name: "Отделение A",
        }}
        roleLabel="Роль 1"
        formatDateTime={() => "—"}
      />,
    );

    for (const title of editSections) {
      expect(screen.getByRole("heading", { name: title })).toBeTruthy();
    }
  });
});

describe("Template edit drawer header actions", () => {
  it("renders save in the header and only one close button in the header", () => {
    render(
      <TemplateDrawer
        open
        title="Редактирование шаблона"
        onClose={vi.fn()}
        headerActions={
          <button type="submit" form={TEMPLATE_FORM_ID}>
            Сохранить
          </button>
        }
      >
        <TemplateForm
          mode="edit"
          initialValues={baseValues}
          onSubmit={vi.fn()}
          ownerUnitOptions={ownerUnitOptions}
        />
      </TemplateDrawer>,
    );

    const dialog = screen.getByRole("dialog");
    const header = dialog.querySelector(".border-b");

    expect(header).toBeTruthy();
    expect(within(header as HTMLElement).getAllByRole("button", { name: "Закрыть" })).toHaveLength(1);
    expect(within(header as HTMLElement).getByRole("button", { name: "Сохранить" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Сохранение..." })).toBeNull();
  });
});
