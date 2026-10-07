"use client";

import * as React from "react";
import { usePersonnelSectionLanguage } from "../_lib/personnelSectionLanguage";
import { PERSONNEL_ORDER_CREATE_TYPES } from "../_lib/personnelOrderLabels";
import PersonnelOrderTypeMenu from "./PersonnelOrderTypeMenu";

import {
  createManualPersonnelOrderDraft,
  getPersonnelOrderPublishedTemplateTitle,
  getPersonnelOrderPublishedVariants,
  type PersonnelPublishedTemplateVariant,
  mapPersonnelOrdersApiError,
  previewPersonnelOrderHeaderDuplicate,
  type PersonnelOrderManualDraftCreateResult,
} from "../_lib/personnelOrdersApi.client";
import { personnelOrderCanonicalTitle } from "../_lib/personnelOrderCanonicalTitles";
import { resolvePersonnelOrderDocumentForms, resolvePersonnelOrderOrgUnitForms } from "../_lib/personnelOrderDocumentForms";
import { russianEmployeeGenitiveForOrder, savedRussianEmployeeNameForm } from "../_lib/personnelOrderRussianWording";
import { calculateKazakhOrgUnitGenitive, calculateKazakhPersonForm, firstNonEmpty } from "../_lib/kazakhDocumentForms";
import {mapEmployeesResponseToSearchOptions} from "../_lib/personnelOrderEmployeeSearch";
import {recallBasis, recallEmployeePrefill} from "../_lib/personnelOrderRecallPrefill";
import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";
import type { EmployeeDTO } from "@/app/directory/employees/_lib/types";
import { loadOrgUnitSelectOptions, type OrgUnitSelectOption } from "@/lib/orgUnitsSelect";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (result: PersonnelOrderManualDraftCreateResult) => void;
  initialEmployeeId?: number | null;
  initialEmployeeQuery?: string | null;
  initialOrgUnitId?: number | null;
};

type Forms = {
  org_unit_document_genitive_kk: string;
  position_document_possessive_kk: string;
  position_document_nominative_ru: string;
  employee_full_name_dative_kk: string;
  employee_full_name_genitive_kk: string;
  employee_full_name_dative_ru: string;
  employee_full_name_genitive_ru: string;
};

const blankForms = (): Forms => ({
  org_unit_document_genitive_kk: "",
  position_document_possessive_kk: "",
  position_document_nominative_ru: "",
  employee_full_name_dative_kk: "",
  employee_full_name_genitive_kk: "",
  employee_full_name_dative_ru: "",
  employee_full_name_genitive_ru: "",
});

const inputClassName =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50";

function asText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function orgUnitDocumentText(orgUnit: EmployeeDTO["org_unit"] | OrgUnitSelectOption | null) {
  return resolvePersonnelOrderOrgUnitForms(orgUnit).org_unit_document_genitive_kk;
}

function documentForms(employee: EmployeeDTO, orgUnit = employee.org_unit): Forms {
  const record = employee as EmployeeDTO & Record<string, unknown>;
  const dictionary = resolvePersonnelOrderDocumentForms(employee.position, employee);

  return {
    org_unit_document_genitive_kk:
      orgUnitDocumentText(orgUnit),
    position_document_possessive_kk:
      dictionary.position_document_possessive_kk,
    position_document_nominative_ru:
      dictionary.position_document_nominative_ru,
    employee_full_name_dative_kk: firstNonEmpty(record.employee_full_name_dative_kk, calculateKazakhPersonForm(employee, "dative").value),
    employee_full_name_genitive_kk: firstNonEmpty(record.employee_full_name_genitive_kk, calculateKazakhPersonForm(employee, "genitive").value),
    employee_full_name_dative_ru: savedRussianEmployeeNameForm(record, "dative") || suggestedRussianNameDative(record),
    employee_full_name_genitive_ru: russianEmployeeGenitiveForOrder(record),
  };
}

function hasKazakhOrgUnitText(orgUnit: EmployeeDTO["org_unit"] | OrgUnitSelectOption | null) {
  return Boolean(orgUnitDocumentText(orgUnit));
}

function kazakhNameForm(fullName: string, form: "dative" | "genitive") {
  const [surname, ...rest] = fullName.split(/\s+/).filter(Boolean);
  if (!surname) return "";
  const vowelFinal = /[аеёиіоуыұүэюя]$/iu.test(surname);
  const suffix = form === "dative" ? (vowelFinal ? "ға" : /[қкг]$/iu.test(surname) ? "ке" : "ге") : (vowelFinal ? "ның" : /[қкг]$/iu.test(surname) ? "нің" : "дың");
  return [surname + suffix, ...rest].join(" ");
}

function russianNameDative(fullName: string) {
  const [surname, ...rest] = fullName.split(/\s+/).filter(Boolean);
  if (!surname) return "";
  const dative = /а$/iu.test(surname) ? `${surname.slice(0, -1)}ой` : /я$/iu.test(surname) ? `${surname.slice(0, -1)}е` : `${surname}у`;
  return [dative, ...rest].join(" ");
}

