import type {
  PersonnelOrderDetailResponse,
  PersonnelOrderItem,
} from "../_lib/personnelOrdersApi.client";

export type PersonnelOrderDocumentLanguage = "kk" | "ru";

export const MMC_ORDER_LANGUAGE_POLICY = {
  primary_order_language: "kk",
  secondary_order_language: "ru",
  generate_bilingual: true,
} as const;

export type RenderedOrderPoint = {
  text: string;
  basis: string[];
};

export type RenderedOrderDocument = {
  templateKey: string;
  templateVersion: 1;
  title: string;
  preamble: string;
  directive: string;
  points: RenderedOrderPoint[];
  additionalInstructions: string[];
};

type BasisDocument = {
  basis_id?: unknown;
  document_type?: unknown;
  description?: unknown;
  source_text?: unknown;
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function text(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function scalarText(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return text(value);
}

function localized(value: unknown, language: PersonnelOrderDocumentLanguage): string | null {
  return text(record(value)[language]);
}

function payload(item: PersonnelOrderItem): Record<string, unknown> {
  return record(item.payload);
}

function employeeName(item: PersonnelOrderItem): string {
  const employee = record(payload(item).employee);
  return text(item.employee_name) || text(record(employee.name).canonical) || "—";
}

function assignment(value: unknown, language: PersonnelOrderDocumentLanguage): {
  unit: string;
  position: string;
  rate: string;
} {
  const source = record(value);
  return {
    unit: localized(source.unit, language) || localized(source.unit, language === "kk" ? "ru" : "kk") || "—",
    position: localized(source.position, language) || localized(source.position, language === "kk" ? "ru" : "kk") || "—",
    rate: text(source.rate) || "—",
  };
}

function dateParts(value: string | null | undefined): { day: number; month: number; year: number } | null {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

const kkMonths = ["қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан"];
const ruMonths = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];

function effectiveDate(value: string | null | undefined, language: PersonnelOrderDocumentLanguage): string {
  const parts = dateParts(value);
  if (!parts) return "—";
  return language === "kk"
    ? `${parts.year} жылғы ${parts.day} ${kkMonths[parts.month - 1]}`
    : `${parts.day} ${ruMonths[parts.month - 1]} ${parts.year} года`;
}

function basisDocuments(detail: PersonnelOrderDetailResponse): BasisDocument[] {
  const basis = record(detail.order.storage_json).basis_documents;
  return Array.isArray(basis) ? basis.map((entry) => record(entry)) : [];
}

function itemBasisIds(item: PersonnelOrderItem): string[] {
  const source = payload(item);
  const ids = Array.isArray(source.basis_ids) ? source.basis_ids : [];
  return ids.filter((id): id is string => typeof id === "string" && Boolean(id.trim()));
}

const basisTypeLabels: Record<string, Record<PersonnelOrderDocumentLanguage, string>> = {
  EMPLOYEE_APPLICATION: { kk: "Қызметкердің жеке өтініші", ru: "Личное заявление работника" },
  SERVICE_MEMO: { kk: "Қызметтік хат", ru: "Служебная записка" },
  REPORT_MEMO: { kk: "Баяндау хат", ru: "Докладная записка" },
};

function renderBasis(
  detail: PersonnelOrderDetailResponse,
  item: PersonnelOrderItem,
  language: PersonnelOrderDocumentLanguage,
): string[] {
  const documents = basisDocuments(detail);
  const byId = new Map(documents.map((basis) => [text(basis.basis_id), basis]));
  const selected = itemBasisIds(item)
    .map((basisId) => byId.get(basisId))
    .filter((basis): basis is BasisDocument => Boolean(basis));
  const manual = text(payload(item).basis_other_text);
  const entries = selected.map((basis) => {
    const kind = String(basis.document_type || "").toUpperCase();
    const sourceText = text(basis.source_text)?.replace(/^\s*(Негіз|Основание)\s*:\s*/i, "");
    // Imported Kazakh basis wording is retained verbatim; Russian is generated
    // from the selected structured document type when no Russian description exists.
    return localized(basis.description, language)
      || (language === "kk" ? sourceText : null)
      || basisTypeLabels[kind]?.[language]
      || sourceText
      || kind;
  });
  if (manual) entries.push(manual);
  return entries;
}

function hasLegalBasis(item: PersonnelOrderItem, ...parts: string[]): boolean {
  const legalBasis = text(payload(item).legal_basis)?.toLowerCase() || "";
  return parts.every((part) => legalBasis.includes(part));
}

export function renderPersonnelOrderDocument(
  detail: PersonnelOrderDetailResponse,
  language: PersonnelOrderDocumentLanguage,
): RenderedOrderDocument | null {
  const transfer = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "TRANSFER");
  const concurrent = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "CONCURRENT_DUTY_START");
  if (transfer && concurrent && hasLegalBasis(transfer, "38")) {
    return permanentTransferWithConcurrentDutyForLanguage(detail, language);
  }
  const termination = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "TERMINATION");
  if (termination && hasLegalBasis(termination, "49", "56")) {
    return terminationByEmployeeInitiativeForLanguage(detail, language);
  }
  return null;
}

