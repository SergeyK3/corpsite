import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonalCardPageClient from "./PersonalCardPageClient";

const getMyPersonalCardMock = vi.fn();
const getMyOperationalAssignmentMock = vi.fn();
const downloadMyPersonalCardPdfMock = vi.fn();
const saveMyContactsMock = vi.fn();
const saveMyForeignLanguagesMock = vi.fn();
const addMyEducationMock = vi.fn();
const addMyExternalEmploymentMock = vi.fn();
const supersedeMyExternalEmploymentMock = vi.fn();
const getMyContactsMock = vi.fn();
const getMyForeignLanguagesMock = vi.fn();

vi.mock("../_lib/selfPersonalCardApi.client", () => ({
  getMyPersonalCard: (...args: unknown[]) => getMyPersonalCardMock(...args),
  getMyOperationalAssignment: (...args: unknown[]) => getMyOperationalAssignmentMock(...args),
  saveMyContacts: (...args: unknown[]) => saveMyContactsMock(...args),
  saveMyForeignLanguages: (...args: unknown[]) => saveMyForeignLanguagesMock(...args),
  addMyEducation: (...args: unknown[]) => addMyEducationMock(...args),
  addMyExternalEmployment: (...args: unknown[]) => addMyExternalEmploymentMock(...args),
  supersedeMyExternalEmployment: (...args: unknown[]) => supersedeMyExternalEmploymentMock(...args),
  getMyContacts: (...args: unknown[]) => getMyContactsMock(...args),
  getMyForeignLanguages: (...args: unknown[]) => getMyForeignLanguagesMock(...args),
}));
vi.mock("../_lib/selfPersonCardPdfOpen.client", () => ({
  downloadMyPersonalCardPdf: () => downloadMyPersonalCardPdfMock(),
}));

afterEach(() => {
  cleanup();
  getMyPersonalCardMock.mockReset();
  getMyOperationalAssignmentMock.mockReset();
  downloadMyPersonalCardPdfMock.mockReset();
  addMyExternalEmploymentMock.mockReset();
  supersedeMyExternalEmploymentMock.mockReset();
  getMyContactsMock.mockReset(); getMyForeignLanguagesMock.mockReset();
});

const readyResponse = {
  status: "READY" as const,
  card: {
    materialization: { materialized: true, lifecycle_state: "READY", hr_relationship_context: null, envelope_version: 1, created_at: null, updated_at: null },
    general: { full_name: "Иванов Иван Иванович", last_name: "Иванов", first_name: "Иван", middle_name: "Иванович", birth_date: "1990-01-01", iin: "********1234", created_at: "2026-01-01", updated_at: "2026-01-01" },
    sections: {
      "PPR-EDUCATION": { section_code: "PPR-EDUCATION", active: [{ education_kind: "masters", institution_type: "university", institution_name: "КазНУ", specialty: "Экономика", qualification: "Магистр", started_at: "2018-09-01", completed_at: "2020-06-30", diploma_number: "Д-42", document_date: "2020-07-15" }], superseded: [], voided: [] },
      "PPR-EMPLOYMENT-BIOGRAPHY": { section_code: "PPR-EMPLOYMENT-BIOGRAPHY", active: [{ record_id: 77, updated_at: "2026-01-02T03:04:05+00:00", record_kind: "episode", employer_name: "АО Пример", department_name: "Финансы", position_title: "Аналитик", employment_type: "full_time", started_at: "2021-02-01", ended_at: "2024-12-31", termination_reason: "По собственному желанию" }], superseded: [], voided: [] },
    },
    additional: { foreign_languages: [{ language: "Казахский", proficiency: "C1" }], foreign_languages_none: false, awards: [], awards_none: true, academic_degrees: [], academic_degrees_none: true, academic_titles: [], academic_titles_none: true, status_facts: [] },
  },
};

const readyAssignmentResponse = {
  status: "READY" as const,
  operational_assignment: {
    department_group_name: "Administration",
    org_unit_name: "Human resources",
    position_name: "Specialist",
    operational_status: "active",
    employment_rate: 1,
    iin: "990101123456",
  },
};