function structuredName(record: Record<string, unknown>) {
  const parts = [asText(record.first_name), asText(record.middle_name), asText(record.last_name)];
  if (parts.every(Boolean)) return parts as [string, string, string];
  const [last = "", first = "", middle = ""] = asText(record.fio).split(/\s+/).filter(Boolean);
  return [first, middle, last] as [string, string, string];
}

function suggestedKazakhNameForm(record: Record<string, unknown>, form: "dative" | "genitive") {
  const [first, middle, surname] = structuredName(record);
  if (!surname) return "";
  const vowel = /[аеёиіоуыұүэюя]$/iu.test(surname);
  const suffix = form === "dative" ? (vowel ? "ға" : /[қкг]$/iu.test(surname) ? "ке" : "ге") : (vowel ? "ның" : /[қкг]$/iu.test(surname) ? "нің" : "дың");
  return [first, middle, surname + suffix].filter(Boolean).join(" ");
}

function suggestedRussianNameDative(record: Record<string, unknown>) {
  const [first, middle, surname] = structuredName(record);
  const inflect = (v: string) => /а$/iu.test(v) ? `${v.slice(0, -1)}е` : /я$/iu.test(v) ? `${v.slice(0, -1)}е` : /ич$/iu.test(v) ? `${v}у` : v;
  const family = /а$/iu.test(surname) ? `${surname.slice(0, -1)}ой` : /я$/iu.test(surname) ? `${surname.slice(0, -1)}е` : `${surname}у`;
  return [family, inflect(first), inflect(middle)].filter(Boolean).join(" ");
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1 text-sm font-medium leading-5 text-zinc-800 dark:text-zinc-100">
      <span>{label}</span>
      {children}
    </label>
  );
}

function focusableElements(container: HTMLElement) {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hasAttribute("hidden"));
}

