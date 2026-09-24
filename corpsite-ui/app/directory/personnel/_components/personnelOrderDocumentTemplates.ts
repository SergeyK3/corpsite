import type {
  PersonnelOrderDetailResponse,
  PersonnelOrderEditorialState,
  PersonnelOrderItem,
} from "../_lib/personnelOrdersApi.client";
import { russianEmployeeForOrder, russianOrderAssignment } from "../_lib/personnelOrderRussianWording";

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

export const APPROVED_PERSONNEL_ORDER_TEMPLATE_VERSIONS = {
  "personnel.hire.standard": { kk: 1, ru: 1 },
  "personnel.transfer.permanent": { kk: 1, ru: 1 },
  "personnel.concurrent-duty.start": { kk: 1, ru: 1 },
  "personnel.termination.employee-initiative-unused-leave": { kk: 1, ru: 1 },
  "personnel.transfer.permanent-with-concurrent-duty": { kk: 1, ru: 1 },
} as const;

export type ApprovedPersonnelOrderTemplateKey = keyof typeof APPROVED_PERSONNEL_ORDER_TEMPLATE_VERSIONS;

/** Approved title pairs are selected by action type, never by an order number. */
export const PERSONNEL_ORDER_TITLE_DICTIONARY = {
  HIRE: { kk: "Жұмысқа қабылдау туралы", ru: "О приёме на работу" },
  TRANSFER: { kk: "Ауыстыру туралы", ru: "О переводе" },
  CONCURRENT_DUTY_START: { kk: "Қоса атқару туралы", ru: "О совмещении должностей" },
  TERMINATION: { kk: "Еңбек шартын бұзу туралы", ru: "О расторжении трудового договора" },
  TRANSFER_WITH_CONCURRENT_DUTY: { kk: "Ауыстыру туралы", ru: "О переводе и совмещении должностей" },
} as const;

// Runtime projection of the existing bilingual position and unit dictionaries.
const POSITION_KK_BY_RU: Record<string, string> = {
  "медсестра": "мейіргер", "медицинская сестра": "мейіргер", "врач": "дәрігер",
  "санитар": "санитар", "сестра хозяйка": "шаруашылық мейіргері",
};
const UNIT_KK_BY_RU: Record<string, string> = {
  "химиотерапия 1": "№1 химиялық терапия бөлімшесі", "химиотерапия 2": "№2 химиялық терапия бөлімшесі",
  "цсо": "Залалсыздандыру орталығы", "диспансер": "Диспансер бөлімшесі",
  "реанимация": "Жансақтау бөлімі", "лучевая диагностика": "Сәулелік диагностика бөлімшесі",
  "инсультный": "Инсульт орталығы", "приемное": "Қабылдау бөлімшесі",
};
const POSITION_RU_BY_KK: Record<string, string> = {
  "мейіргер": "Медицинская сестра", "күндізгі мейіргері": "Медицинская сестра",
};
const POSITION_RU_BY_SOURCE: Record<string, string> = {
  "медсестра": "медицинская сестра",
};
const UNIT_RU_BY_KK: Record<string, string> = {
  "қабылдау бөлімшесі": "Приемное",
};

function isApprovedTemplateKey(value: unknown): value is ApprovedPersonnelOrderTemplateKey {
  return typeof value === "string" && value in APPROVED_PERSONNEL_ORDER_TEMPLATE_VERSIONS;
}

function titleFor(key: ApprovedPersonnelOrderTemplateKey, language: PersonnelOrderDocumentLanguage): string {
  const code = ({
    "personnel.hire.standard": "HIRE",
    "personnel.transfer.permanent": "TRANSFER",
    "personnel.concurrent-duty.start": "CONCURRENT_DUTY_START",
    "personnel.termination.employee-initiative-unused-leave": "TERMINATION",
    "personnel.transfer.permanent-with-concurrent-duty": "TRANSFER_WITH_CONCURRENT_DUTY",
  } as const)[key];
  return PERSONNEL_ORDER_TITLE_DICTIONARY[code][language];
}

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