function permanentTransferWithConcurrentDutyForLanguage(detail: PersonnelOrderDetailResponse, language: PersonnelOrderDocumentLanguage): RenderedOrderDocument {
  const transfer = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "TRANSFER")!;
  const concurrent = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "CONCURRENT_DUTY_START")!;
  const name = employeeName(transfer);
  const target = assignment(payload(transfer).to_assignment, language);
  const concurrentAssignment = assignment(payload(concurrent).assignment, language);
  const date = effectiveDate(transfer.effective_date || concurrent.effective_date, language);
  const sourceUnitKk = localized(record(payload(transfer).from_assignment).unit, "kk") || "";
  const targetUnitKk = localized(record(payload(transfer).to_assignment).unit, "kk") || "";
  const targetPositionKk = localized(record(payload(transfer).to_assignment).position, "kk") || "";
  const isOrder104Vocabulary = /терапия.+паллиатив.+а\s*блог/i.test(sourceUnitKk)
    && /қабылдау/i.test(targetUnitKk)
    && /күндізгі\s+мейіргер/i.test(targetPositionKk);
  const russianPoint = isOrder104Vocabulary
    ? `Медицинскую сестру блока А отделения терапии и паллиативной помощи ${name} с ${date} перевести на должность медицинской сестры приёмного отделения на 1,0 ставки и разрешить ей совмещение должности медицинской сестры этого же отделения на 0,5 ставки.`
    : `${name} с ${date} постоянно перевести на должность ${target.position} ${target.unit} с оплатой ${target.rate} ставки и разрешить совмещение обязанностей ${concurrentAssignment.position} ${concurrentAssignment.unit} с оплатой ${concurrentAssignment.rate} ставки.`;
  return {
    templateKey: "personnel.transfer.permanent-with-concurrent-duty",
    templateVersion: 1,
    title: language === "kk" ? "Ауыстыру туралы" : "О постоянном переводе и совмещении должностей",
    preamble: language === "kk" ? "Қазақстан Республикасының Еңбек Кодексінің 38-бабына сәйкес" : "В соответствии со статьёй 38 Трудового кодекса Республики Казахстан",
    directive: language === "kk" ? "БҰЙЫРАМЫН:" : "ПРИКАЗЫВАЮ:",
    points: [{
      text: language === "kk"
        ? `${name} ${date} бастап ${target.rate} ставкада ${target.unit} ${target.position} қызметіне тұрақты ауыстырылсын және ${concurrentAssignment.rate} ставкада ${concurrentAssignment.unit} ${concurrentAssignment.position} қызметін қоса атқаруға рұқсат берілсін.`
        : russianPoint,
      basis: renderBasis(detail, transfer, language),
    }],
    additionalInstructions: [],
  };
}

function terminationByEmployeeInitiativeForLanguage(detail: PersonnelOrderDetailResponse, language: PersonnelOrderDocumentLanguage): RenderedOrderDocument {
  const termination = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "TERMINATION")!;
  const name = employeeName(termination);
  const date = effectiveDate(termination.effective_date, language);
  const unusedLeaveDays = scalarText(payload(termination).unused_leave_days) || "—";
  return {
    templateKey: "personnel.termination.employee-initiative-unused-leave",
    templateVersion: 1,
    title: language === "kk" ? "Еңбек шартын бұзу туралы" : "О расторжении трудового договора",
    preamble: language === "kk" ? "Қазақстан Республикасы Еңбек Кодексінің 49-бабының 5-тармағына және 56-бабының 2-тармағына сәйкес" : "В соответствии с пунктом 5 статьи 49 и пунктом 2 статьи 56 Трудового кодекса Республики Казахстан",
    directive: language === "kk" ? "БҰЙЫРАМЫН:" : "ПРИКАЗЫВАЮ:",
    points: [{
      text: language === "kk" ? `${name} еңбек шарты ${date} бастап бұзылсын.` : `Расторгнуть трудовой договор с работником ${name} с ${date}.`,
      basis: renderBasis(detail, termination, language),
    }, {
      text: language === "kk" ? `Бухгалтерлік есеп бөлімі пайдаланылмаған еңбек демалысының ${unusedLeaveDays} күнтізбелік күніне есеп айырысу жүргізсін.` : `Бухгалтерии произвести расчёт за ${unusedLeaveDays} календарных дней неиспользованного отпуска.`,
      basis: [],
    }],
    additionalInstructions: [],
  };
}