export default function PersonnelOrderCreateDialog({
  open,
  onClose,
  onCreated,
  initialEmployeeId = null,
  initialEmployeeQuery = null,
  initialOrgUnitId = null,
}: Props) {
  const { language: sectionLanguage } = usePersonnelSectionLanguage();
  const [type, setType] = React.useState("");
  const [selectedVersion, setSelectedVersion] = React.useState<number | undefined>();
  const [variants, setVariants] = React.useState<Record<string, PersonnelPublishedTemplateVariant[]>>({});
  const [variantsError, setVariantsError] = React.useState(false);
  const [variantsLoading, setVariantsLoading] = React.useState(true);
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setVariantsLoading(true); setVariantsError(false); setSelectedVersion(undefined);
    Promise.all(PERSONNEL_ORDER_CREATE_TYPES.map(async code => [code, (await getPersonnelOrderPublishedVariants(code)).items] as const))
      .then(entries => { if (!cancelled) setVariants(Object.fromEntries(entries)); })
      .catch(() => { if (!cancelled) setVariantsError(true); })
      .finally(() => { if (!cancelled) setVariantsLoading(false); });
    return () => { cancelled = true; };
  }, [open]);
  const [number, setNumber] = React.useState("");
  const [orderDate, setOrderDate] = React.useState("");
  const [locale, setLocale] = React.useState<"kk" | "ru">("kk");
  const [title, setTitle] = React.useState("");
  const [published, setPublished] = React.useState<{ kk: string; ru: string } | null>(null);
  const [publishedTitleError, setPublishedTitleError] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState(initialEmployeeQuery ?? "");
  const [employee, setEmployee] = React.useState<EmployeeDTO | null>(null);
  const [matches, setMatches] = React.useState<EmployeeDTO[]>([]);
  const [org, setOrg] = React.useState("");
  const [selectedOrgUnit, setSelectedOrgUnit] = React.useState<EmployeeDTO["org_unit"] | OrgUnitSelectOption | null>(null);
  const [orgUnitOptions, setOrgUnitOptions] = React.useState<OrgUnitSelectOption[]>([]);
  const [position, setPosition] = React.useState("");
  const [start, setStart] = React.useState("");
  const [end, setEnd] = React.useState("");
  const [effective, setEffective] = React.useState("");
  const [applicationDate, setApplicationDate] = React.useState("");
  const [applicationNumber, setApplicationNumber] = React.useState("");
  const [certificateDate, setCertificateDate] = React.useState("");
  const [certificateNumber, setCertificateNumber] = React.useState("");
  const [kk, setKk] = React.useState<Forms>(blankForms);
  const [formsExpanded, setFormsExpanded] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const searchId = React.useRef(0);
  const employeeSelectionId = React.useRef(0);
  const ruGenitiveEdited = React.useRef(false);
  const editedPositionForms = React.useRef(new Set<string>());
  const templateId = React.useRef(0);
  const dialogRef = React.useRef<HTMLElement>(null);
  const restoreFocusRef = React.useRef<HTMLElement | null>(null);

  const recall = type === "LEAVE.ANNUAL.RECALL";
  const [recallFields, setRecallFields] = React.useState({recall_position_kk: "", recall_org_unit_kk: "", basis_ru: "", basis_kk: ""});
  const [recallName,setRecallName]=React.useState("");
  const [recallCases,setRecallCases]=React.useState({ru:"",kk:""});
  const [recallCaseSuggestions,setRecallCaseSuggestions]=React.useState({ru:false,kk:false});
  const recallEdited=React.useRef(new Set<string>());
  const [selectingEmployee,setSelectingEmployee]=React.useState(false);
  const [employeeSearchError,setEmployeeSearchError]=React.useState("");
  const [employeeSearchFinished,setEmployeeSearchFinished]=React.useState(false);
  const unpaid = type === "LEAVE.UNPAID.GRANT";
  const childcare = type === "LEAVE.CHILDCARE.GRANT";
  const periodLeave = unpaid || childcare;
  const formsComplete = Object.entries(kk).every(([key, value]) => (!childcare && key === "employee_full_name_genitive_ru") || value.trim());
  const missingFormLabels = ([
    ["org_unit_document_genitive_kk", "Подразделение в тексте приказа (KK)"],
    ["position_document_possessive_kk", "Должность в тексте приказа (KK)"],
    ["position_document_nominative_ru", "Должность в тексте приказа (RU)"],
    ["employee_full_name_dative_kk", "ФИО в дательном падеже (KK)"],
    ["employee_full_name_genitive_kk", "ФИО в родительном падеже (KK)"],
    ["employee_full_name_dative_ru", "ФИО в дательном падеже (RU)"],
  ] as Array<[keyof Forms, string]>).filter(([key]) => !kk[key].trim()).map(([, label]) => label);
  const resolvedTitle = published?.[locale].trim() || personnelOrderCanonicalTitle(type, locale);
  const canSubmit = Boolean(
    !busy && !variantsLoading && !variantsError && (!selectedVersion || (published && !publishedTitleError)) &&
      type && (!recall || (recallName.trim() && org.trim() && position.trim() && Object.values(recallFields).every(value => value.trim()))) &&
      number.trim() &&
      orderDate &&
      resolvedTitle &&
      employee?.id &&
      (periodLeave ? start && end && end >= start && formsComplete : effective) &&
      (!childcare || (applicationDate && certificateDate && certificateNumber.trim())),
  );

  const requestClose = React.useCallback(() => {
    if (!busy) onClose();
  }, [busy, onClose]);

  const choose = React.useCallback(async (candidate: EmployeeDTO) => {
    const requestId = ++employeeSelectionId.current;
    ruGenitiveEdited.current = false;
    editedPositionForms.current.clear();
    if(recall){
      recallEdited.current.clear();setRecallFields({recall_position_kk:"",recall_org_unit_kk:"",basis_ru:"",basis_kk:""});
      setRecallCases({ru:"",kk:""});setRecallName(candidate.fio || "");
      setEmployee(null);setMatches([]);setQuery(candidate.fio || "");setSelectingEmployee(true);
    }
    setKk(current => ({ ...current, employee_full_name_genitive_ru: "", position_document_possessive_kk: "", position_document_nominative_ru: "", org_unit_document_genitive_kk: "" }));
    const selected = candidate.id
      ? await getEmployee(String(candidate.id)).catch(() => candidate)
      : candidate;
    if (requestId !== employeeSelectionId.current) return;
    setEmployee(selected);
    setSelectingEmployee(false);
    setQuery(selected.fio || "");
    setMatches([]);
    const hasAssignment = selected.has_current_assignment ?? Boolean(selected.active_assignment_id || (recall && selected.position && selected.org_unit));
    setOrg(hasAssignment ? selected.org_unit?.name || "" : "");
    setSelectedOrgUnit(hasAssignment ? selected.org_unit : null);
    setPosition(hasAssignment ? selected.position?.job_nameru || selected.position?.name || "" : "");
    const forms = documentForms(selected, hasAssignment ? selected.org_unit : null);
    if(recall){
      const fill=recallEmployeePrefill(selected);
      setRecallName(fill.fullName);setPosition(fill.positionRu);setOrg(fill.unitRu);
      setRecallFields(current=>({
        recall_position_kk:recallEdited.current.has('recall_position_kk')?current.recall_position_kk:fill.positionKk,
        recall_org_unit_kk:recallEdited.current.has('recall_org_unit_kk')?current.recall_org_unit_kk:fill.unitKk,
        basis_ru:recallEdited.current.has('basis_ru')?current.basis_ru:fill.basisRu,
        basis_kk:recallEdited.current.has('basis_kk')?current.basis_kk:fill.basisKk,
      }));
      setRecallCases({ru:fill.genitiveRu,kk:fill.genitiveKk});setRecallCaseSuggestions({ru:fill.suggestedRu,kk:fill.suggestedKk});
    }
    setKk(current => ({ ...forms,
      employee_full_name_genitive_ru: ruGenitiveEdited.current ? current.employee_full_name_genitive_ru : forms.employee_full_name_genitive_ru,
      position_document_possessive_kk: editedPositionForms.current.has("position_document_possessive_kk") ? current.position_document_possessive_kk : forms.position_document_possessive_kk,
      position_document_nominative_ru: editedPositionForms.current.has("position_document_nominative_ru") ? current.position_document_nominative_ru : forms.position_document_nominative_ru,
      org_unit_document_genitive_kk: editedPositionForms.current.has("org_unit_document_genitive_kk") ? current.org_unit_document_genitive_kk : forms.org_unit_document_genitive_kk,
    }));
    setFormsExpanded(!Object.entries(forms).every(([key, value]) => (!childcare && key === "employee_full_name_genitive_ru") || value.trim()));
  }, [childcare,recall]);

  React.useEffect(() => {
    if (!open || !type) return;
    let cancelled = false;
    void loadOrgUnitSelectOptions()
      .then((items) => { if (!cancelled) setOrgUnitOptions(items); })
      .catch(() => { if (!cancelled) setOrgUnitOptions([]); });
    return () => { cancelled = true; };
  }, [open, type]);

  const changeOrgUnit = React.useCallback((value: string) => {
    const unitId = Number(value);
    const next = orgUnitOptions.find((item) => item.unit_id === unitId) ?? null;
    setSelectedOrgUnit(next);
    setOrg(next?.name || "");
    setKk((current) => ({ ...current, org_unit_document_genitive_kk: orgUnitDocumentText(next) }));
    if(recall)setRecallFields(current=>({...current,recall_org_unit_kk:next?.name_kk || ""}));
  }, [orgUnitOptions,recall]);

  React.useEffect(() => {
    const id = ++templateId.current;
    if (!open || !type) {
      setPublished(null);
      setPublishedTitleError(null);
      setTitle("");
      return;
    }
    setPublished(null);
    setPublishedTitleError(null);
    setTitle("");
    void getPersonnelOrderPublishedTemplateTitle(type, ...(selectedVersion == null ? [] : [selectedVersion]))
      .then((result) => {
        if (id !== templateId.current) return;
        const titles = { kk: result.title_kk, ru: result.title_ru };
        if (!titles[locale].trim()) {
          setPublished(null);
          setPublishedTitleError("Для выбранного типа нет опубликованного шаблона на выбранном языке.");
          return;
        }
        setPublished(titles);
        setTitle(titles[locale].trim() || personnelOrderCanonicalTitle(type, locale));
      })
      .catch(() => {
        if (id !== templateId.current) return;
        setPublished(null);
        setTitle(personnelOrderCanonicalTitle(type, locale));
        setPublishedTitleError("Для выбранного типа отсутствует опубликованный шаблон: будет создан черновик без автоматического применения полного шаблона.");
      });
  }, [locale, open, type, selectedVersion]);

  React.useEffect(() => {
    setTitle(published?.[locale].trim() || personnelOrderCanonicalTitle(type, locale));
  }, [locale, published, type]);

  React.useEffect(() => {
    if (!open || !type) return;
    const trimmedQuery = query.trim();
    if (employee || selectingEmployee || trimmedQuery.length < 2) {
      searchId.current += 1;
      setEmployeeSearchFinished(false);
      setMatches([]);
      return;
    }
    const id = ++searchId.current;
    setEmployeeSearchError("");
    setEmployeeSearchFinished(false);
    setMatches([]);
    void getEmployees({
      q: trimmedQuery,
      status: "active",
      org_unit_id: initialOrgUnitId,
      limit: 10,
      offset: 0,
    })
      .then((result) => {
        if (id === searchId.current) {
          setEmployeeSearchFinished(true);
          const options=mapEmployeesResponseToSearchOptions(result,{activeOnly:true});
          const ids=new Set<number>();
          setMatches(options.filter(option=>{if(ids.has(option.employee_id))return false;ids.add(option.employee_id);return true;})
            .map(option=>result.items.find(item=>Number(item.id)===option.employee_id)!).filter(Boolean));
        }
      })
      .catch(() => {if(id===searchId.current){setEmployeeSearchFinished(true);setEmployeeSearchError("search");}});
  }, [employee, initialOrgUnitId, open, query, type,selectingEmployee]);

  React.useEffect(() => {
    if (!open || !type || !initialEmployeeId) return;
    void getEmployee(String(initialEmployeeId)).then(choose).catch(() => undefined);
  }, [choose, initialEmployeeId, open, type]);

  React.useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => dialogRef.current?.focus());

    return () => {
      document.body.style.overflow = previousOverflow;
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        requestClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const elements = focusableElements(dialogRef.current);
      if (elements.length === 0) return;
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, requestClose]);

  if (!open) return null;

  function changeType(nextType: string, versionId?: number) {
    setSelectedVersion(versionId);
    ++templateId.current;
    setType(nextType);
    setRecallFields({recall_position_kk: "", recall_org_unit_kk: "", basis_ru: "", basis_kk: ""});
    recallEdited.current.clear();setRecallCases({ru:"",kk:""});setRecallName("");
    if(nextType === 'LEAVE.ANNUAL.RECALL' && employee){
      const fill=recallEmployeePrefill(employee);setRecallName(fill.fullName);setPosition(fill.positionRu);setOrg(fill.unitRu);
      setRecallFields({recall_position_kk:fill.positionKk,recall_org_unit_kk:fill.unitKk,basis_ru:fill.basisRu,basis_kk:fill.basisKk});
      setRecallCases({ru:fill.genitiveRu,kk:fill.genitiveKk});setRecallCaseSuggestions({ru:fill.suggestedRu,kk:fill.suggestedKk});
    }
    setPublished(null);
    setPublishedTitleError(null);
    setTitle("");
    setStart("");
    setEnd("");
    setEffective("");
    setKk(blankForms());
    setFormsExpanded(Boolean(employee) && ["LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT"].includes(nextType));
    setApplicationDate(""); setApplicationNumber(""); setCertificateDate(""); setCertificateNumber("");
    setError(null);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || variantsLoading || variantsError) return;
    setError(null);
    setBusy(true);
    try {
      if (!employee?.id) throw Error("Выберите сотрудника из списка.");
      if (unpaid && (!start || !end)) throw Error("Для отпуска укажите дату начала и дату окончания.");
      if (periodLeave && end < start) throw Error("Дата окончания отпуска не может быть раньше даты начала.");
      const duplicate = await previewPersonnelOrderHeaderDuplicate({ order_number: number, order_date: orderDate });
      if (duplicate.blocking) throw Error("Найден приказ с таким же номером и датой.");
      const days = periodLeave
        ? Math.floor((Date.parse(`${end}T00:00:00`) - Date.parse(`${start}T00:00:00`)) / 86400000) + 1
        : undefined;
      const result = await createManualPersonnelOrderDraft({
        ...(selectedVersion == null ? {} : { template_version_id: selectedVersion }),
        order_number: number,
        order_date: orderDate,
        source_title: resolvedTitle,
        source_title_locale: locale,
        item_type_code: type,
        employee_id: Number(employee.id),
        document_subject_context: { org_unit_name: org || null, position_name: position || null },
        effective_date: periodLeave ? start : effective,
        period_start: periodLeave ? start : null,
        period_end: periodLeave ? end : null,
        item_payload: recall ? {...recallFields,source_employee_name:recallName} : periodLeave
          ? {
              ...(childcare ? { leave_start: start, leave_end: end, leave_days: days } : { leave: { period_type: start === end ? "SINGLE_DAY" : "CONTINUOUS_RANGE", start, end, days } }),
              document_forms_kk: {
                org_unit_document_genitive_kk: kk.org_unit_document_genitive_kk,
                position_document_possessive_kk: kk.position_document_possessive_kk,
                employee_full_name_dative_kk: kk.employee_full_name_dative_kk,
                employee_full_name_genitive_kk: kk.employee_full_name_genitive_kk,
              },
              document_forms_ru: {
                employee_full_name_dative_ru: kk.employee_full_name_dative_ru,
                ...(childcare ? { employee_full_name_genitive_ru: kk.employee_full_name_genitive_ru } : {}),
                position_document_nominative_ru: kk.position_document_nominative_ru,
              },
              assignment: { org_unit: { id: selectedOrgUnit?.unit_id || null, name: org || null }, position: { id: employee.position?.id || null, name: position || null } },
              basis: childcare ? { kind: "PERSONAL_APPLICATION", date: applicationDate, number: applicationNumber || null, birth_certificate: { date: certificateDate, number: certificateNumber } } : { kind: "PERSONAL_APPLICATION" },
            }
          : {
              document_forms_kk: { position_document_possessive_kk: kk.position_document_possessive_kk, org_unit_document_genitive_kk: kk.org_unit_document_genitive_kk, employee_full_name_dative_kk: kk.employee_full_name_dative_kk, employee_full_name_genitive_kk: kk.employee_full_name_genitive_kk },
              document_forms_ru: { position_document_nominative_ru: kk.position_document_nominative_ru, employee_full_name_dative_ru: kk.employee_full_name_dative_ru },
            },
      });
      onCreated(result);
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : mapPersonnelOrdersApiError(caught, "Не удалось создать приказ."));
    } finally {
      setBusy(false);
    }
  }

  const selectedEmployee = employee ? (
    <>
      <input type="hidden" name="employee_id" value={employee.id || ""} data-testid="selected-employee-id" />
      <input aria-label="Сотрудник" readOnly={!recall} value={recall?recallName:employee.fio || ""} onChange={event=>{
        const name=event.target.value;setRecallName(name);
        const fill=recallEmployeePrefill({fio:name} as EmployeeDTO);setRecallCases({ru:fill.genitiveRu,kk:fill.genitiveKk});
        setRecallCaseSuggestions({ru:fill.suggestedRu,kk:fill.suggestedKk});
        setRecallFields(current=>({...current,basis_ru:recallEdited.current.has('basis_ru')?current.basis_ru:fill.basisRu,basis_kk:recallEdited.current.has('basis_kk')?current.basis_kk:fill.basisKk}));
      }} className={inputClassName} />
      <button type="button" disabled={busy} className="text-sm text-blue-600" onClick={() => {
        ++employeeSelectionId.current;
        setEmployee(null); setQuery(""); setMatches([]);
        setSelectedOrgUnit(null); setOrg(""); setPosition(""); setKk(blankForms());
        setRecallName("");setRecallCases({ru:"",kk:""});setRecallFields({recall_position_kk:"",recall_org_unit_kk:"",basis_ru:"",basis_kk:""});recallEdited.current.clear();
        editedPositionForms.current.clear(); ruGenitiveEdited.current = false;
      }}>Сменить сотрудника</button>
      <Field label="Подразделение">
        {recall ? <input aria-label="Подразделение" value={org} onChange={event=>setOrg(event.target.value)} maxLength={300} className={inputClassName}/> : null}
        <select aria-label={recall?"Выбор подразделения":"Подразделение"} value={selectedOrgUnit?.unit_id ?? ""} onChange={(event) => changeOrgUnit(event.target.value)} className={inputClassName}>
          <option value="">Выберите подразделение</option>
          {selectedOrgUnit?.unit_id != null && !orgUnitOptions.some((item) => item.unit_id === selectedOrgUnit.unit_id) ? <option value={selectedOrgUnit.unit_id}>{selectedOrgUnit.name}</option> : null}
          {orgUnitOptions.map((item) => <option key={item.unit_id} value={item.unit_id}>{item.name}</option>)}
        </select>
      </Field>
      <Field label="Должность">
        {recall ? <input aria-label="Должность" value={position} onChange={event => setPosition(event.target.value)} maxLength={300} className={inputClassName} /> : <select aria-label="Должность" value={position} onChange={(event) => setPosition(event.target.value)} className={inputClassName}>
          <option value="">Выберите должность</option>
          {position ? <option value={position}>{position}</option> : null}
        </select>}
      </Field>
    </>
  ) : (
    <div className="relative z-20">
      <input aria-label="Сотрудник" value={query} disabled={selectingEmployee} onChange={(event) => setQuery(event.target.value)} className={inputClassName} />
      {selectingEmployee?<p role="status">{sectionLanguage==='kk'?'Қызметкер деректері жүктелуде…':'Загружаются данные сотрудника…'}</p>:null}
      {employeeSearchError?<p role="alert">{sectionLanguage==='kk'?'Қызметкерлерді жүктеу мүмкін болмады. Іздеуді қайталаңыз.':'Не удалось загрузить сотрудников. Повторите поиск.'}</p>:null}
      {recall && employeeSearchFinished && !employeeSearchError && matches.length===0 && query.trim().length>=2?<p role="status">{sectionLanguage==='kk'?'Қызметкерлер табылмады. Аты-жөнін немесе бөлімшені тексеріңіз.':'Сотрудники не найдены. Проверьте фамилию или подразделение.'}</p>:null}
      {matches.length > 0 ? (
        <div role="listbox" className="mt-1 overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
          {matches.map((candidate) => (
            <button
              key={candidate.id}
              type="button"
              role="option"
              data-employee-id={candidate.id}
              className="block w-full px-3 py-2 text-left text-sm text-zinc-900 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none dark:text-zinc-50 dark:hover:bg-zinc-800"
              onClick={() => void choose(candidate)}
            >
              {candidate.fio}{recall?<span className="block text-xs font-normal text-zinc-500">{candidate.org_unit?.name || (sectionLanguage==='kk'?'Бөлімше көрсетілмеген':'Подразделение не указано')}</span>:null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-zinc-700/45 p-4 backdrop-blur-[1px] dark:bg-black/65"
      data-testid="personnel-order-create-dialog"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) requestClose();
      }}
    >
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="personnel-order-create-title"
        tabIndex={-1}
        className="relative flex max-h-[calc(100vh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white text-zinc-950 shadow-2xl dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
      >
        <header data-testid="personnel-order-create-header" className="flex shrink-0 items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <h2 id="personnel-order-create-title" className="text-lg font-semibold">Создать приказ</h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Будет создан новый приказ в статусе DRAFT.</p>
          </div>
          <button type="button" aria-label="Закрыть" onClick={requestClose} disabled={busy} className="-mr-1 -mt-1 rounded-md p-2 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-zinc-800 dark:hover:text-zinc-50">×</button>
        </header>
        <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit} onKeyDown={(event) => {
          if (event.key === "Enter" && event.target instanceof HTMLInputElement && event.target.type !== "submit") event.preventDefault();
        }}>
          <div data-testid="personnel-order-create-body" className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-5 py-4">
            <PersonnelOrderTypeMenu value={type} language={sectionLanguage} onChange={changeType} variants={variants} selectedVersion={selectedVersion} disabled={variantsLoading || variantsError} />
            {variantsError ? <p role="alert">Не удалось загрузить варианты шаблонов. Откройте форму повторно.</p> : null}
            <Field label="Номер приказа"><input aria-label="Номер приказа" required value={number} onChange={(event) => setNumber(event.target.value)} className={inputClassName} /></Field>
            <Field label="Дата приказа"><input aria-label="Дата приказа" type="date" required value={orderDate} onChange={(event) => setOrderDate(event.target.value)} className={inputClassName} /></Field>
            <Field label="Язык"><select aria-label="Язык" value={locale} onChange={(event) => setLocale(event.target.value as "kk" | "ru")} className={inputClassName}><option value="kk">Қазақша</option><option value="ru">Русский</option></select></Field>
            <Field label="Название приказа"><textarea aria-label="Название приказа" readOnly value={title} placeholder={type ? "Загрузка названия…" : "Сначала выберите тип пункта"} className={`${inputClassName} min-h-20 resize-y`} /></Field>
            {publishedTitleError ? <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-100">{publishedTitleError}</p> : null}
            {type ? <>
              <div className="space-y-1 text-sm font-medium leading-5 text-zinc-800 dark:text-zinc-100"><span>Сотрудник</span>{selectedEmployee}</div>
              {periodLeave ? <>
              <Field label="Дата начала"><input aria-label="Дата начала" type="date" required value={start} onChange={(event) => { setStart(event.target.value); setEnd(event.target.value); }} className={inputClassName} /></Field>
              <Field label="Дата окончания"><input aria-label="Дата окончания" type="date" required value={end} onChange={(event) => setEnd(event.target.value)} className={inputClassName} /></Field>
              {childcare ? <>
                <Field label="Дата заявления"><input type="date" required value={applicationDate} onChange={e=>setApplicationDate(e.target.value)} className={inputClassName} /></Field>
                <Field label="Номер заявления"><input value={applicationNumber} onChange={e=>setApplicationNumber(e.target.value)} className={inputClassName} /></Field>
                <Field label="Дата выдачи свидетельства о рождении"><input type="date" required value={certificateDate} onChange={e=>setCertificateDate(e.target.value)} className={inputClassName} /></Field>
                <Field label="Номер свидетельства о рождении"><input required value={certificateNumber} onChange={e=>setCertificateNumber(e.target.value)} className={inputClassName} /></Field>
                <p className="text-xs">Дата выдачи свидетельства — не дата рождения ребёнка. Дата окончания отпуска вводится отдельно.</p>
                <Field label="ФИО сотрудника в родительном падеже (RU)"><input required value={kk.employee_full_name_genitive_ru} onChange={e=>{ ruGenitiveEdited.current = true; setKk(previous=>({...previous, employee_full_name_genitive_ru:e.target.value})); }} className={inputClassName} /></Field>
              </> : null}
              </> : <Field label="Дата действия"><input aria-label="Дата действия" type="date" required value={effective} onChange={(event) => setEffective(event.target.value)} className={inputClassName} /></Field>}
            </> : null}
              {employee && !recall ? <details open={formsExpanded} onToggle={(event) => setFormsExpanded(event.currentTarget.open)} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700" data-testid="personnel-order-text-forms">
                <summary className="cursor-pointer text-sm font-medium">{formsComplete ? "Формы для текста приказа заполнены автоматически" : "Формы для текста приказа"}</summary>
              {periodLeave && missingFormLabels.length ? <p role="alert" className="mt-2 text-sm text-amber-800">Необходимо заполнить: {missingFormLabels.join(", ")}.</p> : null}
              {!kk.position_document_possessive_kk.trim() ? <p className="text-xs text-amber-700">В справочнике должности нет казахского названия или сохранённой документной формы. Заполните КК-должность вручную.</p> : <p className="text-xs text-zinc-500">Документные формы редактируемые; рассчитанную форму из названия справочника проверьте.</p>}
              <div className="mt-3 space-y-3">{([
                ["position_document_possessive_kk", "Должность в тексте приказа (KK)"],
                ["position_document_nominative_ru", "Должность в тексте приказа (RU)"],
                ["employee_full_name_dative_kk", "ФИО сотрудника в дательном падеже (KK)"],
                ["employee_full_name_genitive_kk", "ФИО сотрудника в родительном падеже (KK)"],
                ["employee_full_name_dative_ru", "ФИО сотрудника в дательном падеже (RU)"],
              ] as Array<[keyof Forms, string]>).map(([key, label]) => <Field key={key} label={label}><input aria-label={label} value={kk[key]} onChange={(event) => { editedPositionForms.current.add(key); setKk((value) => ({ ...value, [key]: event.target.value })); }} className={inputClassName} /></Field>)}<Field label="Подразделение в тексте приказа (KK)"><input aria-label="Подразделение в тексте приказа (KK)" value={kk.org_unit_document_genitive_kk} onChange={(event) => { editedPositionForms.current.add("org_unit_document_genitive_kk"); setKk((value) => ({ ...value, org_unit_document_genitive_kk: event.target.value })); }} className={inputClassName} />{!hasKazakhOrgUnitText(selectedOrgUnit) ? <p className="text-xs font-normal text-amber-700 dark:text-amber-300">В справочнике отсутствует казахское название выбранного подразделения.</p> : null}</Field></div>
              </details>
              : null}

            {recall ? <div className="grid w-full gap-3 sm:grid-cols-2">{([['recall_position_kk',sectionLanguage === 'kk' ? 'Лауазым KZ' : 'Должность KZ'],['recall_org_unit_kk',sectionLanguage === 'kk' ? 'Бөлімше KZ' : 'Подразделение KZ'],['basis_ru','Основание RU'],['basis_kk','Негіз KZ']] as const).map(([key,label]) => <Field key={key} label={label}><input aria-label={label} value={recallFields[key]} onChange={event => { recallEdited.current.add(key); setRecallFields(current => ({...current,[key]:event.target.value})); }} className={inputClassName} /></Field>)}</div> : null}
            {recall && employee && (!position || !org || !recallFields.recall_position_kk || !recallFields.recall_org_unit_kk)?<p className="text-xs text-amber-700">{sectionLanguage==='kk'?'Қызметкер карточкасында RU/KZ деректері толық емес. Бұйрық мәтіні үшін жетіспейтін атауларды енгізіңіз.':'В карточке сотрудника нет всех данных на RU/KZ. Заполните недостающие названия для текста приказа.'}</p>:null}
            {recall && employee ? <section className="space-y-2 sm:col-span-2" data-testid="recall-name-case-fields">
              <h3 className="text-sm font-medium">{sectionLanguage==='kk'?'Негіздер үшін аты-жөнінің септік нысандары':'Падежные формы ФИО для оснований'}</h3>
              {recallCaseSuggestions.ru || recallCaseSuggestions.kk ? <p className="text-xs text-zinc-600">{sectionLanguage==='kk'?'Ұсынылған септік нысандарын тексеріңіз; оларды өзгертуге болады.':'Предложенные падежные формы проверьте; их можно уточнить.'}</p>:null}
              {(!recallCases.ru || !recallCases.kk) ? <p className="text-xs text-amber-700">{sectionLanguage==='kk'?'Қажетті септік нысаны жоқ. Оны немесе негіз мәтінін қолмен енгізіңіз.':'Нужная падежная форма не определена. Введите её или текст основания вручную.'}</p>:null}
              <div className="grid gap-3 sm:grid-cols-2">{(['ru','kk'] as const).map(locale=>{
                const label=locale==='ru'?'ФИО в родительном падеже (RU)':'Аты-жөні ілік септігінде (KZ)';
                return <Field key={locale} label={label}><input aria-label={label} value={recallCases[locale]} maxLength={300} onChange={event=>{
                  const value=event.target.value;setRecallCases(current=>({...current,[locale]:value}));
                  setRecallCaseSuggestions(current=>({...current,[locale]:false}));
                  const key=locale==='ru'?'basis_ru':'basis_kk';if(!recallEdited.current.has(key))setRecallFields(current=>({...current,[key]:recallBasis(locale,value)}));
                }} className={inputClassName}/>
                  <button type="button" disabled={!recallCases[locale].trim()} onClick={()=>{const key=locale==='ru'?'basis_ru':'basis_kk';recallEdited.current.delete(key);setRecallFields(current=>({...current,[key]:recallBasis(locale,recallCases[locale])}));}} className="text-xs text-blue-700">{sectionLanguage==='kk'?'Негізді ұсыну':'Предложить основание'} {locale==='ru'?'RU':'KZ'}</button>
                </Field>;
              })}</div>
            </section>:null}
            {error ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-200">{error}</p> : null}
          </div>
          <footer data-testid="personnel-order-create-footer" className="flex shrink-0 justify-end gap-3 border-t border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-950">
            <button type="button" onClick={requestClose} disabled={busy} className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 shadow-sm hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">Отмена</button>

            <button type="submit" disabled={!canSubmit} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-blue-300 dark:disabled:bg-blue-900">{busy ? "Создание…" : "Создать приказ"}</button>
          </footer>
        </form>
      </section>
    </div>
  );
}