function dictionaryValue(
  value: unknown,
  language: PersonnelOrderDocumentLanguage,
  dictionary: Record<string, string>,
  reverseDictionary: Record<string, string> = {},
): string | null {
  const preferred = localized(value, language);
  if (language !== "kk") {
    if (preferred) return preferred;
    const source = localized(value, "kk");
    return source ? reverseDictionary[source.toLocaleLowerCase("kk-KZ").trim()] || source : null;
  }
  const source = preferred || localized(value, "ru");
  if (!source) return null;
  return dictionary[source.toLocaleLowerCase("ru-RU").trim()] || source;
}

function payload(item: PersonnelOrderItem): Record<string, unknown> {
  return record(item.payload);
}

function employeeName(item: PersonnelOrderItem): string {
  const employee = record(payload(item).employee);
  return text(item.employee_name)
    || text(record(employee.name).canonical)
    || text(payload(item).source_employee_name)
    || "—";
}

function assignment(value: unknown, language: PersonnelOrderDocumentLanguage): {
  unit: string;
  position: string;
  rate: string;
} {
  const source = record(value);
  const positionOverride = text(record(source.position_text_override)[language]);
  const sourceRuPosition = localized(source.position, "ru");
  const dictionaryPosition = language === "ru" && sourceRuPosition
    ? POSITION_RU_BY_SOURCE[sourceRuPosition.toLocaleLowerCase("ru-RU").trim()] || sourceRuPosition
    : dictionaryValue(source.position, language, POSITION_KK_BY_RU, POSITION_RU_BY_KK);
  return {
    unit: dictionaryValue(source.unit, language, UNIT_KK_BY_RU, UNIT_RU_BY_KK) || "—",
    position: positionOverride || dictionaryPosition || "—",
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

export function renderPersonnelOrderDocument(
  detail: PersonnelOrderDetailResponse,
  language: PersonnelOrderDocumentLanguage,
  editorial?: PersonnelOrderEditorialState | null,
): RenderedOrderDocument | null {
  if (!detail.items.length) return null;
  const templateKey = resolvePersonnelOrderTemplateKey(detail);
  if (!templateKey) return null;
  const rendered = templateKey === "personnel.hire.standard" ? hireForLanguage(detail, language)
    : templateKey === "personnel.transfer.permanent" ? transferForLanguage(detail, language)
      : templateKey === "personnel.concurrent-duty.start" ? concurrentDutyForLanguage(detail, language)
        : templateKey === "personnel.termination.employee-initiative-unused-leave" ? terminationByEmployeeInitiativeForLanguage(detail, language)
          : permanentTransferWithConcurrentDutyForLanguage(detail, language);
  const manualBlockText = (block: { override_text?: string | null; generated_text?: string | null; effective_text?: string | null } | undefined) =>
    block?.override_text?.trim() || (!block?.generated_text?.trim() ? block?.effective_text?.trim() : null) || null;
  const orderBlockOverride = (blockType: string) => manualBlockText(editorial?.order_blocks.find(
    (block) => block.block_type === blockType && block.locale === language,
  ));
  const items = detail.items.filter((item) => String(item.item_status).toUpperCase() !== "VOIDED");
  const points = rendered.points.map((point, index) => {
    const item = items[index];
    const group = editorial?.items.find((entry) => entry.order_item_id === item?.item_id);
    const body = manualBlockText(group?.blocks.find((block) => block.block_type === "body" && block.locale === language));
    const basis = manualBlockText(group?.blocks.find((block) => block.block_type === "basis" && block.locale === language));
    return { ...point, text: body || point.text, basis: basis ? [basis] : point.basis };
  });
  const closing = orderBlockOverride("closing");
  return {
    ...rendered,
    // Generated editorial snapshots are diagnostic/editing material.  The
    // approved bilingual renderer remains the automatic source of truth.
    title: orderBlockOverride("title") || titleFor(templateKey, language),
    preamble: orderBlockOverride("preamble") || rendered.preamble,
    points,
    additionalInstructions: closing ? [...rendered.additionalInstructions, closing] : rendered.additionalInstructions,
  };
}

/** Resolve only catalogued approved templates.  Order number is deliberately absent. */
export function resolvePersonnelOrderTemplateKey(
  detail: PersonnelOrderDetailResponse,
): ApprovedPersonnelOrderTemplateKey | null {
  const saved = record(detail.order.storage_json).template_key;
  if (isApprovedTemplateKey(saved)) return saved;
  const types = new Set(detail.items.map((item) => String(item.item_type_code).toUpperCase()));
  if (types.has("TRANSFER") && types.has("CONCURRENT_DUTY_START")) {
    return "personnel.transfer.permanent-with-concurrent-duty";
  }
  if (types.size === 1) {
    const [type] = [...types];
    return ({
      HIRE: "personnel.hire.standard",
      TRANSFER: "personnel.transfer.permanent",
      CONCURRENT_DUTY_START: "personnel.concurrent-duty.start",
      TERMINATION: "personnel.termination.employee-initiative-unused-leave",
    } as Record<string, ApprovedPersonnelOrderTemplateKey | undefined>)[type] || null;
  }
  return ({
    HIRE: "personnel.hire.standard",
    TRANSFER: "personnel.transfer.permanent",
    CONCURRENT_DUTY_START: "personnel.concurrent-duty.start",
    TERMINATION: "personnel.termination.employee-initiative-unused-leave",
  } as Record<string, ApprovedPersonnelOrderTemplateKey | undefined>)[String(detail.order.order_type_code).toUpperCase()] || null;
}

function primaryItem(detail: PersonnelOrderDetailResponse, type: string): PersonnelOrderItem {
  return detail.items.find((item) => String(item.item_type_code).toUpperCase() === type) || detail.items[0]!;
}

function assignmentForItem(item: PersonnelOrderItem, language: PersonnelOrderDocumentLanguage) {
  const source = payload(item);
  const target = record(source.to_assignment || source.assignment);
  // The editor keeps the wording override on the item payload.  Preserve the
  // structured assignment as-is and project that wording only while rendering.
  return assignment({ ...target, position_text_override: source.position_text_override || target.position_text_override }, language);
}

function russianOrderEmployee(name: string, action: "hire" | "transfer" | "concurrent"): string | null {
  const sourceName = russianEmployeeForOrder(name);
  if (!sourceName) return null;
  return action === "concurrent" ? `сотруднику ${sourceName}` : `сотрудника ${sourceName}`;
}

function russianOrderTarget(target: { position: string; unit: string }): string {
  return russianOrderAssignment(target.position, target.unit);
}

function standardDocument(
  key: ApprovedPersonnelOrderTemplateKey,
  language: PersonnelOrderDocumentLanguage,
  title: Record<PersonnelOrderDocumentLanguage, string>,
  preamble: Record<PersonnelOrderDocumentLanguage, string>,
  point: string,
  basis: string[],
): RenderedOrderDocument {
  return { templateKey: key, templateVersion: APPROVED_PERSONNEL_ORDER_TEMPLATE_VERSIONS[key][language], title: title[language], preamble: preamble[language], directive: language === "kk" ? "БҰЙЫРАМЫН:" : "ПРИКАЗЫВАЮ:", points: [{ text: point, basis }], additionalInstructions: [] };
}

function hireForLanguage(detail: PersonnelOrderDetailResponse, language: PersonnelOrderDocumentLanguage): RenderedOrderDocument {
  const item = primaryItem(detail, "HIRE"); const target = assignmentForItem(item, language); const name = employeeName(item); const when = effectiveDate(item.effective_date, language);
  const russianEmployee = russianOrderEmployee(name, "hire");
  const russianPoint = russianEmployee
    ? `Принять ${russianEmployee} с ${when} на должность ${russianOrderTarget(target)} с оплатой ${target.rate} ставки.`
    : `Принять ${name} с ${when} на должность ${target.position} ${target.unit} с оплатой ${target.rate} ставки.`;
  return standardDocument("personnel.hire.standard", language, { kk: "Жұмысқа қабылдау туралы", ru: "О приеме на работу" }, { kk: "Қазақстан Республикасының Еңбек кодексіне сәйкес", ru: "В соответствии с Трудовым кодексом Республики Казахстан" }, language === "kk" ? `${name} ${when} бастап ${target.unit} ${target.position} лауазымына ${target.rate} мөлшерлемемен жұмысқа қабылдансын.` : russianPoint, renderBasis(detail, item, language));
}

function transferForLanguage(detail: PersonnelOrderDetailResponse, language: PersonnelOrderDocumentLanguage): RenderedOrderDocument {
  const item = primaryItem(detail, "TRANSFER"); const target = assignmentForItem(item, language); const name = employeeName(item); const when = effectiveDate(item.effective_date, language);
  const russianEmployee = russianOrderEmployee(name, "transfer");
  const russianPoint = russianEmployee
    ? `Перевести ${russianEmployee} с ${when} на должность ${russianOrderTarget(target)} с оплатой ${target.rate} ставки.`
    : `Перевести ${name} с ${when} на должность ${target.position} ${target.unit} с оплатой ${target.rate} ставки.`;
  return standardDocument("personnel.transfer.permanent", language, { kk: "Ауыстыру туралы", ru: "О постоянном переводе" }, { kk: "Қазақстан Республикасының Еңбек кодексінің 38-бабына сәйкес", ru: "В соответствии со статьей 38 Трудового кодекса Республики Казахстан" }, language === "kk" ? `${name} ${when} бастап ${target.unit} ${target.position} лауазымына ${target.rate} мөлшерлемемен ауыстырылсын.` : russianPoint, renderBasis(detail, item, language));
}

function concurrentDutyForLanguage(detail: PersonnelOrderDetailResponse, language: PersonnelOrderDocumentLanguage): RenderedOrderDocument {
  const item = primaryItem(detail, "CONCURRENT_DUTY_START"); const target = assignmentForItem(item, language); const name = employeeName(item); const when = effectiveDate(item.effective_date, language);
  const russianEmployee = russianOrderEmployee(name, "concurrent");
  const russianPoint = russianEmployee
    ? `Разрешить ${russianEmployee} с ${when} совмещение обязанностей по должности ${russianOrderTarget(target)} с оплатой ${target.rate} ставки.`
    : `Разрешить ${name} с ${when} совмещение обязанностей по должности ${target.position} ${target.unit} с оплатой ${target.rate} ставки.`;
  return standardDocument("personnel.concurrent-duty.start", language, { kk: "Қоса атқару туралы", ru: "О совмещении обязанностей" }, { kk: "Қазақстан Республикасының Еңбек кодексінің 111-бабына сәйкес", ru: "В соответствии со статьей 111 Трудового кодекса Республики Казахстан" }, language === "kk" ? `${name} ${when} бастап ${target.unit} ${target.position} міндеттерін ${target.rate} мөлшерлемемен қоса атқаруға рұқсат берілсін.` : russianPoint, renderBasis(detail, item, language));
}

function permanentTransferWithConcurrentDutyForLanguage(detail: PersonnelOrderDetailResponse, language: PersonnelOrderDocumentLanguage): RenderedOrderDocument {
  const transfer = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "TRANSFER")!;
  const concurrent = detail.items.find((item) => String(item.item_type_code).toUpperCase() === "CONCURRENT_DUTY_START")!;
  const name = employeeName(transfer);
  const target = assignmentForItem(transfer, language);
  const concurrentAssignment = assignmentForItem(concurrent, language);
  const date = effectiveDate(transfer.effective_date || concurrent.effective_date, language);
  const russianPoint = russianEmployeeForOrder(name)
    ? `Перевести сотрудника ${name} с ${date} на должность ${russianOrderTarget(target)} с оплатой ${target.rate} ставки и разрешить сотруднику ${name} совмещение обязанностей по должности ${russianOrderTarget(concurrentAssignment)} с оплатой ${concurrentAssignment.rate} ставки.`
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
  const unusedLeaveDays = scalarText(payload(termination).unused_leave_days);
  const russianLeaveInstruction = unusedLeaveDays
    ? `Бухгалтерии произвести расчёт за ${unusedLeaveDays} календарных дней неиспользованного отпуска.`
    : "Бухгалтерии произвести расчёт за неиспользованные дни отпуска.";
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
      text: language === "kk" ? `Бухгалтерлік есеп бөлімі пайдаланылмаған еңбек демалысының ${unusedLeaveDays || "—"} күнтізбелік күніне есеп айырысу жүргізсін.` : russianLeaveInstruction,
      basis: [],
    }],
    additionalInstructions: [],
  };
}
