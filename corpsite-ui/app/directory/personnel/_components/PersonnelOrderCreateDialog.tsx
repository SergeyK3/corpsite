"use client";
import PersonnelOrderHirePositionFields from "./PersonnelOrderHirePositionFields";
import type {HirePositionManualForms} from "../_lib/personnelOrderHirePosition";

import PersonnelOrderHireDetailsFields from "./PersonnelOrderHireDetailsFields";
import {emptyHireDetails, hireDetailsPayload} from "../_lib/personnelOrderHireDetails";
import PersonnelOrderDuplicateActions from "./PersonnelOrderDuplicateActions";
import {hireTermsIssues, hireRateNumber,hasHireBasis} from "../_lib/personnelOrderHireTerms";
import {newHireBasis} from "../_lib/personnelOrderHireBasis";
import PersonnelOrderHireTermsFields from './PersonnelOrderHireTermsFields';
import PersonnelOrderHireEmployeeFields from "./PersonnelOrderHireEmployeeFields";
import {blankHireNewEmployee, hireNewEmployeeName, hireNewEmployeeError} from "../_lib/personnelOrderHireNewEmployee";
import { useCurrentUser } from "@/lib/currentUser";
import PersonnelOrderPersonalDataFields from './PersonnelOrderPersonalDataFields';
import {emptyPersonalDataDraft,refreshPersonalDataContext,personalDataErrors,personalDataOrderPayload} from '../_lib/personalDataDraft';
import PersonnelOrderEducationFields from "./PersonnelOrderEducationFields";
import {emptyEducationDraft, refreshEducationContext, educationErrors, educationOrderPayload, educationDraftFromRecord} from "../_lib/educationDraft";
import PersonnelOrderServiceLengthFields from "./PersonnelOrderServiceLengthFields";
import {emptyServiceLengthDraft, refreshServiceLengthContext, serviceLengthErrors, serviceLengthOrderPayload} from "../_lib/serviceLengthDraft";
import PersonnelOrderCategoryFields from "./PersonnelOrderCategoryFields";
import {resolvePersonnelDocumentContext,refreshCategoryDocumentContext,type PersonnelDocumentContext} from "../_lib/personnelOrderDocumentContext";
import {emptyCategoryOrderDraft as emptyCategoryDraft,categoryDraftErrors,categoryOrderPayload} from "../_lib/qualificationCategoryDraft";
import PersonnelOrderAllowancePercent from "./PersonnelOrderAllowancePercent";
import { allowancePercentError } from "../_lib/personnelOrderAllowancePercent";

import * as React from "react";
import {manualSubjectWording} from "../_lib/personnelOrderManualSubject";
import {loadTemplateWithTimeout} from "../_lib/personnelOrderTemplateLoading";
import {usePersonnelOrderEmployeeSearch} from "../_lib/usePersonnelOrderEmployeeSearch";
import {blankDepartment,departmentFromUnit,departmentValues,type DepartmentDraft} from "../_lib/personnelOrderDepartment";
import PersonnelOrderDepartmentPicker from "./PersonnelOrderDepartmentPicker";
import PersonnelOrderHireDepartmentFields from "./PersonnelOrderHireDepartmentFields";
import PersonnelOrderPositionPicker from "./PersonnelOrderPositionPicker";
import { usePersonnelOrderPositions, type DocumentPosition } from "../_lib/personnelOrderPositions";
import {concurrentEmployeeDatives} from "../_lib/personnelOrderConcurrentForms";
import { usePersonnelSectionLanguage } from "../_lib/personnelSectionLanguage";
import { PERSONNEL_ORDER_CREATE_TYPES } from "../_lib/personnelOrderLabels";
import PersonnelOrderTypeMenu from "./PersonnelOrderTypeMenu";
import PersonnelOrderReplacementFields, {blankReplacement,replacementBlockers,type ReplacementFields} from "./PersonnelOrderReplacementFields";
import PersonnelOrderTransferFields, { type TransferFields } from "./PersonnelOrderTransferFields";
import PersonnelOrderMedicalSpecialtyPicker, {type MedicalSpecialtySnapshot} from "./PersonnelOrderMedicalSpecialtyPicker";
import PersonnelOrderAllowanceRecipient,{blankAllowanceRecipient,recipientBlockers,type AllowanceRecipient} from './PersonnelOrderAllowanceRecipient';
import {russianEmployeeDativeForOrder} from '../_lib/personnelOrderRussianWording';
import {savedKazakhEmployeeNameForm} from '../_lib/personnelOrderDocumentForms';

import {
  createManualPersonnelOrderDraft, createPersonnelOrderItem,
  type PersonnelOrderDetailResponse,
  getPersonnelOrderPublishedTemplateTitle,
  getPersonnelOrderPublishedVariants,
  type PersonnelPublishedTemplateVariant,
  mapPersonnelOrdersApiError,
  previewPersonnelOrderHeaderDuplicate,
  type PersonnelOrderManualDraftCreateResult,
  type PersonnelOrderHeaderDuplicatePreview,
  PersonnelOrderDuplicateError, personnelOrderDuplicateMessage,
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
  itemContext?: {orderId: number; itemTypeCode: string; template: PersonnelPublishedTemplateVariant; employeeIds: number[];items?: PersonnelOrderDetailResponse['items']; sourceTitleLocale?: "ru" | "kk" | "unknown" | null};
  onItemAdded?: (result: PersonnelOrderDetailResponse) => void;
  initialEmployeeId?: number | null;
  initialEmployeeQuery?: string | null;
  initialOrgUnitId?: number | null;
};

type Forms = {
  employee_full_name_accusative_ru: string;
  org_unit_document_genitive_kk: string;
  position_document_possessive_kk: string;
  position_document_nominative_ru: string;
  employee_full_name_dative_kk: string;
  employee_full_name_genitive_kk: string;
  employee_full_name_dative_ru: string;
  employee_full_name_genitive_ru: string;
};

