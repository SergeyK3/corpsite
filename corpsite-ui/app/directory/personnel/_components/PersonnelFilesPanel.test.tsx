import * as React from "react";
import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PersonnelFilesPanel from "./PersonnelFilesPanel";
import * as api from "../_lib/personnelFilesApi.client";
import type { PersonnelFile } from "../_lib/personnelFilesApi.client";
vi.mock("next/image", () => ({ default: () => null }));
vi.mock("../_lib/personnelFilesApi.client", async () => {
  const actual = await vi.importActual<typeof api>("../_lib/personnelFilesApi.client");
  return { ...actual, listFiles: vi.fn(), decideFile: vi.fn(), fileBlob: vi.fn(), submitFile: vi.fn(), reviewQueue: vi.fn(), classifierCatalog: vi.fn(), registryCertificates: vi.fn(), certificateComparison: vi.fn() };
});
const file: PersonnelFile = { version_id: "synthetic-version", set_id: "synthetic-set", person_id: 1, kind: "certificate", title: "Вымышленный сертификат", version_no: 1, state: "approved", revision: 2, original_name: "test.pdf", mime_type: "application/pdf", byte_size: 123, page_count: 2, reason: "", created_at: "2026-11-15T00:00:00Z", decided_at: null, proposed_name: null, name_applied_at: null, can_review: false, can_replace: false, can_export: false };
afterEach(cleanup);
beforeEach(() => { vi.clearAllMocks();
  vi.mocked(api.classifierCatalog).mockResolvedValue({can_manage:false,editions:[],entries:[],mappings:[],medical_specialties:[]});
  vi.mocked(api.registryCertificates).mockResolvedValue({items:[]});
});
describe("personnel file operations", () => {
  it("identifies approved and returned versions of the same certificate in the viewer", async () => {
    const approved = { ...file, title: "Вымышленный сертификат A", version_id: "a-v4", version_no: 4, state: "approved" as const };
    const returned = { ...file, title: "Вымышленный сертификат A", version_id: "a-v3-x", version_no: 3, state: "returned" as const, original_name: "fictional-incompatible-X.pdf" };
    vi.mocked(api.listFiles).mockResolvedValue({ items: [approved, returned], can_upload: false, can_review: false });
    vi.mocked(api.fileBlob).mockResolvedValue(new Blob(["preview"], { type: "image/png" }));
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:preview") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    render(<PersonnelFilesPanel personId={1} fullName="Тест" />);

    const approvedArticle = (await screen.findAllByRole("article"))[0];
    fireEvent.click(within(approvedArticle).getByRole("button", { name: "Просмотреть" }));
    expect(within(screen.getByRole("dialog", { name: "Просмотр файла" })).getByRole("heading", { name: "Вымышленный сертификат A · версия 4 · Одобрен" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Закрыть просмотр" }));

    fireEvent.click(screen.getByLabelText("Показывать предыдущие версии"));
    const returnedArticle = screen.getAllByRole("article")[1];
    fireEvent.click(within(returnedArticle).getByRole("button", { name: "Просмотреть" }));
    expect(within(screen.getByRole("dialog", { name: "Просмотр файла" })).getByRole("heading", { name: "Вымышленный сертификат A · версия 3 · Возвращён" })).toBeInTheDocument();
  });

  it("shows a leader previews without original download, print or approval", async () => {
    vi.mocked(api.listFiles).mockResolvedValue({ items: [file], can_upload: false, can_review: false });
    render(<PersonnelFilesPanel personId={1} fullName="Тест" />);
    expect(await screen.findByText("Вымышленный сертификат")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Просмотреть" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Скачать" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Печать" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Одобрить" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Отправить кадровику" })).toBeNull();
  });
  it("requires a return explanation and submits the exact revision", async () => {
    const pending = { ...file, state: "pending" as const, revision: 1, can_review: true };
    vi.mocked(api.listFiles).mockResolvedValue({ items: [pending], can_upload: false, can_review: true });
    vi.mocked(api.decideFile).mockResolvedValue({ ...pending, state: "returned", revision: 2 });
    render(<PersonnelFilesPanel personId={1} fullName="Тест" />);
    fireEvent.click(await screen.findByRole("button", { name: "Вернуть с пояснением" }));
    const field = screen.getByLabelText("Пояснение");
    expect(field).toBeRequired();
    fireEvent.change(field, { target: { value: "Загрузите оборотную сторону" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить решение" }));
    await waitFor(() => expect(api.decideFile).toHaveBeenCalledWith(pending, "return", "Загрузите оборотную сторону"));
  });
  it("shows owner decision notifications and the upload form", async () => {
    vi.mocked(api.listFiles).mockResolvedValue({ items: [], can_upload: true, can_review: false, notifications: [{ event_id: 5, version_id: "v", actor_id: 3, action: "return", created_at: "2026-11-15T00:00:00Z", detail: { reason: "Нечитаемый номер" } }] });
    render(<PersonnelFilesPanel personId={null} fullName="Тест" />);
    expect(await screen.findByText("Новые решения по вашим файлам")).toBeInTheDocument();
    expect(screen.getByText("Возвращён: Нечитаемый номер")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отправить кадровику" })).toBeInTheDocument();
  });
  it("shows both issued certificates and the central basis before confirmation", async () => {
    const facts = {document_id:11,certificate_entry_id:1,specialty_name_at_issue:"Исходное название А",specialty_code_at_issue:"OLD-A",classifier_edition_at_issue:"TEST-OLD",issued_at:"2025-01-01",valid_until:"2031-01-01",document_number:null,issued_by:null,lifecycle_status:"ACTIVE",verification_status:"VERIFIED"};
    const pending = {...file,state:"pending" as const,version_no:2,revision:1,can_review:true,certificate:{...facts,document_id:12,certificate_entry_id:2,specialty_name_at_issue:"Новое название А",classifier_edition_at_issue:"TEST-NEW"}};
    const comparison: api.CertificateComparison = {previous:{...file,certificate:facts},new_certificate:pending.certificate,can_approve:true,context_token:"a".repeat(64),basis:{kind:"confirmed_mapping",description:"Центральное подтверждение",source_reference:"Вымышленный протокол",mapping_id:3}};
    vi.mocked(api.listFiles).mockResolvedValue({items:[pending],can_upload:false,can_review:true});
    vi.mocked(api.certificateComparison).mockResolvedValue(comparison);
    vi.mocked(api.decideFile).mockResolvedValue({...pending,state:"approved",revision:2});
    render(<PersonnelFilesPanel personId={1} fullName="Тест" />);
    fireEvent.click(await screen.findByRole("button",{name:"Одобрить"}));
    expect(await screen.findByText("Исходное название А")).toBeInTheDocument();
    expect(screen.getByText("Источник: Вымышленный протокол")).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Просмотреть прежний сертификат"})).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Просмотреть новый сертификат"})).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button",{name:"Подтвердить решение"})).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button",{name:"Подтвердить решение"}));
    await waitFor(() => expect(api.decideFile).toHaveBeenCalledWith(pending,"approve","",comparison));
  });
});