describe("PersonalCardPageClient", () => {
  it("loads the self card without accepting or displaying subject IDs", async () => {
    getMyPersonalCardMock.mockResolvedValue(readyResponse);
    getMyOperationalAssignmentMock.mockResolvedValue(readyAssignmentResponse);
    getMyContactsMock.mockResolvedValue({ canonical: null, fallback: null }); getMyForeignLanguagesMock.mockResolvedValue({ foreign_languages: [], updated_at: null });
    render(<PersonalCardPageClient />);

    await waitFor(() => expect(screen.getByTestId("self-personal-card-ready")).toBeInTheDocument());
    expect(getMyPersonalCardMock).toHaveBeenCalledWith({ signal: expect.any(AbortSignal) });
    expect(getMyOperationalAssignmentMock).toHaveBeenCalledWith({ signal: expect.any(AbortSignal) });
    expect(screen.getByText("Иванов Иван Иванович")).toBeInTheDocument();
    expect(screen.getByTestId("self-personal-card-download-pdf")).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(6);
    expect(screen.queryByTestId("self-contacts-editor")).not.toBeInTheDocument();
    expect(screen.queryByTestId("self-education-editor")).not.toBeInTheDocument();
    expect(screen.queryByTestId("self-languages-editor")).not.toBeInTheDocument();
    expect(screen.queryByText(/person_id|employee_id/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("self-operational-assignment")).toHaveTextContent("Human resources");
    expect(screen.getByTestId("self-operational-assignment")).toHaveTextContent("Specialist");
    expect(screen.getByTestId("self-operational-assignment")).toHaveTextContent("Работает");
    expect(screen.getByTestId("self-operational-assignment")).toHaveTextContent("1.00");
    expect(screen.getByTestId("self-operational-assignment")).not.toHaveTextContent("active");
    expect(screen.getByText("990101123456")).toBeInTheDocument();
  });

  it("renders one styled editor inside its selected tab and keeps education heading single", async () => {
    getMyPersonalCardMock.mockResolvedValue(readyResponse);
    getMyOperationalAssignmentMock.mockResolvedValue(readyAssignmentResponse);
    getMyContactsMock.mockResolvedValue({ canonical: null, fallback: null }); getMyForeignLanguagesMock.mockResolvedValue({ foreign_languages: [], updated_at: null });
    render(<PersonalCardPageClient />);

    await screen.findByTestId("self-personal-card-ready");
    fireEvent.click(screen.getByRole("tab", { name: "Контакты" }));
    const contacts = screen.getByTestId("self-contacts-editor");
    expect(contacts).toHaveClass("rounded-xl", "border", "p-4");
    expect(screen.queryByTestId("self-education-editor")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    const mobile = screen.getByLabelText("Мобильный телефон");
    expect(mobile).toHaveClass("h-11", "w-full", "border", "border-zinc-300");
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Адрес регистрации")).toBeInTheDocument();
    expect(screen.getByLabelText("Адрес проживания")).toBeInTheDocument();
    fireEvent.change(mobile, { target: { value: "+77001234567" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Есть несохранённые изменения");
    expect(screen.getByRole("button", { name: "Сохранить" })).toHaveClass("bg-blue-600");
    expect(screen.getByRole("button", { name: "Отмена" })).toHaveClass("border");

    fireEvent.click(screen.getByRole("tab", { name: "Образование" }));
    expect(screen.getByTestId("self-education-editor")).toBeInTheDocument();
    expect(screen.queryByTestId("self-contacts-editor")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Образование" })).toHaveLength(1);
  });

  it("shows all saved education and employment fields before editing", async () => {
    getMyPersonalCardMock.mockResolvedValue(readyResponse);
    getMyOperationalAssignmentMock.mockResolvedValue(readyAssignmentResponse);
    render(<PersonalCardPageClient />);

    await screen.findByTestId("self-personal-card-ready");
    fireEvent.click(screen.getByRole("tab", { name: "Образование" }));
    const education = screen.getByTestId("self-education-records");
    expect(education).toHaveTextContent("Вид образования");
    expect(education).toHaveTextContent("Магистратура");
    expect(education).toHaveTextContent("Тип учреждения");
    expect(education).toHaveTextContent("ВУЗ");
    expect(education).toHaveTextContent("КазНУ");
    expect(education).toHaveTextContent("Экономика");
    expect(education).toHaveTextContent("Магистр");
    expect(education).toHaveTextContent("01.09.2018");
    expect(education).toHaveTextContent("30.06.2020");
    expect(education).toHaveTextContent("Д-42");
    expect(education).toHaveTextContent("15.07.2020");

    fireEvent.click(screen.getByRole("tab", { name: "Трудовая биография" }));
    const employment = screen.getByTestId("self-employment-records");
    expect(employment).toHaveTextContent("АО Пример");
    expect(employment).not.toHaveTextContent("Финансы");
    expect(employment).toHaveTextContent("Аналитик");
    expect(employment).toHaveTextContent("01.02.2021");
    expect(employment).toHaveTextContent("31.12.2024");
    expect(employment).toHaveTextContent("По собственному желанию");
    expect(employment).not.toHaveTextContent("Финансы");
  });

  it("adds one organization separately and returns to the employment list after reload", async () => {
    getMyPersonalCardMock.mockResolvedValue(readyResponse);
    getMyOperationalAssignmentMock.mockResolvedValue(readyAssignmentResponse);
    addMyExternalEmploymentMock.mockResolvedValue({ status: "applied" });
    render(<PersonalCardPageClient />);

    await screen.findByTestId("self-personal-card-ready");
    fireEvent.click(screen.getByRole("tab", { name: "Трудовая биография" }));
    expect(screen.queryByText("Подразделение")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Трудовая биография" })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Добавить место работы" }));
    expect(screen.queryByText("Организация 1")).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "По собственному желанию" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Перевод" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Переезд в другой регион" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Другое" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "По соглашению сторон" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Сокращение" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Организация"), { target: { value: "Организация один" } });
    fireEvent.change(screen.getByLabelText("Должность"), { target: { value: "Специалист" } });
    fireEvent.change(screen.getByLabelText("Причина увольнения"), { target: { value: "other" } });
    fireEvent.change(screen.getByLabelText("Другая причина увольнения"), { target: { value: "Семейные обстоятельства" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(addMyExternalEmploymentMock).toHaveBeenCalledTimes(1));
    expect(addMyExternalEmploymentMock.mock.calls[0]?.[0]).toMatchObject({ employer_name: "Организация один", position_title: "Специалист", termination_reason: "Семейные обстоятельства" });
    expect(addMyExternalEmploymentMock.mock.calls.flat().some((value) => value && typeof value === "object" && "department_name" in value)).toBe(false);
    await waitFor(() => expect(screen.getByRole("button", { name: "Добавить место работы" })).toBeInTheDocument());
    expect(getMyPersonalCardMock).toHaveBeenCalledTimes(2);
  });

  it("supersedes a self-owned employment record from its own card without subject IDs", async () => {
    getMyPersonalCardMock.mockResolvedValue(readyResponse);
    getMyOperationalAssignmentMock.mockResolvedValue(readyAssignmentResponse);
    supersedeMyExternalEmploymentMock.mockResolvedValue({ status: "COMMITTED" });
    render(<PersonalCardPageClient />);

    await screen.findByTestId("self-personal-card-ready");
    fireEvent.click(screen.getByRole("tab", { name: "Трудовая биография" }));
    const record = screen.getByTestId("self-employment-record-77");
    fireEvent.click(within(record).getByRole("button", { name: "Редактировать" }));
    fireEvent.change(screen.getByLabelText("Должность"), { target: { value: "Старший аналитик" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(supersedeMyExternalEmploymentMock).toHaveBeenCalledTimes(1));
    const [recordId, payload, commandId] = supersedeMyExternalEmploymentMock.mock.calls[0] ?? [];
    expect(recordId).toBe(77);
    expect(payload).toMatchObject({
      expected_updated_at: "2026-01-02T03:04:05+00:00",
      replacement: { record_kind: "episode", employer_name: "АО Пример", position_title: "Старший аналитик" },
    });
    expect(commandId).toEqual(expect.stringMatching(/^self-employment-/));
    expect(JSON.stringify(payload)).not.toMatch(/person_id|employee_id/i);
    expect(record).toContainElement(within(record).getByRole("button", { name: "Редактировать" }));
  });

  it("shows a clear HR contact state when Person is not linked", async () => {
    getMyPersonalCardMock.mockResolvedValue({ status: "PERSON_NOT_LINKED", card: null });
    render(<PersonalCardPageClient />);

    await waitFor(() => expect(screen.getByTestId("self-personal-card-person-not-linked")).toBeInTheDocument());
    expect(screen.getByText(/Обратитесь в отдел кадров/)).toBeInTheDocument();
    expect(screen.queryByTestId("self-personal-card-download-pdf")).not.toBeInTheDocument();
  });

  it("shows a safe unavailable state for other resolver states", async () => {
    getMyPersonalCardMock.mockResolvedValue({ status: "NO_EMPLOYEE_LINK", card: null });
    render(<PersonalCardPageClient />);

    await waitFor(() => expect(screen.getByTestId("self-personal-card-unavailable")).toBeInTheDocument());
    expect(screen.queryByTestId("self-personal-card-download-pdf")).not.toBeInTheDocument();
  });
});