const blankForms = (): Forms => ({
  employee_full_name_accusative_ru: "",
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

function orgUnitDocumentText(orgUnit: {name?:string|null;name_kk?:string|null;document_genitive_kk?:string|null}|null) {
  return resolvePersonnelOrderOrgUnitForms(orgUnit).org_unit_document_genitive_kk;
}

function documentForms(employee: EmployeeDTO, orgUnit = employee.org_unit): Forms {
  const context=resolvePersonnelDocumentContext(employee,undefined,orgUnit);
  const f=context.values;
  return {
    employee_full_name_accusative_ru:f.employee_full_name_accusative_ru,
    org_unit_document_genitive_kk:f.org_unit_document_genitive_kk,
    position_document_possessive_kk:f.position_document_possessive_kk,
    position_document_nominative_ru:f.position_document_nominative_ru,
    employee_full_name_dative_kk:f.employee_full_name_dative_kk,
    employee_full_name_genitive_kk:f.employee_full_name_genitive_kk,
    employee_full_name_dative_ru:f.employee_full_name_dative_ru,
    employee_full_name_genitive_ru:f.employee_full_name_genitive_ru,
  };
}

function hasKazakhOrgUnitText(orgUnit: {name?:string|null;name_kk?:string|null;document_genitive_kk?:string|null}|null) {
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
  itemContext, onItemAdded,
  initialEmployeeId = null,
  initialEmployeeQuery = null,
  initialOrgUnitId = null,
}: Props) {
  const documentationViewer = useCurrentUser()?.is_documentation_viewer === true;
  const { language: sectionLanguage } = usePersonnelSectionLanguage();
  const [type, setType] = React.useState(itemContext?.itemTypeCode ?? "");
  const [selectedVersion, setSelectedVersion] = React.useState<number | undefined>(itemContext?.template.template_version_id);
  const [variants, setVariants] = React.useState<Record<string, PersonnelPublishedTemplateVariant[]>>({});
  const [variantErrors, setVariantErrors] = React.useState<Record<string, string>>({});
  const [pendingVariants, setPendingVariants] = React.useState<Record<string, boolean>>(()=>Object.fromEntries(PERSONNEL_ORDER_CREATE_TYPES.map(code=>[code,true])));
  const variantsLoading = type ? pendingVariants[type] !== false : Object.values(pendingVariants).some(Boolean);
  const [variantLoadAttempt, setVariantLoadAttempt] = React.useState(0);
  const [titleLoadAttempt, setTitleLoadAttempt] = React.useState(0);
  const [creationCapabilities,setCreationCapabilities]=React.useState<Record<string,{independent_supported?:boolean;creation_supported?:boolean;creation_reason?:string|null}>>({});
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setPendingVariants(Object.fromEntries(PERSONNEL_ORDER_CREATE_TYPES.map(code=>[code,true])));
    setVariantErrors({});setVariants({});setCreationCapabilities({});
    // Publish each catalogue independently: another item kind must not hold
    // the selected version in a loading state.
    PERSONNEL_ORDER_CREATE_TYPES.forEach(code=>{
      void loadTemplateWithTimeout(getPersonnelOrderPublishedVariants(code))
        .then(response=>{
          if(cancelled)return;
          setVariants(previous=>({...previous,[code]:response.items}));
          setCreationCapabilities(previous=>({...previous,[code]:response}));
        })
        .catch(reason=>{
          if(!cancelled)setVariantErrors(previous=>({...previous,[code]:mapPersonnelOrdersApiError(reason,"Не удалось загрузить варианты шаблона.")}));
        })
        .finally(()=>{if(!cancelled)setPendingVariants(previous=>({...previous,[code]:false}));});
    });
    return () => { cancelled = true; };
  }, [open, variantLoadAttempt, itemContext?.orderId, itemContext?.template.template_version_id]);
  const [number, setNumber] = React.useState("");
  const [orderDate, setOrderDate] = React.useState("");
  const [locale, setLocale] = React.useState<"kk" | "ru">(() => itemContext?.itemTypeCode === "HIRE" && itemContext.sourceTitleLocale === "ru" ? "ru" : "kk");
  const [title, setTitle] = React.useState("");
  const [published, setPublished] = React.useState<{ kk: string; ru: string } | null>(null);
  const [publishedTitleError, setPublishedTitleError] = React.useState<string | null>(null);
  const [publishedLoading, setPublishedLoading] = React.useState(false);
  const [publishedFor, setPublishedFor] = React.useState("");
  const employeeContextOwner=React.useRef<string|null>(null);
  const [hireNew, setHireNew] = React.useState(false);
  const [hireName, setHireName] = React.useState(blankHireNewEmployee);
  const [hireTerms, setHireTerms] = React.useState({employment_rate: ""});
  const [hireBasis,setHireBasis]=React.useState(newHireBasis);
  const manualHire = type === "HIRE" && hireNew;
  const [hireDetails, setHireDetails] = React.useState(emptyHireDetails);
  React.useEffect(() => {if (!open) {setHireDetails(emptyHireDetails());setHireBasis(newHireBasis());}}, [open]);
  const hireFullName = manualHire ? hireNewEmployeeName(hireName) : "";
  const hireEmployee = React.useMemo(() => hireFullName ? manualSubjectWording(hireFullName) : null, [hireFullName]);
  const employeeSearchInput=React.useRef<HTMLInputElement>(null);
  const employeeSearch=usePersonnelOrderEmployeeSearch({enabled:open&&Boolean(type)&&!manualHire,initialEmployeeId,initialQuery:initialEmployeeQuery??"",scopeKey:String(itemContext?.orderId??"new"),includeAssignments:["SUPPLEMENTARY_PAY","CONCURRENT_DUTY_START","CONCURRENT_DUTY_END"].includes(type),onReset:resetEmployeeContext,onSelected:applyEmployee});
  const {employee:linkedEmployee,manualName,query,matches,loading:selectingEmployee,searching,finished:employeeSearchFinished,error:employeeSearchError}=employeeSearch;
  const employee=manualHire ? hireEmployee : linkedEmployee??(manualName?manualSubjectWording(manualName):null);
  const [department,setDepartment]=React.useState<DepartmentDraft>(blankDepartment);
  const departmentText=departmentValues(department),selectedOrgUnit=department.unit,org=departmentText.name_ru;
  const [orgUnitOptions, setOrgUnitOptions] = React.useState<OrgUnitSelectOption[]>([]);
  const [position, setPosition] = React.useState("");
  const [hirePositionKk,setHirePositionKk]=React.useState("");
  const [hirePositionManual,setHirePositionManual]=React.useState<HirePositionManualForms>({ru:false,kk:false});
  const [documentPosition, setDocumentPosition] = React.useState<DocumentPosition | null>(null);
  const positionCatalog = usePersonnelOrderPositions(open);
  const positionChoiceOwner = React.useRef<string | null>(null);
  const [start, setStart] = React.useState("");
  const [end, setEnd] = React.useState("");
  const [effective, setEffective] = React.useState("");
  const [applicationDate, setApplicationDate] = React.useState("");
  const [applicationNumber, setApplicationNumber] = React.useState("");
  const [certificateDate, setCertificateDate] = React.useState("");
  const [certificateNumber, setCertificateNumber] = React.useState("");
  const [nameForms,setNameForms]=React.useState(()=>{const {org_unit_document_genitive_kk:_,...forms}=blankForms();return forms;});
  const kk:Forms={...nameForms,org_unit_document_genitive_kk:departmentText.genitive_kk};
  const setKk:React.Dispatch<React.SetStateAction<Forms>>=update=>setNameForms(previous=>{
    const next=typeof update==="function"?update({...previous,org_unit_document_genitive_kk:departmentText.genitive_kk}):update;
    const {org_unit_document_genitive_kk:_,...forms}=next;return forms;
  });
  const [formsExpanded, setFormsExpanded] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [duplicateConflict,setDuplicateConflict]=React.useState<PersonnelOrderHeaderDuplicatePreview|null>(null);
  const [createdOrder,setCreatedOrder]=React.useState<PersonnelOrderManualDraftCreateResult|null>(null);
  const submitInFlight=React.useRef(false);
  const savedOrder=React.useRef<PersonnelOrderManualDraftCreateResult|null>(null);
  React.useEffect(()=>{if(open){submitInFlight.current=false;savedOrder.current=null;setCreatedOrder(null);setDuplicateConflict(null);}},[open]);
  const ruGenitiveEdited = React.useRef(false);
  const editedPositionForms = React.useRef(new Set<string>());
  const editedEmployeeDatives = React.useRef(new Set<string>());
  React.useEffect(() => {if (open) editedEmployeeDatives.current.clear();}, [open]);
  const templateId = React.useRef(0);
  const dialogRef = React.useRef<HTMLElement>(null);
  const restoreFocusRef = React.useRef<HTMLElement | null>(null);

  const cessation = type === "CONCURRENT_DUTY_END";
  const concurrent = type === "CONCURRENT_DUTY_START" || cessation;
  const simpleAllowance = type === "SUPPLEMENTARY_PAY";
  const [simpleAllowanceBasis, setSimpleAllowanceBasis] = React.useState({basis_ru:"Личное заявление",basis_kk:"Жеке өтініш"});
  const [replacementFields,setReplacementFields] = React.useState<ReplacementFields>(blankReplacement);
  type RecipientRole=Omit<AllowanceRecipient,"org_unit_id"|"org_unit_ru"|"org_unit_kk"|"org_unit_genitive_ru">;
  const [recipientRole,setRecipientRole]=React.useState<RecipientRole>(()=>({position_ru:"",position_kk:"",position_dative_ru:""}));
  const allowanceRecipient:AllowanceRecipient={...recipientRole,org_unit_id:selectedOrgUnit?.unit_id??undefined,org_unit_ru:departmentText.name_ru,org_unit_kk:departmentText.genitive_kk,org_unit_genitive_ru:departmentText.genitive_ru};
  const setAllowanceRecipient=(next:AllowanceRecipient)=>{
    const {org_unit_id:_,org_unit_ru:__,org_unit_kk:___,org_unit_genitive_ru:____,...role}=next;
    if(next.assignment_id!==recipientRole.assignment_id&&next.assignment_id){
      const assignment=employee?.assignments?.find(row=>row.assignment_id===next.assignment_id);
      if(assignment?.org_unit)setDepartment(departmentFromUnit({...assignment.org_unit,unit_id:assignment.org_unit_id??assignment.org_unit.unit_id}));
    }
    setRecipientRole(role);
  };
  const [ablativeKk, setAblativeKk] = React.useState("");
  const educationOrder = type === "EDUCATION_INFORMATION_CHANGE";
  const personalDataOrder = type === "PERSONAL_DATA_CHANGE";
  const [personalDataDoc,setPersonalDataDoc]=React.useState(emptyPersonalDataDraft);
  const [educationDoc, setEducationDoc] = React.useState(emptyEducationDraft);
  const educationManual = educationOrder && educationDoc.subject_mode === "MANUAL";
  const serviceLengthOrder = type === "SERVICE_LENGTH_CHANGE";
  const [serviceLengthDoc, setServiceLengthDoc] = React.useState(emptyServiceLengthDraft);
  const manualDocumentSubject = educationManual || (personalDataOrder && personalDataDoc.subject_mode === 'MANUAL') || (serviceLengthOrder && serviceLengthDoc.subject_mode === "MANUAL");
  const categoryOrder = type === "QUALIFICATION_CATEGORY";
  const [categoryDoc,setCategoryDoc] = React.useState(emptyCategoryDraft);
  const previousCategoryContext=React.useRef<PersonnelDocumentContext|null>(null);
  const categoryContext=React.useMemo(()=>resolvePersonnelDocumentContext(employee,documentPosition??undefined,
    selectedOrgUnit?{...selectedOrgUnit,
      name:department.overrides.name_ru??selectedOrgUnit.name,
      name_kk:department.overrides.name_kk??selectedOrgUnit.name_kk,
      document_genitive_ru:department.overrides.genitive_ru??selectedOrgUnit.document_genitive_ru,
      document_genitive_kk:department.overrides.genitive_kk??selectedOrgUnit.document_genitive_kk}:null),[employee,documentPosition,department]);
  React.useEffect(()=>{
    const previous=previousCategoryContext.current;previousCategoryContext.current=categoryContext;
    setCategoryDoc(current=>refreshCategoryDocumentContext(current,categoryContext,previous));
    setEducationDoc(current=>refreshEducationContext(current,categoryContext,previous));
    setServiceLengthDoc(current=>refreshServiceLengthContext(current,categoryContext,previous));
    setPersonalDataDoc(current=>refreshPersonalDataContext(current,categoryContext,previous));
  },[categoryContext]);
  function updateCategoryDocument(next:typeof categoryDoc) {
    if(next.document_forms_ru.employee_full_name_genitive_ru!==categoryDoc.document_forms_ru.employee_full_name_genitive_ru)ruGenitiveEdited.current=true;
    for(const key of ["employee_full_name_genitive_kk","position_document_possessive_kk"] as const) {
      if(next.document_forms_kk[key]!==categoryDoc.document_forms_kk[key])editedPositionForms.current.add(key);
    }
    setKk(current=>({...current,employee_full_name_genitive_ru:next.document_forms_ru.employee_full_name_genitive_ru,
      employee_full_name_genitive_kk:next.document_forms_kk.employee_full_name_genitive_kk,position_document_possessive_kk:next.document_forms_kk.position_document_possessive_kk}));
    if(JSON.stringify(next.document_org_unit)!==JSON.stringify(categoryDoc.document_org_unit))setDepartment(current=>({...current,overrides:{...current.overrides,
      name_ru:next.document_org_unit.name,name_kk:next.document_org_unit.name_kk,
      genitive_ru:next.document_org_unit.document_genitive_ru,genitive_kk:next.document_org_unit.document_genitive_kk}}));
    setCategoryDoc(next);setEffective(next.effective_date||"");
  }
  const transfer = type === "TRANSFER";
  const [medicalSpecialty,setMedicalSpecialty]=React.useState<MedicalSpecialtySnapshot|null>(null);
  React.useEffect(()=>setMedicalSpecialty(null),[open,itemContext?.orderId,type]);
  const [positionRefreshing,setPositionRefreshing]=React.useState(false);
  const [transferFields, setTransferFields] = React.useState<TransferFields>({ position_ru: "", position_kk: "", org_unit_ru: "", org_unit_kk: "", rate: "", basis_ru: "", basis_kk: "" });
  const transferLabels = { position_ru: "Новая должность (RU)", position_kk: "Новая должность (KK)", org_unit_ru: "Новое подразделение (RU)", org_unit_kk: "Новое подразделение (KK)", rate: "Ставка после перевода", basis_ru: "Основание перевода (RU)", basis_kk: "Основание перевода (KK)" };
  const recall = type === "LEAVE.ANNUAL.RECALL";
  const [recallTextFields,setRecallTextFields]=React.useState({recall_position_kk:"",basis_ru:"",basis_kk:""});
  const recallFields={...recallTextFields,recall_org_unit_kk:departmentText.name_kk};
  const setRecallFields:React.Dispatch<React.SetStateAction<typeof recallFields>>=update=>setRecallTextFields(previous=>{
    const next=typeof update==="function"?update({...previous,recall_org_unit_kk:departmentText.name_kk}):update;
    const {recall_org_unit_kk:_,...fields}=next;return fields;
  });
  const [recallName,setRecallName]=React.useState("");
  const [recallCases,setRecallCases]=React.useState({ru:"",kk:""});
  const [recallCaseSuggestions,setRecallCaseSuggestions]=React.useState({ru:false,kk:false});
  const recallEdited=React.useRef(new Set<string>());
  const unpaid = type === "LEAVE.UNPAID.GRANT";
  const childcare = type === "LEAVE.CHILDCARE.GRANT";
  const periodLeave = unpaid || childcare;
  const formsComplete = Object.entries(kk).every(([key, value]) => key === "employee_full_name_accusative_ru" || (!childcare && key === "employee_full_name_genitive_ru") || value.trim());
  const missingFormLabels = ([
    ["org_unit_document_genitive_kk", "Подразделение в тексте приказа (KK)"],
    ["position_document_possessive_kk", "Должность в тексте приказа (KK)"],
    ["position_document_nominative_ru", "Должность в тексте приказа (RU)"],
    ["employee_full_name_dative_kk", "ФИО в дательном падеже (KK)"],
    ["employee_full_name_genitive_kk", "ФИО в родительном падеже (KK)"],
    ["employee_full_name_dative_ru", "ФИО в дательном падеже (RU)"],
  ] as Array<[keyof Forms, string]>).filter(([key]) => !kk[key].trim()).map(([, label]) => label);
  const resolvedTitle = published?.[locale].trim() || personnelOrderCanonicalTitle(type, locale);
  const typeVariants = variants[type] || [];
  const resolvedVersion = !variantsLoading && !variantErrors[type]
    ? typeVariants.find(variant => variant.template_version_id === selectedVersion)?.template_version_id
      ?? (typeVariants.length === 1 ? typeVariants[0].template_version_id : undefined)
    : undefined;
  const replacementMode = type === "CONCURRENT_DUTY_START" ? typeVariants.find(v=>v.template_version_id===resolvedVersion)?.replacement_mode : null;
  const workAllowance = replacementMode === "WORK_ALLOWANCE";
  const optionalPlacement = replacementMode === "PAY" && typeVariants.find(v=>v.template_version_id===resolvedVersion)?.replacement_optional_placement === true;
  const serviceArea=optionalPlacement && typeVariants.find(v=>v.template_version_id===resolvedVersion)?.service_area_allowance===true;
  const legacyTemplates = !itemContext && creationCapabilities[type]?.independent_supported === false;
  const versionResolved = !variantsLoading && !variantErrors[type] && Boolean(creationCapabilities[type])
    && (resolvedVersion != null || legacyTemplates);
  const templateKey = `${type}:${resolvedVersion ?? "legacy"}`;
  const templateReady = versionResolved && publishedFor === templateKey && Boolean(published?.[locale]?.trim()) && !publishedTitleError;
  const typeCreationBlocked=creationCapabilities[type]?.creation_supported===false;
  const independentUnavailable=Object.values(creationCapabilities).some(value=>value.independent_supported===false);
  const blockedReasons: string[] = [];
  if(selectingEmployee)blockedReasons.push("Дождитесь загрузки данных сотрудника.");
  const missing = (condition: boolean, ru: string, kz: string) => {
    if (condition) blockedReasons.push(sectionLanguage === "kk" ? kz : ru);
  };
  missing(busy, "Приказ создаётся. Дождитесь завершения.", "Бұйрық жасалып жатыр. Аяқталуын күтіңіз.");
  missing(!type, "Выберите вид кадрового приказа.", "Кадрлық бұйрық түрін таңдаңыз.");
  missing(typeCreationBlocked, creationCapabilities[type]?.creation_reason || "Выбранный вид недоступен в текущей схеме БД.", "Қазіргі ДБ құрылымы таңдалған бұйрық түрін сақтауға рұқсат етпейді. Үшінші кезеңнің көшіруі қажет.");
  missing(variantsLoading, "Дождитесь загрузки вариантов шаблона и определения версии.", "Үлгі нұсқаларын жүктеу және нұсқаны анықтау аяқталуын күтіңіз.");
  missing(Boolean(type && variantErrors[type]), variantErrors[type] || "", variantErrors[type] || "");
  missing(Boolean(type && !variantsLoading && !variantErrors[type] && !versionResolved), typeVariants.length > 1
    ? "Выберите опубликованную версию шаблона в меню вида приказа."
    : "Для выбранного вида нет опубликованной версии шаблона. Опубликуйте шаблон перед созданием приказа.",
    typeVariants.length > 1 ? "Бұйрық түрі мәзірінен жарияланған үлгі нұсқасын таңдаңыз." : "Таңдалған түр үшін жарияланған үлгі жоқ. Бұйрық жасамас бұрын үлгіні жариялаңыз.");
  missing(Boolean(type && versionResolved && !templateReady), publishedTitleError || "Дождитесь загрузки выбранной версии шаблона.", publishedTitleError || "Таңдалған үлгі нұсқасының жүктелуін күтіңіз.");
  missing(!itemContext && !number.trim(), "Введите номер приказа.", "Бұйрық нөмірін енгізіңіз.");
  missing(!itemContext && !orderDate, "Укажите дату приказа.", "Бұйрық күнін көрсетіңіз.");
  missing(!resolvedTitle, "Название приказа не загружено.", "Бұйрық атауы жүктелмеді.");
  missing(!manualHire&&!manualDocumentSubject&&!linkedEmployee?.id&&!manualName, "Выберите сотрудника из списка кандидатов.", "Қызметкерді үміткерлер тізімінен таңдаңыз.");
  if (manualHire && hireNewEmployeeError(hireName)) blockedReasons.push(hireNewEmployeeError(hireName)!);
  if (type === "HIRE") blockedReasons.push(...hireTermsIssues(hireTerms.employment_rate, hasHireBasis({hire_basis:hireBasis})));

  if(educationOrder)blockedReasons.push(...educationErrors(educationDoc));
  if(personalDataOrder)blockedReasons.push(...personalDataErrors(personalDataDoc));
  if(serviceLengthOrder)blockedReasons.push(...serviceLengthErrors(serviceLengthDoc));
  if(categoryOrder)blockedReasons.push(...categoryDraftErrors(categoryDoc));
  if (periodLeave) {
    missing(!start, "Укажите дату начала отпуска.", "Демалыстың басталу күнін көрсетіңіз.");
    missing(!end, "Укажите дату окончания отпуска.", "Демалыстың аяқталу күнін көрсетіңіз.");
    missing(Boolean(start && end && end < start), "Дата окончания отпуска раньше даты начала.", "Демалыстың аяқталу күні басталу күнінен ерте.");
    const formNames: Record<Exclude<keyof Forms, "employee_full_name_accusative_ru">, [string, string]> = {
      org_unit_document_genitive_kk: ["Подразделение в тексте приказа (KZ)", "Бұйрық мәтініндегі бөлімше (KZ)"],
      position_document_possessive_kk: ["Должность в тексте приказа (KZ)", "Бұйрық мәтініндегі лауазым (KZ)"],
      position_document_nominative_ru: ["Должность в тексте приказа (RU)", "Бұйрық мәтініндегі лауазым (RU)"],
      employee_full_name_dative_kk: ["ФИО в дательном падеже (KZ)", "Аты-жөні барыс септігінде (KZ)"],
      employee_full_name_genitive_kk: ["ФИО в родительном падеже (KZ)", "Аты-жөні ілік септігінде (KZ)"],
      employee_full_name_dative_ru: ["ФИО в дательном падеже (RU)", "Аты-жөні барыс септігінде (RU)"],
      employee_full_name_genitive_ru: ["ФИО в родительном падеже (RU)", "Аты-жөні ілік септігінде (RU)"],
    };
    (Object.keys(formNames) as Array<keyof typeof formNames>).forEach(key => {
      if (key !== "employee_full_name_genitive_ru" || childcare)
        missing(!kk[key].trim(), `Заполните поле «${formNames[key][0]}».`, `«${formNames[key][1]}» өрісін толтырыңыз.`);
    });
  } else {
    missing(!effective, recall ? "Укажите дату отзыва." : "Укажите дату действия.", recall ? "Шақырту күнін көрсетіңіз." : "Күшіне ену күнін көрсетіңіз.");
  }
  if (recall) {
    missing(!recallName.trim(), "Укажите ФИО сотрудника.", "Қызметкердің аты-жөнін көрсетіңіз.");
    missing(!position.trim(), "Заполните должность RU.", "Лауазымды RU тілінде толтырыңыз.");
    missing(!org.trim(), "Заполните подразделение RU.", "Бөлімшені RU тілінде толтырыңыз.");
    missing(!recallFields.recall_position_kk.trim(), "Заполните должность KZ; при отсутствии перевода введите её вручную.", "Лауазымды KZ тілінде толтырыңыз; аудармасы болмаса, қолмен енгізіңіз.");
    missing(!recallFields.recall_org_unit_kk.trim(), "Заполните подразделение KZ.", "Бөлімшені KZ тілінде толтырыңыз.");
    missing(!recallFields.basis_ru.trim(), "Заполните основание RU.", "Негізді RU тілінде толтырыңыз.");
    missing(!recallFields.basis_kk.trim(), "Заполните основание KZ.", "Негізді KZ тілінде толтырыңыз.");
  }
  if (childcare) {
    missing(!applicationDate, "Укажите дату заявления.", "Өтініш күнін көрсетіңіз.");
    missing(!certificateDate, "Укажите дату выдачи свидетельства о рождении.", "Туу туралы куәліктің берілген күнін көрсетіңіз.");
    missing(!certificateNumber.trim(), "Введите номер свидетельства о рождении.", "Туу туралы куәлік нөмірін енгізіңіз.");
  }
  if (transfer) {
    if (!kk.employee_full_name_accusative_ru.trim()) blockedReasons.push("Заполните подтверждённое ФИО в винительном падеже (RU).");
    Object.entries(transferLabels).forEach(([key]) => {
      if (!String(transferFields[key as keyof TransferFields] || "").trim()) blockedReasons.push(`Заполните поле «${transferLabels[key as keyof typeof transferLabels]}».`);
    });
    if (transferFields.rate && (!Number.isFinite(Number(String(transferFields.rate || "").replace(",", "."))) || Number(String(transferFields.rate || "").replace(",", ".")) <= 0)) blockedReasons.push("Ставка после перевода должна быть положительным числом.");
  }
  if (concurrent) {
    const names: Record<string,string> = {...transferLabels, position_ru:"Дополнительная должность (RU)",position_kk:"Дополнительная должность (KK)",org_unit_ru:"Дополнительное подразделение (RU)",org_unit_kk:"Дополнительное подразделение (KK)",rate:"Дополнительная ставка",basis_ru:"Основание совмещения (RU)",basis_kk:"Основание совмещения (KK)",position_genitive_ru:"Дополнительная должность в родительном падеже (RU)",org_unit_genitive_ru:"Дополнительное подразделение в родительном падеже (RU)",total_rate:"Общая ставка"};
    if (cessation) { delete names.total_rate; names.remaining_rate="Оставшаяся общая ставка"; names.rate="Снимаемая ставка"; names.basis_ru="Основание прекращения совмещения (RU)"; names.basis_kk="Основание прекращения совмещения (KK)"; }
    if (replacementMode === "PAY") { delete names.rate; delete names.total_rate; }
    if (workAllowance) delete names.rate;
    if (optionalPlacement) {
      for (const key of ["position_ru","position_kk","org_unit_ru","org_unit_kk"]) delete names[key];
      if (!transferFields.position_ru.trim()) delete names.position_genitive_ru;
      if (!transferFields.org_unit_ru.trim()) delete names.org_unit_genitive_ru;
    }
    if(serviceArea)for(const key of ['position_genitive_ru','org_unit_genitive_ru'])delete names[key];
    Object.entries(names).forEach(([key,label]) => {if (!String(transferFields[key as keyof TransferFields] || "").trim()) blockedReasons.push(`Заполните поле «${label}».`);});
    if (!cessation && !kk.employee_full_name_dative_ru.trim()) blockedReasons.push("Заполните ФИО в дательном падеже (RU).");
    if (!cessation && !kk.employee_full_name_dative_kk.trim()) blockedReasons.push("Заполните ФИО в дательном падеже (KK).");
    if (replacementMode !== "PAY" && transferFields.rate && (!Number.isFinite(Number(String(transferFields.rate || "").replace(",", "."))) || Number(String(transferFields.rate || "").replace(",", ".")) <= 0)) blockedReasons.push("Дополнительная ставка должна быть положительной.");
    if (!cessation && replacementMode !== "PAY" && transferFields.total_rate && (!Number.isFinite(Number(String(transferFields.total_rate || "").replace(",", "."))) || Number(String(transferFields.total_rate || "").replace(",", ".")) <= 0 || (Boolean(transferFields.rate.trim()) && Number(String(transferFields.total_rate || "").replace(",", ".")) <= Number(String(transferFields.rate || "").replace(",", "."))))) blockedReasons.push("Общая ставка должна быть положительной и больше дополнительной, если она указана.");
  }
  if (cessation) {
    missing(!kk.employee_full_name_genitive_ru.trim(), "Заполните ФИО в родительном падеже (RU).", "Аты-жөнін RU тілінде ілік септігінде толтырыңыз.");
    missing(!ablativeKk.trim(), "Заполните ФИО в исходном падеже (KK).", "Аты-жөнін KK тілінде шығыс септігінде толтырыңыз.");
    if (transferFields.remaining_rate && (!Number.isFinite(Number(String(transferFields.remaining_rate || "").replace(",", "."))) || Number(String(transferFields.remaining_rate || "").replace(",", "."))<0)) blockedReasons.push("Оставшаяся общая ставка должна быть неотрицательной.");
  }
  if (replacementMode) blockedReasons.push(...replacementBlockers(replacementFields,replacementMode,effective,optionalPlacement,serviceArea));
  if(serviceArea || simpleAllowance)blockedReasons.push(...recipientBlockers(allowanceRecipient,employee,!simpleAllowance,!simpleAllowance));
  if(simpleAllowance) {
    const percentError = allowancePercentError(replacementFields.allowance_percent);
    if (percentError) blockedReasons.push(percentError);
    for(const [key,label] of [['basis_ru','Основание (RU)'],['basis_kk','Основание (KK)']] as const)if(!simpleAllowanceBasis[key].trim())blockedReasons.push(`Заполните поле «${label}».`);
    if(!kk.employee_full_name_dative_ru.trim())blockedReasons.push('Заполните ФИО в дательном падеже (RU).');
    if(!kk.employee_full_name_dative_kk.trim())blockedReasons.push('Заполните ФИО в дательном падеже (KK).');
  }
  if(positionRefreshing)blockedReasons.push("Загружаются актуальные данные должности.");
  const canSubmit = blockedReasons.length === 0 && !createdOrder;

  const requestClose = React.useCallback(() => {
    if (!busy) onClose();
  }, [busy, onClose]);

  function resetEmployeeContext(){
    setHirePositionKk("");setHirePositionManual({ru:false,kk:false});
    setMedicalSpecialty(null);
    employeeContextOwner.current=null;
    positionChoiceOwner.current=null;
    setDocumentPosition(null);setDepartment(blankDepartment());setPosition("");setKk(blankForms());
    editedEmployeeDatives.current.clear();editedPositionForms.current.clear();recallEdited.current.clear();ruGenitiveEdited.current=false;
    setAllowanceRecipient(blankAllowanceRecipient());
    setTransferFields({position_ru:"",position_kk:"",org_unit_ru:"",org_unit_kk:"",rate:"",basis_ru:"",basis_kk:""});
    setReplacementFields(previous=>({...blankReplacement(),allowance_percent:previous.allowance_percent}));
    setSimpleAllowanceBasis({basis_ru:"Личное заявление",basis_kk:"Жеке өтініш"});
    setRecallName("");setRecallCases({ru:"",kk:""});setRecallCaseSuggestions({ru:false,kk:false});
    setRecallFields({recall_position_kk:"",recall_org_unit_kk:"",basis_ru:"",basis_kk:""});setAblativeKk("");
    setApplicationDate("");setApplicationNumber("");setCertificateDate("");setCertificateNumber("");setError(null);
  }
  function applyEmployee(selected:EmployeeDTO){
    const sameEmployee=employeeContextOwner.current===(selected.id?String(selected.id):`manual:${selected.fio}`);
    if(employeeContextOwner.current!=null&&!sameEmployee)resetEmployeeContext();
    employeeContextOwner.current=(selected.id?String(selected.id):`manual:${selected.fio}`);
    const keepPosition=()=>positionChoiceOwner.current===(selected.id?String(selected.id):`manual:${selected.fio}`);
    if(!keepPosition())setDocumentPosition(null);
    const hasAssignment = selected.has_current_assignment ?? Boolean(selected.active_assignment_id || (recall && selected.position && selected.org_unit));
    if (!keepPosition()) setPosition(hasAssignment ? selected.position?.job_nameru || selected.position?.name || "" : "");
    const forms = documentForms(selected, hasAssignment ? selected.org_unit : null);
    if(!sameEmployee)setDepartment(departmentFromUnit(hasAssignment&&selected.org_unit?{...selected.org_unit,document_genitive_kk:selected.org_unit.document_genitive_kk||forms.org_unit_document_genitive_kk}:null));
    if (cessation) {
      setTransferFields({position_ru:"",position_kk:"",org_unit_ru:"",org_unit_kk:"",rate:"",remaining_rate:"",basis_ru:"",basis_kk:""});
      forms.employee_full_name_genitive_ru = savedRussianEmployeeNameForm(selected, "genitive");
      const proposal = calculateKazakhPersonForm(selected, "ablative");
      setAblativeKk(proposal.needsReview ? "" : proposal.value);
    }
    if (transfer) {
      forms.employee_full_name_dative_ru = savedRussianEmployeeNameForm(selected, "dative");
      forms.employee_full_name_accusative_ru = savedRussianEmployeeNameForm(selected, "accusative");
    }
    if (concurrent || simpleAllowance) {
      // An unconfirmed automatic RU declension must not enter this order.
      forms.employee_full_name_dative_ru = serviceArea||simpleAllowance?russianEmployeeDativeForOrder(selected):savedRussianEmployeeNameForm(selected, "dative");
      if(serviceArea||simpleAllowance)forms.employee_full_name_dative_kk=savedKazakhEmployeeNameForm(selected,'dative')||calculateKazakhPersonForm(selected,'dative').value;
    }
    if (concurrent && !cessation) Object.assign(forms, concurrentEmployeeDatives(selected));
    if(recall){
      const fill=recallEmployeePrefill(selected);
      setRecallName(fill.fullName);if (!keepPosition()) setPosition(fill.positionRu);
      setRecallFields(current=>({
        recall_position_kk:keepPosition() || recallEdited.current.has('recall_position_kk')?current.recall_position_kk:fill.positionKk,
        recall_org_unit_kk:sameEmployee || recallEdited.current.has('recall_org_unit_kk')?current.recall_org_unit_kk:fill.unitKk,
        basis_ru:recallEdited.current.has('basis_ru')?current.basis_ru:fill.basisRu,
        basis_kk:recallEdited.current.has('basis_kk')?current.basis_kk:fill.basisKk,
      }));
      setRecallCases({ru:fill.genitiveRu,kk:fill.genitiveKk});setRecallCaseSuggestions({ru:fill.suggestedRu,kk:fill.suggestedKk});
    }
    setKk(current => ({ ...forms,
      ...Object.fromEntries([...editedPositionForms.current].filter(key=>key in forms).map(key=>[key,current[key as keyof Forms]])),
      employee_full_name_dative_ru: editedEmployeeDatives.current.has("employee_full_name_dative_ru") ? current.employee_full_name_dative_ru : forms.employee_full_name_dative_ru,
      employee_full_name_dative_kk: editedEmployeeDatives.current.has("employee_full_name_dative_kk") ? current.employee_full_name_dative_kk : forms.employee_full_name_dative_kk,
      employee_full_name_genitive_ru: ruGenitiveEdited.current ? current.employee_full_name_genitive_ru : forms.employee_full_name_genitive_ru,
      position_document_possessive_kk: keepPosition() || editedPositionForms.current.has("position_document_possessive_kk") ? current.position_document_possessive_kk : forms.position_document_possessive_kk,
      position_document_nominative_ru: keepPosition() || editedPositionForms.current.has("position_document_nominative_ru") ? current.position_document_nominative_ru : forms.position_document_nominative_ru,
      org_unit_document_genitive_kk: sameEmployee || editedPositionForms.current.has("org_unit_document_genitive_kk") ? current.org_unit_document_genitive_kk : forms.org_unit_document_genitive_kk,
    }));
    setFormsExpanded(!Object.entries(forms).every(([key, value]) => key === "employee_full_name_accusative_ru" || (!childcare && key === "employee_full_name_genitive_ru") || value.trim()));
  }

  // Changing the item kind recomputes its name forms without another actor
  // request or changing the document's selected department.
  React.useEffect(() => {
    if (employee) applyEmployee(employee);
    // Employee selection itself is handled atomically by the search hook.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type]);

  React.useEffect(() => {
    if (!open || !type) return;
    let cancelled = false;
    void loadOrgUnitSelectOptions({includeInactive: true})
      .then((items) => { if (!cancelled) setOrgUnitOptions(items); })
      .catch(() => { if (!cancelled) setOrgUnitOptions([]); });
    return () => { cancelled = true; };
  }, [open, type]);

  React.useEffect(() => {
    setDepartment(current => {
      const source=current.unit;
      const catalog=orgUnitOptions.find(unit=>unit.unit_id===source?.unit_id);
      if(!source||!catalog||source.name_kk)return current;
      return {...current,unit:{...source,name_kk:catalog.name_kk||"",document_genitive_kk:source.document_genitive_kk||catalog.document_genitive_kk||""}};
    });
  }, [orgUnitOptions, employee?.id]);

  React.useEffect(() => {
    const id = ++templateId.current;
    if (!open || !type || !versionResolved) {
      setPublished(null);
      setPublishedFor("");
      setPublishedTitleError(null);
      setPublishedLoading(false);
      setTitle("");
      return;
    }
    setPublished(null);
    setPublishedTitleError(null);
    setTitle("");
    setPublishedLoading(true);
    void loadTemplateWithTimeout(getPersonnelOrderPublishedTemplateTitle(type, ...(resolvedVersion == null ? [] : [resolvedVersion])))
      .then((result) => {
        if (id !== templateId.current) return;
        if (resolvedVersion != null && result.template_version_id !== resolvedVersion) {
          setPublishedTitleError("Ответ сервера не соответствует выбранной версии шаблона. Повторите загрузку.");
          return;
        }
        const titles = { kk: result.title_kk || "", ru: result.title_ru || "" };
        if(result.print_title_approval_required?.length){setPublished(null);setPublishedTitleError(result.print_title_approval_required.join(' '));return;}
        if (!titles[locale].trim()) {
          setPublished(null);
          setPublishedTitleError("Для выбранного типа нет опубликованного шаблона на выбранном языке.");
          return;
        }
        setPublished(titles);
        setPublishedFor(templateKey);
        setTitle(titles[locale].trim() || personnelOrderCanonicalTitle(type, locale));
      })
      .catch((caught) => {
        if (id !== templateId.current) return;
        setPublished(null);
        setTitle(personnelOrderCanonicalTitle(type, locale));
        setPublishedTitleError(`Не удалось загрузить шаблон ${type}${resolvedVersion == null ? "" : ` (ID версии ${resolvedVersion})`}: ${mapPersonnelOrdersApiError(caught, "Опубликованный шаблон не найден.")}`);
      })
      .finally(() => { if (id === templateId.current) setPublishedLoading(false); });
    return () => { if (id === templateId.current) ++templateId.current; };
  }, [locale, open, type, resolvedVersion, versionResolved, templateKey, titleLoadAttempt]);

  React.useEffect(() => {
    setTitle(published?.[locale].trim() || personnelOrderCanonicalTitle(type, locale));
  }, [locale, published, type]);

  React.useEffect(() => {
    if (!open) return;
    if (itemContext) return;
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => dialogRef.current?.focus());

    return () => {
      document.body.style.overflow = previousOverflow;
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [open, itemContext]);

  React.useEffect(() => {
    if (!open || itemContext) return;
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
  }, [open, requestClose, itemContext]);

  if (!open) return null;

  function changeType(nextType: string, versionId?: number) {
    setSelectedVersion(versionId);
    ++templateId.current;
    setType(nextType);
    setRecallFields({recall_position_kk: "", recall_org_unit_kk: "", basis_ru: "", basis_kk: ""});
    recallEdited.current.clear();setRecallCases({ru:"",kk:""});setRecallName("");
    if(nextType === 'LEAVE.ANNUAL.RECALL' && employee){
      const fill=recallEmployeePrefill(employee);setRecallName(fill.fullName);setPosition(fill.positionRu);
      setRecallFields({recall_position_kk:fill.positionKk,recall_org_unit_kk:fill.unitKk,basis_ru:fill.basisRu,basis_kk:fill.basisKk});
      setRecallCases({ru:fill.genitiveRu,kk:fill.genitiveKk});setRecallCaseSuggestions({ru:fill.suggestedRu,kk:fill.suggestedKk});
    }
    setPublished(null);
    setPublishedTitleError(null);
    setTitle("");
    setStart("");
    setHirePositionKk("");setHirePositionManual({ru:false,kk:false});
    setHireDetails(emptyHireDetails());
    setHireBasis(newHireBasis());
    setEnd("");
    setEffective("");
    setEducationDoc(refreshEducationContext(emptyEducationDraft(), categoryContext));
    setServiceLengthDoc(refreshServiceLengthContext(emptyServiceLengthDraft(), categoryContext));
    setPersonalDataDoc(refreshPersonalDataContext(emptyPersonalDataDraft(),categoryContext));
    setReplacementFields(blankReplacement());
    setAllowanceRecipient(blankAllowanceRecipient());
    setTransferFields({ position_ru: "", position_kk: "", org_unit_ru: "", org_unit_kk: "", rate: "", basis_ru: "", basis_kk: "" });
    editedEmployeeDatives.current.clear();
    setKk(blankForms());
    setFormsExpanded(Boolean(employee) && ["LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT"].includes(nextType));
    setApplicationDate(""); setApplicationNumber(""); setCertificateDate(""); setCertificateNumber("");
    setError(null);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (documentationViewer) return;
    if (!canSubmit || !templateReady || submitInFlight.current || savedOrder.current) return;
    submitInFlight.current=true;
    setError(null);
    setDuplicateConflict(null);
    setBusy(true);
    try {
      if (manualHire && hireNewEmployeeError(hireName)) throw Error(hireNewEmployeeError(hireName)!);
      if (!manualHire && !manualDocumentSubject && !linkedEmployee?.id && !manualName) throw Error("Выберите сотрудника или подтвердите ручное ФИО.");
      if (unpaid && (!start || !end)) throw Error("Для отпуска укажите дату начала и дату окончания.");
      if (periodLeave && end < start) throw Error("Дата окончания отпуска не может быть раньше даты начала.");
      if (!itemContext) {
        const duplicate = await previewPersonnelOrderHeaderDuplicate({ order_number: number, order_date: orderDate });
        if (duplicate.blocking) {setDuplicateConflict(duplicate);setError(personnelOrderDuplicateMessage(duplicate,orderDate));return;}
      }
      const days = periodLeave
        ? Math.floor((Date.parse(`${end}T00:00:00`) - Date.parse(`${start}T00:00:00`)) / 86400000) + 1
        : undefined;
      const request = {
        ...(resolvedVersion == null ? {} : { template_version_id: resolvedVersion }),
        order_number: number,
        order_date: orderDate,
        source_title: resolvedTitle,
        source_title_locale: locale,
        item_type_code: type,
        employee_id: manualHire || manualDocumentSubject ? null : linkedEmployee?.id ? Number(linkedEmployee.id) : null,
        unresolved_subject: manualHire ? {full_name:hireFullName,org_unit_name:org,position_name:position,specialty:""} : manualDocumentSubject ? {full_name:personalDataOrder ? personalDataDoc.source_employee_name : educationOrder ? educationDoc.source_employee_name : serviceLengthDoc.source_employee_name,org_unit_name:"",position_name:"",specialty:""} : manualName ? {full_name:manualName,org_unit_name:org,position_name:position,specialty:""} : undefined,
        document_subject_context: { document_department:department, document_position_id: documentPosition?.id ?? null, document_position_kk: type === "HIRE" ? hirePositionKk : documentPosition ? (recall ? recallFields.recall_position_kk : documentPosition.name_kk ?? "") : null, document_position_nominative_ru: documentPosition ? kk.position_document_nominative_ru : null, document_position_possessive_kk: documentPosition ? kk.position_document_possessive_kk : null, org_unit_name: org || null, position_name: position || null, document_org_unit_id: selectedOrgUnit?.unit_id ?? null, document_org_unit_kk: recall ? recallFields.recall_org_unit_kk : selectedOrgUnit?.name_kk ?? null, document_org_unit_genitive_kk: kk.org_unit_document_genitive_kk },
        effective_date: periodLeave ? start : effective,
        period_start: periodLeave ? start : null,
        period_end: periodLeave ? end : null,
        item_payload: personalDataOrder ? personalDataOrderPayload(personalDataDoc) : educationOrder ? educationOrderPayload(educationDoc) : serviceLengthOrder ? serviceLengthOrderPayload(serviceLengthDoc) : categoryOrder ? categoryOrderPayload(categoryDoc) : simpleAllowance ? {allowance_recipient:allowanceRecipient,allowance:{percent:Number(replacementFields.allowance_percent),basis_type:'RECIPIENT_BASE_SALARY',employee_dative_ru:kk.employee_full_name_dative_ru,employee_dative_kk:kk.employee_full_name_dative_kk,basis_ru:simpleAllowanceBasis.basis_ru,basis_kk:simpleAllowanceBasis.basis_kk}} : replacementMode ? {...(serviceArea?{allowance_recipient:allowanceRecipient}:{}),concurrent:{...transferFields,rate:replacementMode==="RATE" || (workAllowance && transferFields.rate.trim())?Number(String(transferFields.rate || "").replace(",", ".")):undefined,total_rate:replacementMode==="RATE" || workAllowance?Number(String(transferFields.total_rate || "").replace(",", ".")):undefined,employee_dative_ru:kk.employee_full_name_dative_ru,employee_dative_kk:kk.employee_full_name_dative_kk},replacement:{...(workAllowance?{allowance_percent:replacementFields.allowance_percent,allowance_basis_ru:replacementFields.allowance_basis_ru,allowance_basis_kk:replacementFields.allowance_basis_kk}:replacementFields),...(serviceArea?{allowance_basis_type:'RECIPIENT_BASE_SALARY'}:{}),mode:replacementMode}} : cessation ? {concurrent:{...transferFields,rate:Number(String(transferFields.rate || "").replace(",", ".")),remaining_rate:Number(String(transferFields.remaining_rate || "").replace(",", ".")),employee_genitive_ru:kk.employee_full_name_genitive_ru,employee_ablative_kk:ablativeKk}} : concurrent ? {concurrent:{...transferFields,rate:Number(String(transferFields.rate || "").replace(",", ".")),total_rate:Number(String(transferFields.total_rate || "").replace(",", ".")),employee_dative_ru:kk.employee_full_name_dative_ru,employee_dative_kk:kk.employee_full_name_dative_kk}} : transfer ? { transfer: { ...transferFields, rate: Number(String(transferFields.rate || "").replace(",", ".")) }, document_forms_ru: { employee_full_name_accusative_ru: kk.employee_full_name_accusative_ru } } : recall ? {...recallFields,source_employee_name:recallName} : periodLeave
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
              assignment: { org_unit: { id: selectedOrgUnit?.unit_id || null, name: org || null }, position: { id: employee?.position?.id || null, name: position || null } },
              basis: childcare ? { kind: "PERSONAL_APPLICATION", date: applicationDate, number: applicationNumber || null, birth_certificate: { date: certificateDate, number: certificateNumber } } : { kind: "PERSONAL_APPLICATION" },
            }
          : {
              document_forms_kk: { position_document_possessive_kk: kk.position_document_possessive_kk, org_unit_document_genitive_kk: kk.org_unit_document_genitive_kk, employee_full_name_dative_kk: kk.employee_full_name_dative_kk, employee_full_name_genitive_kk: kk.employee_full_name_genitive_kk },
              document_forms_ru: { position_document_nominative_ru: kk.position_document_nominative_ru, employee_full_name_dative_ru: kk.employee_full_name_dative_ru },
            },
      };
      if (manualHire) Object.assign(request.item_payload, {new_employee: {...hireName}});
      if (type === "HIRE") Object.assign(request.item_payload, {
        hire_details: hireDetailsPayload(hireDetails),
        hire_position_manual_forms:hirePositionManual,
        employment_rate: hireRateNumber(hireTerms.employment_rate),
        hire_basis: hireBasis,
        ...(selectedOrgUnit?.unit_id ? {org_unit_id: selectedOrgUnit.unit_id} : {}),
        ...(documentPosition?.id ? {position_id: documentPosition.id} : {}),
      });
      if ((transfer || concurrent && !cessation && !replacementMode) && medicalSpecialty && request.item_payload) Object.assign(request.item_payload,{medical_specialty:medicalSpecialty});
      if (type === "HIRE" && request.item_payload) {
        const payload=request.item_payload as Record<string,unknown>;
        payload.document_forms_ru={employee_full_name_dative_ru:kk.employee_full_name_dative_ru,employee_full_name_genitive_ru:kk.employee_full_name_genitive_ru,
          employee_full_name_accusative_ru:kk.employee_full_name_accusative_ru,position_document_nominative_ru:kk.position_document_nominative_ru,
          position_document_genitive_ru:categoryContext.values.position_document_genitive_ru,...(payload.document_forms_ru as object||{})};
        payload.document_forms_kk={employee_full_name_dative_kk:kk.employee_full_name_dative_kk,employee_full_name_genitive_kk:kk.employee_full_name_genitive_kk,
          position_document_possessive_kk:kk.position_document_possessive_kk,org_unit_document_genitive_kk:kk.org_unit_document_genitive_kk,...(payload.document_forms_kk as object||{})};
      }
      if (itemContext) {
        const result = await createPersonnelOrderItem(itemContext.orderId, {
          template_version_id: resolvedVersion,
          item_type_code: type,
          employee_id: request.employee_id,
          unresolved_subject: request.unresolved_subject,
          effective_date: request.effective_date,
          period_start: request.period_start, period_end: request.period_end,
          document_subject_context: request.document_subject_context,
          payload: request.item_payload,
        });
        onItemAdded?.(result);
        return;
      }
      const result = await createManualPersonnelOrderDraft(request);
      savedOrder.current=result;
      setCreatedOrder(result);
      try {onCreated(result);onClose();} catch {setError(`Приказ № ${result.order_number||number} создан (ID ${result.order_id}). Откройте его карточку по ссылке ниже.`);}
    } catch (caught) {
      if (itemContext) dialogRef.current?.closest("details")?.setAttribute("open", "");
      if(caught instanceof PersonnelOrderDuplicateError)setDuplicateConflict(caught.duplicate);
      setError(caught instanceof Error ? caught.message : mapPersonnelOrdersApiError(caught, "Не удалось создать приказ."));
    } finally {
      submitInFlight.current=false;
      setBusy(false);
    }
  }

  const selectHirePosition=(selected:DocumentPosition)=>{
    const forms=resolvePersonnelOrderDocumentForms(selected);
    setDocumentPosition(selected);setPosition(selected.name);setHirePositionKk(selected.name_kk||"");
    positionChoiceOwner.current=employee?.id?String(employee.id):employee?.fio?`manual:${employee.fio}`:null;
    setKk(current=>({...current,...forms,
      position_document_nominative_ru:hirePositionManual.ru?current.position_document_nominative_ru:forms.position_document_nominative_ru,
      position_document_possessive_kk:hirePositionManual.kk?current.position_document_possessive_kk:forms.position_document_possessive_kk}));
    editedPositionForms.current.add("position_document_nominative_ru");editedPositionForms.current.add("position_document_possessive_kk");
  };
  const editHirePosition=(locale:"ru"|"kk",text:string)=>{
    if(locale==='ru')setPosition(text);else setHirePositionKk(text);
    const key=locale==='ru'?'position_document_nominative_ru':'position_document_possessive_kk';
    setDocumentPosition(current=>current?{...current,[locale==='ru'?'name':'name_kk']:text,
      ...(!hirePositionManual[locale]?{[locale==='ru'?'document_nominative_ru':'document_possessive_kk']:text}:{})}:current);
    if(!hirePositionManual[locale])setKk(current=>({...current,[key]:text}));
    editedPositionForms.current.add(key);
  };
  const selectedEmployee = <>
    {!manualHire ? <>
    <div className="relative z-20">
      <input ref={employeeSearchInput} aria-label="Сотрудник" role="combobox" aria-autocomplete="list" aria-expanded={matches.length>0} value={query} maxLength={300} placeholder="Введите фамилию или ФИО" onChange={event=>employeeSearch.input(event.target.value)} className={inputClassName}/>
      {(query||employee)?<button type="button" disabled={busy} className="mt-1 text-sm text-blue-600" onClick={()=>{employeeSearch.clear();requestAnimationFrame(()=>employeeSearchInput.current?.focus());}} aria-label="Очистить сотрудника">Очистить</button>:null}
      {selectingEmployee||searching?<p role="status">{selectingEmployee?"Загружаются данные сотрудника…":"Поиск сотрудников…"}</p>:null}
      {employeeSearchError?<p role="alert">{employeeSearchError}</p>:null}
      {employeeSearchFinished&&!employeeSearchError&&!employee&&matches.length===0&&query.trim().length>=2?<p role="status">Сотрудники не найдены. Уточните фамилию.</p>:null}
      {manualName?<p role="status" data-testid="manual-subject-status" className="text-sm text-amber-700">ФИО введено вручную. Карточка сотрудника не найдена. В приказе сохранится только снимок ФИО.</p>:null}
      {!personalDataOrder&&!serviceLengthOrder&&!educationOrder&&!manualName&&employeeSearchFinished&&!employeeSearchError&&!employee&&!searching&&matches.length===0&&query.trim().length>=2?<button type="button" onClick={()=>{employeeSearch.confirmManual();applyEmployee(manualSubjectWording(query.trim()));}} className="mt-2 rounded border px-3 py-2 text-sm">Использовать ФИО вручную</button>:null}
      {matches.length>0?<div role="listbox" aria-label="Найденные сотрудники" className="mt-1 rounded border bg-white shadow dark:bg-zinc-900">{matches.map(candidate=><button type="button" role="option" aria-label={candidate.fio||undefined} key={candidate.id} data-employee-id={candidate.id} className="block w-full p-2 text-left text-sm hover:bg-blue-50 dark:hover:bg-zinc-800" onClick={()=>employeeSearch.select(candidate)}>{candidate.fio}<span className="block text-xs text-zinc-500">{candidate.org_unit?.name||"Подразделение не указано"}</span></button>)}</div>:null}
    </div>
    </> : null}
    {employee || type === 'HIRE'?<>
      {linkedEmployee?<input type="hidden" name="employee_id" value={linkedEmployee.id||""} data-testid="selected-employee-id"/>:null}
      {!cessation ? <>
      {type === "HIRE" ? <PersonnelOrderHireDepartmentFields value={department} options={orgUnitOptions} onChange={value=>setDepartment(value)} disabled={busy}/> : <PersonnelOrderDepartmentPicker value={department} options={orgUnitOptions} onChange={setDepartment} label={transfer||concurrent?"Подразделение сотрудника":"Подразделение"}/>}
      {type === "HIRE" ? <PersonnelOrderHirePositionFields value={{id:documentPosition?.id??null,ru:position,kk:hirePositionKk}}
        {...positionCatalog} disabled={busy} onSelect={selectHirePosition} onTextChange={editHirePosition}/> : <>
      <Field label="Должность">
        <PersonnelOrderPositionPicker label="Должность" value={position} {...positionCatalog}
          onCustomChange={recall ? value => {setPosition(value);setDocumentPosition(null);positionChoiceOwner.current=employee?.id?String(employee.id):employee?.fio?`manual:${employee.fio}`:null;} : undefined}
          onSelect={selected => {
            setDocumentPosition(selected); positionChoiceOwner.current=employee?.id?String(employee.id):employee?.fio?`manual:${employee.fio}`:null; setPosition(selected.name);
            const forms=resolvePersonnelOrderDocumentForms(selected);
            setKk(current=>({...current,...forms}));
            editedPositionForms.current.add("position_document_nominative_ru");editedPositionForms.current.add("position_document_possessive_kk");
            if(recall)setRecallFields(current=>({...current,recall_position_kk:selected.name_kk||""}));
          }}/>

      </Field>
      </>}
      </> : null}
    </>:null}
  </>;

  return (
    <div
      className={itemContext ? "border-t border-zinc-200 dark:border-zinc-800" : "fixed inset-0 z-[60] flex items-center justify-center bg-zinc-700/45 p-4 backdrop-blur-[1px] dark:bg-black/65"}
      data-testid={itemContext ? "personnel-order-add-item-form" : "personnel-order-create-dialog"}
      onMouseDown={(event) => {
        if (!itemContext && event.target === event.currentTarget) requestClose();
      }}
    >
      <section
        ref={dialogRef}
        role={itemContext ? undefined : "dialog"}
        aria-modal={itemContext ? undefined : true}
        aria-labelledby={itemContext ? undefined : "personnel-order-create-title"}
        tabIndex={-1}
        className={itemContext ? "w-full" : "relative flex max-h-[calc(100vh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white text-zinc-950 shadow-2xl dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"}
      >
        {!itemContext ? <header data-testid="personnel-order-create-header" className="flex shrink-0 items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <h2 id="personnel-order-create-title" className="text-lg font-semibold">Создать приказ</h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Будет создан новый приказ в статусе DRAFT.</p>
          </div>
          <button type="button" aria-label="Закрыть" onClick={requestClose} disabled={busy} className="-mr-1 -mt-1 rounded-md p-2 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-zinc-800 dark:hover:text-zinc-50">×</button>
        </header> : null}
        <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit} onKeyDown={(event) => {
          if (event.key === "Enter" && event.target instanceof HTMLInputElement && event.target.type !== "submit") event.preventDefault();
        }}>
          <div data-testid="personnel-order-create-body" className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-5 py-4">
            {itemContext ? <p className="text-sm font-medium">Тип пункта и шаблон</p> : null}
            <PersonnelOrderTypeMenu value={type} language={sectionLanguage} onChange={changeType} variants={variants} selectedVersion={resolvedVersion} disabled={busy} />
            {variantsLoading ? <p role="status">{sectionLanguage==='kk'?'Үлгі нұсқалары жүктелуде; бұйрық түрін таңдауға болады.':'Загружаются варианты шаблонов; вид приказа уже можно выбрать.'}</p> : null}
            {type && variantErrors[type] ? <p role="alert">{sectionLanguage==='kk'?'Үлгі нұсқаларын жүктеу қатесі: ':'Не удалось загрузить варианты шаблона: '}{variantErrors[type]}</p> : null}
            {publishedLoading ? <p role="status" data-testid="selected-template-loading">{sectionLanguage==='kk'?'Таңдалған үлгі нұсқасы жүктелуде':'Загружается выбранная версия шаблона'}{resolvedVersion == null ? "" : ` (ID ${resolvedVersion})`}…</p> : null}
            {type && (variantErrors[type] || publishedTitleError) ? <button type="button" disabled={busy || variantsLoading} onClick={() => publishedTitleError ? setTitleLoadAttempt(attempt => attempt + 1) : setVariantLoadAttempt(attempt => attempt + 1)} className="text-sm text-blue-700">{sectionLanguage === 'kk' ? 'Жүктеуді қайталау' : 'Повторить загрузку шаблонов'}</button> : null}
            {independentUnavailable ? <p role="status">{sectionLanguage==='kk'?'Дербес үлгі нұсқалары осы БД құрылымында қолжетімсіз. Бұрынғы бұйрық түрлері мен негізгі үлгілері қолжетімді.':'Независимые варианты шаблонов недоступны в текущей схеме БД. Прежние виды приказов и основные шаблоны доступны.'}</p> : null}
            {typeCreationBlocked ? <p role="alert" data-testid="order-type-schema-unavailable">{sectionLanguage==='kk'?`Қазіргі БД құрылымы ${type} бұйрық түрін сақтауға рұқсат етпейді. ${categoryOrder ? "poqual001 (hrlocal305)" : "hrrecall001"} көшіруін келісіп қолдану қажет; БД автоматты түрде өзгермейді.`:creationCapabilities[type]?.creation_reason || 'Выбранный вид недоступен в текущей схеме БД.'}</p> : null}
            {!itemContext ? <>
            <Field label="Номер приказа"><input aria-label="Номер приказа" required value={number} onChange={(event) => setNumber(event.target.value)} className={inputClassName} /></Field>
            <Field label="Дата приказа"><input aria-label="Дата приказа" type="date" required value={orderDate} onChange={(event) => setOrderDate(event.target.value)} className={inputClassName} /></Field>
            <Field label="Язык"><select aria-label="Язык" value={locale} onChange={(event) => setLocale(event.target.value as "kk" | "ru")} className={inputClassName}><option value="kk">Қазақша</option><option value="ru">Русский</option></select></Field>
            <Field label="Название приказа"><textarea aria-label="Название приказа" readOnly value={title} placeholder={type ? "Загрузка названия…" : "Сначала выберите тип пункта"} className={`${inputClassName} min-h-20 resize-y`} /></Field>
            </> : null}
            {publishedTitleError ? <p role="alert" data-testid="selected-template-error" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-100">{publishedTitleError}</p> : null}
            {type ? <>
              {type === "HIRE" ? <PersonnelOrderHireEmployeeFields isNew={hireNew} value={hireName} disabled={busy}
                onModeChange={next => {employeeSearch.clear(); setHireNew(next);}}
                onChange={setHireName} /> : null}
              {manualHire ? selectedEmployee : null}
              {!manualHire&&!manualDocumentSubject ? <div className="space-y-1 text-sm font-medium leading-5 text-zinc-800 dark:text-zinc-100"><span>Сотрудник</span>{selectedEmployee}</div> : null}
              {personalDataOrder ? <PersonnelOrderPersonalDataFields value={personalDataDoc} disabled={busy} orgUnits={orgUnitOptions} onChange={next=>{
                if(next.subject_mode!==personalDataDoc.subject_mode){employeeSearch.clear();previousCategoryContext.current=null;}
                setPersonalDataDoc(next);setEffective(next.effective_date);
              }}/> : null}
              {educationOrder ? <PersonnelOrderEducationFields value={educationDoc} disabled={busy} onChange={next=>{
                if(next.subject_mode !== educationDoc.subject_mode) {employeeSearch.clear();previousCategoryContext.current=null;}
                setEducationDoc(next);setEffective(next.effective_date);
              }}/> : null}
              {serviceLengthOrder ? <PersonnelOrderServiceLengthFields value={serviceLengthDoc} disabled={busy} onChange={next=>{
                if(next.subject_mode !== serviceLengthDoc.subject_mode) {employeeSearch.clear();previousCategoryContext.current=null;}
                setServiceLengthDoc(next);setEffective(next.effective_date);
              }}/> : null}
              {categoryOrder ? <PersonnelOrderCategoryFields value={categoryDoc} disabled={busy} onChange={updateCategoryDocument}/> : null}
              {type === "HIRE" ? <PersonnelOrderHireDetailsFields value={hireDetails} onChange={setHireDetails} disabled={busy}/> : null}
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
              </> : categoryOrder || serviceLengthOrder || educationOrder || personalDataOrder ? null : <Field label="Дата действия"><input aria-label="Дата действия" type="date" required value={effective} onChange={(event) => setEffective(event.target.value)} className={inputClassName} /></Field>}
            </> : null}
              {employee && cessation ? <section className="space-y-3 sm:col-span-2">
                {employee.additional_assignments?.length ? <Field label="Прекращаемое дополнительное назначение"><select aria-label="Прекращаемое дополнительное назначение" className={inputClassName} value={transferFields.assignment_id || ""} onChange={e=>{
                  const assignment=employee.additional_assignments?.find(a=>a.assignment_id===Number(e.target.value) && a.is_primary===false);
                  setTransferFields(current=>({...current,assignment_id:assignment?.assignment_id,position_id:assignment?.position_id,org_unit_id:assignment?.org_unit_id,
                    position_ru:assignment?.position?.job_nameru || assignment?.position?.name || "",position_kk:assignment?.position?.document_form_status==='needs_review' ? '' : assignment?.position?.job_namekk || assignment?.position?.name_kk || "",
                    org_unit_ru:assignment?.org_unit?.name || "",org_unit_kk:assignment?.org_unit?.document_genitive_kk || assignment?.org_unit?.name_kk || "",position_genitive_ru:"",org_unit_genitive_ru:"",rate:assignment ? String(assignment.rate) : ""}));
                }}><option value="">Выберите дополнительное назначение</option>{employee.additional_assignments.filter(a=>a.is_primary===false).map(a=><option key={a.assignment_id} value={a.assignment_id}>{a.position?.job_nameru || a.position?.name} — {a.org_unit?.name} ({a.rate})</option>)}</select></Field> : null}
                <Field label="ФИО в родительном падеже (RU)"><input aria-label="ФИО в родительном падеже (RU)" className={inputClassName} value={kk.employee_full_name_genitive_ru} onChange={e=>setKk(current=>({...current,employee_full_name_genitive_ru:e.target.value}))}/></Field>
                <Field label="ФИО в исходном падеже (KK)"><input aria-label="ФИО в исходном падеже (KK)" className={inputClassName} value={ablativeKk} onChange={e=>setAblativeKk(e.target.value)}/></Field>
              </section> : null}
              {employee && transfer ? <Field label="ФИО в винительном падеже (RU)"><input aria-label="ФИО в винительном падеже (RU)" value={kk.employee_full_name_accusative_ru} onChange={e=>setKk(current=>({...current,employee_full_name_accusative_ru:e.target.value}))} className={inputClassName}/>{!kk.employee_full_name_accusative_ru.trim() ? <p role="alert">Нет подтверждённого ФИО в винительном падеже (RU). Заполните вручную.</p> : null}</Field> : null}
              {employee && (serviceArea || simpleAllowance)?<PersonnelOrderAllowanceRecipient employee={employee} value={allowanceRecipient} onChange={setAllowanceRecipient}/>:null}
              {simpleAllowance ? <section data-testid="simple-allowance-fields" className="space-y-3 sm:col-span-2">
                <PersonnelOrderAllowancePercent value={replacementFields.allowance_percent} onChange={value=>setReplacementFields(current=>({...current,allowance_percent:value}))} inputClassName={inputClassName}/>
                {(['ru','kk'] as const).map(lang=><Field key={lang} label={`Основание (${lang.toUpperCase()})`}><input aria-label={`Основание (${lang.toUpperCase()})`} className={inputClassName} value={simpleAllowanceBasis[`basis_${lang}`]} onChange={e=>setSimpleAllowanceBasis(current=>({...current,[`basis_${lang}`]:e.target.value}))}/></Field>)}
              </section> : null}
              {employee && (transfer || concurrent) ? <PersonnelOrderTransferFields value={transferFields} onChange={setTransferFields} orgUnits={orgUnitOptions} disabled={busy} mode={cessation ? "cessation" : concurrent ? "concurrent" : "transfer"} showRates={replacementMode!=="PAY"} rateOptional={workAllowance} documentFormsKK={Boolean(replacementMode)} autoCaseForms={serviceArea} autoGenitiveForms={concurrent && !cessation && !serviceArea} afterDepartment={transfer || concurrent && !cessation && !replacementMode ? <PersonnelOrderMedicalSpecialtyPicker value={medicalSpecialty} onChange={setMedicalSpecialty} disabled={busy}/> : undefined} /> : null}
              {employee && (concurrent || simpleAllowance) && !cessation ? <section className="space-y-3 sm:col-span-2"><p className="text-xs">Проверьте предложенные формы ФИО в дательном падеже; их можно уточнить вручную.</p>{([['employee_full_name_dative_ru','ФИО в дательном падеже (RU)'],['employee_full_name_dative_kk','ФИО в дательном падеже (KK)']] as const).map(([key,label])=><Field key={key} label={label}><input aria-label={label} value={kk[key]} onChange={e=>{editedEmployeeDatives.current.add(key);setKk(current=>({...current,[key]:e.target.value}));}} className={inputClassName}/></Field>)}</section> : null}
              {employee && replacementMode ? <PersonnelOrderReplacementFields value={replacementFields} onChange={setReplacementFields} orgUnits={orgUnitOptions} mode={replacementMode} start={effective} fixedAllowance={optionalPlacement} serviceArea={serviceArea}/> : null}
              {employee && !recall && !transfer && !concurrent && !simpleAllowance && !categoryOrder && !serviceLengthOrder && !educationOrder && !personalDataOrder ? <details open={formsExpanded} onToggle={(event) => setFormsExpanded(event.currentTarget.open)} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700" data-testid="personnel-order-text-forms">
                <summary className="cursor-pointer text-sm font-medium">{formsComplete ? "Формы для текста приказа заполнены автоматически" : "Формы для текста приказа"}</summary>
              {periodLeave && missingFormLabels.length ? <p role="alert" className="mt-2 text-sm text-amber-800">Необходимо заполнить: {missingFormLabels.join(", ")}.</p> : null}
              {!kk.position_document_possessive_kk.trim() ? <p className="text-xs text-amber-700">В справочнике должности нет казахского названия или сохранённой документной формы. Заполните КК-должность вручную.</p> : <p className="text-xs text-zinc-500">Документные формы редактируемые; рассчитанную форму из названия справочника проверьте.</p>}
              <div className="mt-3 space-y-3">{([
                ["position_document_possessive_kk", "Должность в тексте приказа (KK)"],
                ["position_document_nominative_ru", "Должность в тексте приказа (RU)"],
                ["employee_full_name_dative_kk", "ФИО сотрудника в дательном падеже (KK)"],
                ["employee_full_name_genitive_kk", "ФИО сотрудника в родительном падеже (KK)"],
                ["employee_full_name_dative_ru", "ФИО сотрудника в дательном падеже (RU)"],
              ] as Array<[keyof Forms, string]>).map(([key, label]) => <Field key={key} label={label}><input aria-label={label} value={kk[key]} onChange={(event) => { if(type === "HIRE" && (key === "position_document_nominative_ru" || key === "position_document_possessive_kk"))setHirePositionManual(current=>({...current,[key === "position_document_nominative_ru"?"ru":"kk"]:Boolean(event.target.value.trim())})); editedPositionForms.current.add(key); setKk((value) => ({ ...value, [key]: event.target.value })); }} className={inputClassName} /></Field>)}</div>
              </details>
              : null}

            {recall ? <div className="grid w-full gap-3 sm:grid-cols-2">{([['recall_position_kk',sectionLanguage === 'kk' ? 'Лауазым KZ' : 'Должность KZ'],['basis_ru','Основание RU'],['basis_kk','Негіз KZ']] as const).map(([key,label]) => <Field key={key} label={label}><input aria-label={label} value={recallFields[key]} onChange={event => { recallEdited.current.add(key); setRecallFields(current => ({...current,[key]:event.target.value})); }} className={inputClassName} /></Field>)}</div> : null}
            {recall && linkedEmployee && !employee?.position?.job_namekk?.trim() && !employee?.position?.name_kk?.trim() ? <p data-testid="recall-position-kz-missing" className="text-xs text-amber-700">{sectionLanguage==='kk'?'Лауазым анықтамалығында қазақша атау жоқ. «Лауазым KZ» өрісін қолмен толтырыңыз.':'В справочнике должности нет казахского названия. Заполните «Должность KZ» вручную.'}</p> : null}
            {recall && employee && (!position || !org || !recallFields.recall_position_kk || !recallFields.recall_org_unit_kk)?<p className="text-xs text-amber-700">{sectionLanguage==='kk'?'Қызметкер карточкасында RU/KZ деректері толық емес. Бұйрық мәтіні үшін жетіспейтін атауларды енгізіңіз.':'В карточке сотрудника нет всех данных на RU/KZ. Заполните недостающие названия для текста приказа.'}</p>:null}
            {recall&&employee?<Field label="ФИО в тексте приказа (RU)"><input aria-label="ФИО в тексте приказа (RU)" value={recallName} onChange={event=>setRecallName(event.target.value)} className={inputClassName}/></Field>:null}
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
            {type === "HIRE" ? <PersonnelOrderHireTermsFields rate={hireTerms.employment_rate}
              onRateChange={employment_rate=>setHireTerms(current=>({...current,employment_rate}))}
              basis={hireBasis} onBasisChange={setHireBasis} disabled={busy}/> : null}
            {error ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-200">{error}</p> : null}
            {duplicateConflict ? <PersonnelOrderDuplicateActions duplicate={duplicateConflict} day={orderDate} /> : null}
            {createdOrder?<a className="text-sm text-blue-700 underline" href={`/directory/personnel/orders?order_id=${createdOrder.order_id}&tab=data`}>Открыть созданный приказ (ID {createdOrder.order_id})</a>:null}
          </div>
          <footer data-testid="personnel-order-create-footer" className="flex shrink-0 flex-col gap-3 border-t border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-950">
            {!canSubmit ? <div id="personnel-order-create-blockers" data-testid="personnel-order-create-blockers" role="status" className="max-h-36 overflow-y-auto text-sm text-amber-800 dark:text-amber-200">
              <p>{itemContext ? "Чтобы добавить пункт:" : sectionLanguage === 'kk' ? 'Бұйрықты жасау үшін:' : 'Чтобы создать приказ:'}</p>
              <ul className="list-disc pl-5">{blockedReasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
            </div> : null}
            <div className="flex justify-end gap-3">
            <button type="button" onClick={requestClose} disabled={busy} className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 shadow-sm hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">Отмена</button>

            <button type="submit" disabled={documentationViewer || !canSubmit} aria-describedby={!canSubmit ? 'personnel-order-create-blockers' : undefined} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-blue-300 dark:disabled:bg-blue-900">{busy ? (itemContext ? "Сохранение…" : "Создание…") : itemContext ? "Добавить пункт" : "Создать приказ"}</button>
            </div>
          </footer>
        </form>
      </section>
    </div>
  );
}
