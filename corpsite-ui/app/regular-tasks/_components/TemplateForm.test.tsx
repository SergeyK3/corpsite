import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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

  it("submits schedule_type=monthly when monthly is selected", async () => {
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

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        schedule_type: "monthly",
        schedule_params: baseValues.schedule_params,
      }),
    );
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
