"use client";

import * as React from "react";
import { useOrgUnitScopeOptions } from "@/lib/useOrgUnitScopeOptions";
import { usePersonnelOrderPositionOptions } from "@/lib/usePersonnelOrderPositionOptions";
import OrgScopeFilter from "@/components/OrgScopeFilter";
import { getActiveIntakeLink, getPersonnelApplication, issueIntakeLink, reissueIntakeLink, type PersonnelApplicationDetail } from "../_lib/personnelApplicationsApi.client";
import { canOpenApplicantIntakeReview, resolveIntakeDraftStatusDisplayLabel } from "../_lib/personnelApplicantWorkflow";
import { formatPersonnelApplicationDateTime } from "../_lib/personnelApplicationLabels";
import { candidateIntakePublicUrl } from "../_lib/candidateIntakePublicUrl";
import {
  checkElectronicHire, getHireUnitApprovalMode, recordHirePaperConfirmation, confirmElectronicHireIdentity, createElectronicHire, createElectronicHireOrderDraft, getElectronicHire, getElectronicHireIdentity,
  deleteElectronicHireApplication, getElectronicHireDeletePreview,
  getElectronicHireOrderPreview, getElectronicHireOrderReadiness,
  listElectronicHireApplications, printElectronicHire,
  retryElectronicHireNotification, searchFormerCandidates, sendElectronicHireLinkTelegram, updateElectronicHireConditions,
  updateElectronicHirePreliminaryName,
  uploadElectronicHireSignedCopy, getPositionReview, requestPositionReview,
  type CandidateNameParts, type ElectronicHireDeletePreview, type ElectronicHireIdentity, type ElectronicHireOrderPreview, type ElectronicHireOrderReadiness, type FormerCandidate, type PositionReview,
} from "../_lib/electronicHireApi.client";
import PersonnelApplicationIntakeOnBehalfDrawer from "./PersonnelApplicationIntakeOnBehalfDrawer";
import PersonnelApplicationIntakeLinkPanel from "./PersonnelApplicationIntakeLinkPanel";
import PersonnelApplicationIntakeMemo from "./PersonnelApplicationIntakeMemo";
import PersonnelApplicationIntakeReviewDrawer from "./PersonnelApplicationIntakeReviewDrawer";
import HiringDocumentChecklistActions from "./HiringDocumentChecklistActions";

type Props = { open: boolean; onClose: () => void; initialApplicationId?: number | null };
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const field = "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900";

function isMissingDeleteTarget(error: unknown): boolean {
  const response = error as {status?: number; details?: {detail?: {code?: string}}} | null;
  return response?.status === 404 && response.details?.detail?.code === "ELECTRONIC_HIRE_DELETE_CONFLICT";
}

function isMissingDeleteRoute(error: unknown): boolean {
  const response = error as {status?: number; details?: {detail?: unknown}} | null;
  return response?.status === 404 && response.details?.detail === "Not Found";
}

export default function ElectronicHireApplicationDrawer({ open, onClose, initialApplicationId = null }: Props) {
  const [query, setQuery] = React.useState("");
  const [matches, setMatches] = React.useState<FormerCandidate[]>([]);
  const [iin, setIin] = React.useState("");
  const [lastName, setLastName] = React.useState("");
  const [firstName, setFirstName] = React.useState("");
  const [middleName, setMiddleName] = React.useState("");
  const [legacyFullName, setLegacyFullName] = React.useState("");
  const [birthDate, setBirthDate] = React.useState("");
  const [received, setReceived] = React.useState(today);
  const [start, setStart] = React.useState(today);
  const [orgGroupId, setOrgGroupId] = React.useState<number | null>(null);
  const [unitId, setUnitId] = React.useState<number | null>(null);
  const [positionId, setPositionId] = React.useState<number | null>(null);
  const [manualPosition, setManualPosition] = React.useState(false);
  const [newPositionName, setNewPositionName] = React.useState("");
  const [newPositionDocumentRu, setNewPositionDocumentRu] = React.useState("");
  const [resolution, setResolution] = React.useState<"catalog" | "unmatched_manual" | "matched_manual">("catalog");
  const [review, setReview] = React.useState<PositionReview | null>(null);
  const [reviewExplanation, setReviewExplanation] = React.useState("");
  const [positionReloadKey, setPositionReloadKey] = React.useState(0);
  const [rate, setRate] = React.useState("1");
  const [applicationId, setApplicationId] = React.useState<number | null>(null);
  const [personId, setPersonId] = React.useState<number | null>(null);
  const [printText, setPrintText] = React.useState<Partial<Record<"ru" | "kk", string>> | null>(null);
  const [locale, setLocale] = React.useState<"ru" | "kk">("ru");
  const [checked, setChecked] = React.useState(false);
  const [identity, setIdentity] = React.useState<ElectronicHireIdentity | null>(null);
  const [documentChecked, setDocumentChecked] = React.useState(false);
  const [confirmReuse, setConfirmReuse] = React.useState(false);
  const [link, setLink] = React.useState("");
  const [intakeDetail, setIntakeDetail] = React.useState<PersonnelApplicationDetail | null>(null);
  const [intakeLinkDisplayState, setIntakeLinkDisplayState] = React.useState("not_issued");
  const [reviewOpen, setReviewOpen] = React.useState(false);
  const [assist, setAssist] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [uploaded, setUploaded] = React.useState("");
  const [existing, setExisting] = React.useState<Array<{application_id: number; full_name: string; status: string; personnel_order_id: number | null; order_number: string | null}>>([]);
  const [menuId, setMenuId] = React.useState<number | null>(null);
  const [deletePreview, setDeletePreview] = React.useState<ElectronicHireDeletePreview | null>(null);
  const [deleteBusy, setDeleteBusy] = React.useState(false);
  const [deleteRowError, setDeleteRowError] = React.useState<{id: number; message: string} | null>(null);
  const [existingNotice, setExistingNotice] = React.useState("");
  const [existingLoadError, setExistingLoadError] = React.useState("");
  const [existingReloadKey, setExistingReloadKey] = React.useState(0);
  const [orderId, setOrderId] = React.useState<number | null>(null);
  const [orderError, setOrderError] = React.useState("");
  const [hireNameAccusativeRu, setHireNameAccusativeRu] = React.useState("");
  const creatingOrder = React.useRef(false);
  const [orderPreview, setOrderPreview] = React.useState<ElectronicHireOrderPreview | null>(null);
  const [orderReadiness, setOrderReadiness] = React.useState<ElectronicHireOrderReadiness | null>(null);
  const [notification, setNotification] = React.useState("");
  const [approvalMode, setApprovalMode] = React.useState<"paper" | "electronic">("paper");
  const [targetMode, setTargetMode] = React.useState<"paper" | "electronic" | null>(null);
  const [savedUnitId, setSavedUnitId] = React.useState<number | null>(null);
  const [modeReason, setModeReason] = React.useState("");
  const [paperApprover, setPaperApprover] = React.useState("");
  const [paperDate, setPaperDate] = React.useState(today);
  const [paperNote, setPaperNote] = React.useState("");
  const [paperAttachmentId, setPaperAttachmentId] = React.useState<number | null>(null);
  const [paperResult, setPaperResult] = React.useState("");
  const [paperAttachmentHref, setPaperAttachmentHref] = React.useState("");
  const { options: units, catalogOptions: allUnits, loading: unitsLoading, error: unitsError } = useOrgUnitScopeOptions(orgGroupId, open);
  const unit = allUnits.find(row => row.unit_id === unitId);
  const validUnit = orgGroupId != null && unit?.group_id === orgGroupId;
  const { scopedOptions: positions, loading: positionsLoading, error: positionsError } = usePersonnelOrderPositionOptions({ enabled: open, orgUnitId: unitId, orgGroupId: unit?.group_id ?? null, allowedOnly: true, reloadKey: positionReloadKey });
  const positionValid = !positionsLoading && !positionsError && positions.some(row => row.id === positionId);
  const canSavePosition = validUnit && (manualPosition
    ? newPositionName.trim().length > 0 && newPositionDocumentRu.trim().length > 0
    : positionValid);
  const positionHint = manualPosition
    ? "Выбрано ручное название. Список должностей отключён; вернитесь к выбору из справочника при необходимости."
    : unitId == null
      ? "Сначала выберите отделение."
      : positionsLoading
        ? "Загружаем должности для выбранного отделения…"
        : positionsError
          ? positionsError
          : positions.length === 0
             ? "Для этого отделения в справочнике нет разрешённых или используемых должностей. Проверьте связи справочника."
            : null;

  function clearPositionForScopeChange() {
    setPositionId(null);
    setManualPosition(false);
    setNewPositionName("");
    setNewPositionDocumentRu("");
  }

  function selectOrgGroup(next: number | null) {
    if (next === orgGroupId) return;
    setOrgGroupId(next);
    setUnitId(null);
    clearPositionForScopeChange();
  }

  function selectOrgUnit(next: number | null) {
    if (next === unitId) return;
    setUnitId(next);
    clearPositionForScopeChange();
  }

  React.useEffect(() => {
    if (applicationId != null && unitId != null && !unitsLoading && unit?.group_id != null && orgGroupId !== unit.group_id) {
      setOrgGroupId(unit.group_id);
    }
  }, [applicationId, unitId, unitsLoading, unit, orgGroupId]);

  React.useEffect(() => {
    if (!manualPosition && positionId != null && unitId != null && !positionsLoading && !positionsError && !positions.some(row => row.id === positionId)) {
      setPositionId(null);
    }
  }, [manualPosition, positionId, unitId, positionsLoading, positionsError, positions]);

  React.useEffect(() => {
    if (!open || unitId == null) { setTargetMode(null); return; }
    let active = true;
    setTargetMode(null);
    void getHireUnitApprovalMode(unitId).then(result => { if (active) setTargetMode(result.approval_mode); })
      .catch(() => { if (active) { setTargetMode(null); setError("Не удалось получить порядок согласования отделения."); } });
    return () => { active = false; };
  }, [open, unitId]);

  React.useEffect(() => {
    if (!open) return;
    let active = true;
    setExistingLoadError("");
    setExistingNotice("");
    void listElectronicHireApplications()
      .then(result => { if (active) setExisting(result.items); })
      .catch((e: unknown) => { if (active) {
        const status = e && typeof e === "object" && "status" in e ? Number(e.status) : null;
        setExistingLoadError(status === 401 || status === 403
          ? "Не удалось загрузить заявления: проверьте вход и права доступа."
          : status != null && Number.isFinite(status)
            ? `Не удалось загрузить заявления: ошибка сервера (${status}).`
            : "Не удалось загрузить заявления: нет соединения с API. Проверьте сеть и повторите попытку.");
      } });
    return () => { active = false; };
  }, [open, existingReloadKey]);

  React.useEffect(() => {
    if (!open || query.trim().length < 2) { setMatches([]); return; }
    let active = true;
    const timer = window.setTimeout(() => { void searchFormerCandidates(query).then(result => { if (active) setMatches(result.items); }).catch(() => { if (active) setMatches([]); }); }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [open, query]);

  React.useEffect(() => {
    if (open && initialApplicationId != null) void openExisting(initialApplicationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialApplicationId]);

  if (!open) return null;
  const message = (e: unknown) => e instanceof Error ? e.message
    : e && typeof e === "object" && "message" in e && typeof e.message === "string"
      ? e.message : "Не удалось выполнить действие.";

  const deleteErrorMessage = (e: unknown) => isMissingDeleteRoute(e)
    ? "Маршрут удаления недоступен на сервере (404). Повторите попытку после обновления тестового стенда."
    : message(e);

  async function reconcileMissingDeleteTarget(id: number, error: unknown): Promise<boolean> {
    if (!isMissingDeleteTarget(error)) return false;
    try {
      const result = await listElectronicHireApplications();
      setExisting(result.items);
      if (result.items.some(row => row.application_id === id)) {
        setDeleteRowError({id, message: "Сервер не нашёл заявление, хотя оно есть в списке. Обновите страницу и повторите попытку."});
      } else {
        setDeleteRowError(null);
        setDeletePreview(null);
        setExistingNotice(`Заявление №${id} уже удалено. Список обновлён.`);
      }
    } catch (refreshError) {
      setDeleteRowError({id, message: `Заявление не найдено. Не удалось обновить список: ${message(refreshError)}`});
    }
    return true;
  }

  async function loadPrintText(id: number, preliminary = false) {
    const [ru, kk] = await Promise.allSettled([
      printElectronicHire(id, "ru", preliminary), printElectronicHire(id, "kk", preliminary),
    ]);
    const texts: Partial<Record<"ru" | "kk", string>> = {};
    if (ru.status === "fulfilled") texts.ru = ru.value.ru;
    if (kk.status === "fulfilled") texts.kk = kk.value.kk;
    setPrintText(texts);
    if (ru.status === "rejected" && kk.status === "rejected") setError(message(ru.reason));
  }

  async function refreshOrderReadiness(id: number) {
    setOrderReadiness(await getElectronicHireOrderReadiness(id));
  }

  async function refreshIntake(id: number) {
    const [detail, activeLink] = await Promise.all([
      getPersonnelApplication(id),
      getActiveIntakeLink(id),
    ]);
    setIntakeDetail(detail);
    setIntakeLinkDisplayState(activeLink.display_state);
    setLink(activeLink.intake_url_path || "");
    setIdentity(detail.intake_draft_status === "submitted"
      ? await getElectronicHireIdentity(id).catch(() => null) : null);
  }

  async function openExisting(id: number) {
    setBusy(true); setError(""); setPrintText(null); setOrderPreview(null); setOrderReadiness(null);
    setOrderError(""); setHireNameAccusativeRu("");
    try {
      const app = await getElectronicHire(id);
      setApplicationId(id); setPersonId(app.person_id == null ? null : Number(app.person_id));
      setIin(String(app.iin || ""));
      setLastName(String(app.preliminary_last_name || ""));
      setFirstName(String(app.preliminary_first_name || ""));
      setMiddleName(String(app.preliminary_middle_name || ""));
      setLegacyFullName(String(app.preliminary_full_name ||
        (!app.preliminary_last_name ? app.full_name || "" : "")));
      setBirthDate(String(app.preliminary_birth_date || ""));
      setReceived(String(app.application_received_at || "")); setStart(String(app.planned_start_date || ""));
      const savedUnitId = Number(app.intended_org_unit_id) || null;
      setUnitId(savedUnitId); setPositionId(Number(app.intended_position_id) || null);
      setOrgGroupId(allUnits.find(row => row.unit_id === savedUnitId)?.group_id ?? null);
      setManualPosition(app.position_resolution === "unmatched_manual");
      setResolution(app.position_resolution as typeof resolution);
      setReview((await getPositionReview(id).catch(() => ({request: null}))).request);
      setNewPositionName(String(app.manual_position_name || ""));
      setNewPositionDocumentRu(String(app.manual_position_document_ru || ""));
      setPositionReloadKey(key => key + 1);
      setSavedUnitId(Number(app.intended_org_unit_id) || null);
      setApprovalMode(app.approval_mode === "electronic" ? "electronic" : "paper");
      const paper = app.current_paper_confirmation as {is_current?: boolean; approver_name?: string; approved_on?: string;
        note?: string; recorded_by_name?: string; recorded_at?: string; attachment_id?: number} | null;
      setPaperResult(paper?.is_current ? `Согласовано на бумаге: ${paper.approver_name}, ${paper.approved_on}. Внёс: ${paper.recorded_by_name}, ${paper.recorded_at ? new Date(paper.recorded_at).toLocaleString("ru-RU", {timeZone: "Asia/Qyzylorda"}) : ""}. ${paper.note || ""}` : "");
      setPaperAttachmentHref(paper?.is_current && paper.attachment_id ? `/api/directory/electronic-hire/applications/${id}/signed-copy/${paper.attachment_id}` : "");
      setRate(String(app.intended_employment_rate || "1")); setChecked(Boolean(app.candidate_checked_at));
      setOrderId(Number(app.personnel_order_id) || null);
      const note = app.notification as {status?: string; last_error?: string | null} | null;
      setNotification(note?.last_error || note?.status || "");
      await refreshIntake(id);
      await loadPrintText(id, !app.candidate_checked_at);
      await refreshOrderReadiness(id);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function prepareDelete(id: number) {
    setMenuId(null); setDeleteRowError(null); setExistingNotice("");
    try {
      const preview = await getElectronicHireDeletePreview(id);
      if (preview.can_delete) setDeletePreview(preview);
      else setDeleteRowError({id, message: preview.reason || "Удаление заявления недоступно."});
    } catch (e) {
      if (!(await reconcileMissingDeleteTarget(id, e))) setDeleteRowError({id, message: deleteErrorMessage(e)});
    }
  }

  async function confirmDelete() {
    if (!deletePreview) return;
    setDeleteBusy(true);
    try {
      const result = await deleteElectronicHireApplication(deletePreview.application_id);
      setExisting(rows => rows.filter(row => row.application_id !== result.application_id));
      setDeletePreview(null);
      setExistingNotice("");
      setExistingReloadKey(key => key + 1);
    } catch (e) {
      if (!(await reconcileMissingDeleteTarget(deletePreview.application_id, e)))
        setDeleteRowError({id: deletePreview.application_id, message: deleteErrorMessage(e)});
      setDeletePreview(null);
    }
    finally { setDeleteBusy(false); }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (unitId == null || !canSavePosition) return;
    setBusy(true); setError("");
    setOrderError(""); setHireNameAccusativeRu("");
    try {
      const result = await createElectronicHire({ iin, last_name: lastName, first_name: firstName,
        middle_name: middleName, application_received_at: received,
        birth_date: birthDate || undefined,
        planned_start_date: start, org_unit_id: unitId,
        ...(manualPosition ? { manual_position_name: newPositionName.trim(), manual_position_document_ru: newPositionDocumentRu.trim() } : { position_id: positionId! }),
        employment_rate: Number(rate.replace(",", ".")), org_group_id: orgGroupId });
      setApplicationId(result.application_id); setPersonId(result.person_id); setPositionId(result.position_id);
      setManualPosition(result.position_resolution === "unmatched_manual");
      setResolution(result.position_resolution);
      setReview(null);
      setSavedUnitId(unitId); setApprovalMode(result.approval_mode);
      setPaperResult(""); setPaperAttachmentHref("");
      if (result.position_resolution !== "unmatched_manual") { setNewPositionName(""); setNewPositionDocumentRu(""); }
      setPositionReloadKey(key => key + 1);
      await loadPrintText(result.application_id, true);
      await refreshIntake(result.application_id);
      await refreshOrderReadiness(result.application_id);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function issue(reissue: boolean) {
    if (applicationId == null) return;
    setBusy(true); setError("");
    try {
      const result = reissue ? await reissueIntakeLink(applicationId) : await issueIntakeLink(applicationId);
      setLink(result.intake_url_path);
      await refreshIntake(applicationId);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function createOrder() {
    if (applicationId == null || orderId != null || creatingOrder.current) return;
    creatingOrder.current = true;
    setBusy(true); setOrderError("");
    try {
      const result = await createElectronicHireOrderDraft(applicationId, hireNameAccusativeRu);
      setOrderId(result.personnel_order_id);
      setNotification(result.notification.status === "paper" ? "Согласование на бумаге: электронная задача не создаётся" : result.notification.status);
      setOrderPreview(null);
    } catch (e) { setOrderError(message(e)); await refreshOrderReadiness(applicationId).catch(() => {}); }
    finally { creatingOrder.current = false; setBusy(false); }
  }

  async function previewOrder() {
    if (applicationId == null) return;
    setBusy(true); setError("");
    try { setOrderPreview(await getElectronicHireOrderPreview(applicationId)); }
    catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function confirmIdentity() {
    if (applicationId == null || !identity?.applicant_name_parts || !documentChecked) return;
    setBusy(true); setError("");
    try {
      const result = await confirmElectronicHireIdentity(applicationId, identity.applicant_name_parts, confirmReuse);
      setPersonId(result.person_id); setChecked(true); setDocumentChecked(false);
      await refreshIntake(applicationId);
      await loadPrintText(applicationId);
      await refreshOrderReadiness(applicationId);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function saveName() {
    if (applicationId == null || !lastName.trim() || !firstName.trim()) return;
    setBusy(true); setError("");
    try {
      const name: CandidateNameParts = {last_name: lastName, first_name: firstName, middle_name: middleName};
      const updated = await updateElectronicHirePreliminaryName(applicationId, name);
      setOrderPreview(null);
      setLastName(String(updated.preliminary_last_name || ""));
      setFirstName(String(updated.preliminary_first_name || ""));
      setMiddleName(String(updated.preliminary_middle_name || ""));
      await loadPrintText(applicationId, true);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function saveConditions() {
    if (applicationId == null || unitId == null || !canSavePosition) return;
    setBusy(true); setError("");
    try {
      const updated = await updateElectronicHireConditions(applicationId, {org_unit_id: unitId,
        ...(manualPosition ? { manual_position_name: newPositionName.trim(), manual_position_document_ru: newPositionDocumentRu.trim() } : { position_id: positionId! }),
        employment_rate: Number(rate.replace(",", ".")), planned_start_date: start,
        mode_change_reason: savedUnitId !== unitId ? modeReason : undefined});
      setSavedUnitId(unitId); setApprovalMode(updated.approval_mode); setModeReason(""); setPaperResult(""); setPaperAttachmentHref("");
      setPositionId(updated.intended_position_id);
      setManualPosition(updated.position_resolution === "unmatched_manual");
      setResolution(updated.position_resolution);
      setReview((await getPositionReview(applicationId).catch(() => ({request: null}))).request);
      setNewPositionName(updated.manual_position_name || "");
      setNewPositionDocumentRu(updated.manual_position_document_ru || "");
      setPositionReloadKey(key => key + 1);
      setOrderPreview(null); await loadPrintText(applicationId, !checked); setChecked(false); await refreshOrderReadiness(applicationId); setNotification(updated.approval_mode === "electronic" ? "Ожидает повторного согласования" : "Требуется новое бумажное подтверждение");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function confirmPaper() {
    if (applicationId == null) return;
    setBusy(true); setError("");
    try {
      const result = await recordHirePaperConfirmation(applicationId, {
        approver_name: paperApprover, approved_on: paperDate, note: paperNote,
        attachment_id: paperAttachmentId,
      }) as {approver_name: string; approved_on: string; recorded_by_user_id: number; recorded_at: string; attachment_id?: number};
      setPaperResult(`Согласовано на бумаге: ${result.approver_name}, ${result.approved_on}. Отметка внесена ${new Date(result.recorded_at).toLocaleString("ru-RU", {timeZone: "Asia/Qyzylorda"})}.`);
      setPaperAttachmentHref(result.attachment_id ? `/api/directory/electronic-hire/applications/${applicationId}/signed-copy/${result.attachment_id}` : "");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function sendPositionReview() {
    if (applicationId == null || !reviewExplanation.trim()) return;
    setBusy(true); setError("");
    try { setReview(await requestPositionReview(applicationId, reviewExplanation.trim())); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }

  const publicLink = candidateIntakePublicUrl(
    link,
    process.env.NEXT_PUBLIC_PERSONNEL_INTAKE_PUBLIC_BASE_URL,
    typeof window === "undefined" ? null : window.location.origin,
  );
  const canReviewIntake = intakeDetail && canOpenApplicantIntakeReview(intakeDetail);

  return <div className="fixed inset-0 z-50 flex justify-end bg-black/30" data-testid="electronic-hire-drawer">
    <aside className="h-full w-full max-w-2xl overflow-y-auto border-l border-zinc-200 bg-white p-6 text-zinc-900 shadow-xl">
      <div className="mb-5 flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold">Заявление о приёме на работу</h2><p className="text-sm text-zinc-600">Электронное заявление и планируемые условия приёма</p></div><button onClick={onClose} className="rounded border px-3 py-1">Закрыть</button></div>
      <div className="mb-4"><HiringDocumentChecklistActions testIdPrefix="electronic-hire" /></div>
      {error && <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {existingLoadError && <div role="alert" className="mb-4 rounded bg-red-50 p-3 text-sm text-red-800">{existingLoadError} <button type="button" className="underline" onClick={() => setExistingReloadKey(key => key + 1)}>Повторить загрузку</button></div>}
      {existingNotice && <div role="status" className="mb-4 rounded bg-blue-50 p-3 text-sm text-blue-900">{existingNotice}</div>}
      {applicationId == null ? <form onSubmit={create} className="space-y-4">
        {existing.length > 0 && <div className="rounded border bg-zinc-50 p-3 text-sm"><h3 className="mb-2 font-medium">Незавершённые заявления</h3><ul className="space-y-1">{existing.map(row => <li key={row.application_id} className="flex items-start justify-between gap-2"><div className="min-w-0"><button type="button" className="text-left underline" onClick={() => void openExisting(row.application_id)}>№{row.application_id} · {row.full_name}</button>{deleteRowError?.id === row.application_id && <p role="alert" className="mt-1 text-red-700">{deleteRowError.message}</p>}</div><div className="relative"><button type="button" aria-label={`Действия с заявлением №${row.application_id}`} aria-expanded={menuId === row.application_id} className="rounded px-2 py-1 hover:bg-zinc-200" onClick={() => setMenuId(menuId === row.application_id ? null : row.application_id)}>⋯</button>{menuId === row.application_id && <div className="absolute right-0 z-10 rounded border bg-white p-1 shadow"><button type="button" className="whitespace-nowrap rounded px-3 py-1 text-red-700 hover:bg-red-50" onClick={() => void prepareDelete(row.application_id)}>Удалить</button></div>}</div></li>)}</ul></div>}
        {deletePreview && <div role="dialog" aria-modal="true" aria-label="Подтверждение удаления заявления" className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"><div className="max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded border border-amber-300 bg-amber-50 p-4 text-sm text-zinc-900 shadow-2xl"><h3 className="font-semibold">Окончательно удалить заявление №{deletePreview.application_id}?</h3><p>{deletePreview.full_name}</p>{deletePreview.personnel_order_id ? <p>Будут окончательно удалены обе записи: заявление №{deletePreview.application_id} и черновик приказа {deletePreview.order_number || `ID ${deletePreview.personnel_order_id}`} (ID {deletePreview.personnel_order_id}).</p> : <p>Заявление будет окончательно удалено.</p>}<p>Публичная ссылка кандидата перестанет работать. Восстановить удалённые записи нельзя.</p><div className="mt-3 flex gap-2"><button type="button" disabled={deleteBusy} className="rounded bg-red-700 px-3 py-1 text-white disabled:opacity-50" onClick={() => void confirmDelete()}>Подтвердить удаление</button><button type="button" className="rounded border px-3 py-1" onClick={() => setDeletePreview(null)}>Отмена</button></div></div></div>}
        <label className="block text-sm">Поиск среди ранее уволенных<input className={field} value={query} onChange={e => setQuery(e.target.value)} placeholder="ФИО или ИИН" /></label>
        {matches.length > 0 && <ul className="rounded border p-2">{matches.map(row => <li key={row.person_id}><button type="button" className="w-full rounded px-2 py-1 text-left hover:bg-zinc-100" onClick={() => {
          const structured = Boolean(row.last_name?.trim() && row.first_name?.trim());
          setIin(row.iin); setLastName(structured ? row.last_name || "" : "");
          setFirstName(structured ? row.first_name || "" : "");
          setMiddleName(structured ? row.middle_name || "" : "");
          setLegacyFullName(structured ? "" : row.full_name);
          setMatches([]); setQuery(row.full_name);
        }}>{row.full_name} · {row.iin}</button></li>)}</ul>}
        <label className="block text-sm">ИИН (если известен)<input inputMode="numeric" pattern="[0-9]{12}" maxLength={12} className={field} value={iin} onChange={e => setIin(e.target.value)} /></label>
        {legacyFullName && <p className="rounded border bg-zinc-50 p-3 text-sm">ФИО в прежней карточке: {legacyFullName}. Заполните поля ниже по документу.</p>}
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">Фамилия<input required className={field} value={lastName} onChange={e => setLastName(e.target.value)} /></label>
          <label className="text-sm">Имя<input required className={field} value={firstName} onChange={e => setFirstName(e.target.value)} /></label>
          <label className="text-sm">Отчество (если есть)<input className={field} value={middleName} onChange={e => setMiddleName(e.target.value)} /></label>
        </div>
        <label className="block text-sm">Дата рождения<input type="date" className={field} value={birthDate} onChange={e => setBirthDate(e.target.value)} /></label>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Дата заявления<input type="date" required className={field} value={received} onChange={e => setReceived(e.target.value)} /></label><label className="text-sm">Планируемая дата начала работы<input type="date" required className={field} value={start} onChange={e => setStart(e.target.value)} /></label></div>
        <OrgScopeFilter basePath="/directory/personnel/orders" label="Группа отделений" emptyLabel="Выберите группу отделений" value={orgGroupId} onChange={selectOrgGroup} />
        <label className="block text-sm">Отделение<select required disabled={orgGroupId == null || unitsLoading || !!unitsError} className={field} value={validUnit ? unitId ?? "" : ""} onChange={e => selectOrgUnit(Number(e.target.value) || null)}><option value="">{orgGroupId == null ? "Сначала выберите группу отделений" : unitsLoading ? "Загрузка отделений…" : unitsError ? "Ошибка загрузки отделений" : "Выберите отделение"}</option>{units.map(row => <option key={row.unit_id} value={row.unit_id}>{row.name}</option>)}</select></label>
        {orgGroupId == null && <p role="status" className="text-sm text-zinc-600">Отделение станет доступно после выбора группы отделений.</p>}
        {unitsError && <p role="alert" className="text-sm text-red-700">{unitsError}</p>}
        {unitId && <p className="rounded bg-blue-50 p-2 text-sm">{targetMode === null ? "Загрузка порядка согласования…" : targetMode === "electronic" ? "Требуется электронное согласование" : "Согласование на бумаге"}</p>}
        <label className="block text-sm">Должность<select required={!manualPosition} disabled={manualPosition || unitId == null || positionsLoading || !!positionsError || positions.length === 0} className={field} value={positionValid ? positionId ?? "" : ""} onChange={e => setPositionId(Number(e.target.value) || null)}><option value="">{unitId == null ? "Сначала выберите отделение" : positionsLoading ? "Загрузка должностей…" : positionsError ? "Ошибка загрузки должностей" : positions.length === 0 ? "Нет доступных должностей" : "Выберите должность"}</option>{positions.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
        {positionHint && <p role={positionsError && !manualPosition ? "alert" : "status"} className={`text-sm ${positionsError && !manualPosition ? "text-red-700" : "text-amber-800"}`}>{positionHint}</p>}
        {positionsError && !manualPosition && <button type="button" className="text-sm underline" onClick={() => setPositionReloadKey(key => key + 1)}>Повторить загрузку должностей</button>}
        <button type="button" className="text-sm underline" onClick={() => setManualPosition(value => !value)}>{manualPosition ? "Выбрать должность из списка" : "Нет подходящей должности? Ввести вручную"}</button>
        {manualPosition && <label className="block text-sm">Название должности вручную<input required maxLength={500} className={field} value={newPositionName} onChange={e => setNewPositionName(e.target.value)} /></label>}
        {manualPosition && <p className="text-xs text-zinc-600">Название сохранится в этом заявлении без связи со справочником должностей.</p>}
        {manualPosition && <label className="block text-sm">После «на должность» (для текста заявления)<input required maxLength={500} className={field} value={newPositionDocumentRu} onChange={e => setNewPositionDocumentRu(e.target.value)} placeholder="Например: старшего специалиста" /></label>}
        <label className="block text-sm">Ставка<input required type="number" step="0.01" min="0.01" max="2" className={field} value={rate} onChange={e => setRate(e.target.value)} /></label>
        <button disabled={busy || !canSavePosition || targetMode === null} className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Сохранить черновик заявления</button>
      </form> : <div className="space-y-5">
        <p className="rounded bg-emerald-50 p-3 text-sm text-emerald-800">Черновик заявления №{applicationId} сохранён. {personId ? `Личная карточка: ${personId}.` : "Личная карточка появится после проверки личности."}</p>
        <p className="rounded bg-blue-50 p-3 text-sm">Порядок заявления: {approvalMode === "electronic" ? "электронное согласование" : "согласование на бумаге"}</p>
        {(!checked && !orderId || legacyFullName) && <section className="space-y-2 rounded border p-3 text-sm" data-testid="electronic-hire-preliminary-name">
          {legacyFullName && <p>Ранее сохранённое ФИО: {legacyFullName}. Поля ниже заполняются вручную без разбора этой строки.</p>}
          {!checked && !orderId && <>
            <div className="grid gap-3 sm:grid-cols-3">
              <label>Фамилия<input className={field} value={lastName} onChange={e => setLastName(e.target.value)} /></label>
              <label>Имя<input className={field} value={firstName} onChange={e => setFirstName(e.target.value)} /></label>
              <label>Отчество (если есть)<input className={field} value={middleName} onChange={e => setMiddleName(e.target.value)} /></label>
            </div>
            <button type="button" disabled={busy || !lastName.trim() || !firstName.trim()} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => void saveName()}>Сохранить ФИО</button>
          </>}
        </section>}
        {resolution === "unmatched_manual" && <section className="rounded-lg border-2 border-amber-500 bg-amber-50 p-4 text-sm text-amber-950" role="status">
          <h3 className="font-semibold">Должность требует сопоставления со справочником</h3>
          <p className="mt-1">Исходное название: {newPositionName}. Заявление и черновик доступны; подписание, регистрация и применение приказа ожидают решения.</p>
          {review ? <p className="mt-2">Запрос №{review.request_id}: {review.status === "open" ? "ожидает решения" : "решён"}. Автор: {review.requester_name}. <a className="underline" href={`/directory/personnel/position-reconciliation?request_id=${review.request_id}`}>Открыть запрос</a></p>
            : <div className="mt-3"><label className="block">Пояснение для ответственного за справочник<textarea className={field} value={reviewExplanation} onChange={e => setReviewExplanation(e.target.value)} maxLength={2000} /></label><button type="button" disabled={busy || !reviewExplanation.trim()} className="mt-2 rounded bg-amber-800 px-3 py-2 text-white disabled:opacity-50" onClick={() => void sendPositionReview()}>Отправить на уточнение</button></div>}
        </section>}
        {resolution === "matched_manual" && review?.status === "resolved" && <section className="rounded-lg border border-emerald-400 bg-emerald-50 p-4 text-sm" role="status">
          <h3 className="font-semibold">Должность сопоставлена</h3>
          <p>Исходное название: {review.source_title}. Решение: {review.resolved_position_name} / {review.resolved_position_name_kk}. Принял: {review.decider_name}, {review.decided_at ? new Date(review.decided_at).toLocaleString("ru-RU") : ""}.</p>
          <p>Проверьте текст приказа RU/KK и повторное согласование. Исходное заявление сохранено.</p>
          <a className="underline" href={`/directory/personnel/position-reconciliation?request_id=${review.request_id}`}>Показать историю и изменения</a>
        </section>}
        <details className="rounded border p-3"><summary className="cursor-pointer font-medium">Изменить условия приёма</summary><div className="mt-3 space-y-3">
          <OrgScopeFilter basePath="/directory/personnel/orders" label="Группа отделений" emptyLabel="Выберите группу отделений" value={orgGroupId} onChange={selectOrgGroup} />
          <label className="block text-sm">Отделение<select disabled={orgGroupId == null || unitsLoading || !!unitsError} className={field} value={validUnit ? unitId ?? "" : ""} onChange={e => selectOrgUnit(Number(e.target.value) || null)}><option value="">{orgGroupId == null ? "Сначала выберите группу отделений" : unitsLoading ? "Загрузка отделений…" : unitsError ? "Ошибка загрузки отделений" : "Выберите отделение"}</option>{units.map(row => <option key={row.unit_id} value={row.unit_id}>{row.name}</option>)}</select></label>
          {orgGroupId == null && <p role="status" className="text-sm text-zinc-600">Отделение станет доступно после выбора группы отделений.</p>}
          {unitsError && <p role="alert" className="text-sm text-red-700">{unitsError}</p>}
          {savedUnitId !== unitId && <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm"><p>При смене отделения порядок согласования будет обновлён: {targetMode === null ? "загрузка…" : targetMode === "electronic" ? "электронный" : "бумажный"}.</p><label className="block">Причина смены отделения<input className={field} value={modeReason} onChange={e => setModeReason(e.target.value)} /></label></div>}
          <label className="block text-sm">Должность<select disabled={manualPosition || unitId == null || positionsLoading || !!positionsError || positions.length === 0} className={field} value={positionValid ? positionId ?? "" : ""} onChange={e => setPositionId(Number(e.target.value) || null)}><option value="">{unitId == null ? "Сначала выберите отделение" : positionsLoading ? "Загрузка должностей…" : positionsError ? "Ошибка загрузки должностей" : positions.length === 0 ? "Нет доступных должностей" : "Выберите должность"}</option>{positions.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
          {positionHint && <p role={positionsError && !manualPosition ? "alert" : "status"} className={`text-sm ${positionsError && !manualPosition ? "text-red-700" : "text-amber-800"}`}>{positionHint}</p>}
          {positionsError && !manualPosition && <button type="button" className="text-sm underline" onClick={() => setPositionReloadKey(key => key + 1)}>Повторить загрузку должностей</button>}
          <button type="button" className="text-sm underline" onClick={() => setManualPosition(value => !value)}>{manualPosition ? "Выбрать должность из списка" : "Нет подходящей должности? Ввести вручную"}</button>
          {manualPosition && <label className="block text-sm">Название должности вручную<input maxLength={500} className={field} value={newPositionName} onChange={e => setNewPositionName(e.target.value)} /></label>}
          {manualPosition && <p className="text-xs text-zinc-600">Название сохранится в этом заявлении без связи со справочником должностей.</p>}
          {manualPosition && <label className="block text-sm">После «на должность» (для текста заявления)<input maxLength={500} className={field} value={newPositionDocumentRu} onChange={e => setNewPositionDocumentRu(e.target.value)} placeholder="Например: старшего специалиста" /></label>}
          <div className="grid gap-2 sm:grid-cols-2"><label className="text-sm">Ставка<input className={field} type="number" min="0.01" max="2" step="0.01" value={rate} onChange={e => setRate(e.target.value)} /></label><label className="text-sm">Планируемая дата начала работы<input className={field} type="date" value={start} onChange={e => setStart(e.target.value)} /></label></div>
          <button disabled={busy || !canSavePosition || (savedUnitId !== unitId && (targetMode === null || !modeReason.trim()))} className="rounded border px-3 py-2 text-sm" onClick={() => void saveConditions()}>Сохранить условия</button>
        </div></details>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Язык заявления">
          {(["ru", "kk"] as const).map(language => (
            <button key={language} type="button" onClick={() => setLocale(language)} aria-pressed={locale === language}
              className={`rounded px-3 py-2 text-sm ${locale === language ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "border text-zinc-600 dark:text-zinc-300"}`}>
              {language === "ru" ? "Русский" : "Қазақша"}
            </button>
          ))}
          <button type="button" className="rounded border px-3 py-2" onClick={() => { void loadPrintText(applicationId, !checked); }}>{checked ? "Обновить после исправлений в ЛК" : "Обновить предварительный текст"}</button>
        </div>
        {!checked && <p className="text-sm text-amber-800">Предварительный текст по сведениям кадровика. После проверки личности ФИО обновится из личной карточки.</p>}
        {printText?.[locale] && <pre className="whitespace-pre-wrap rounded border bg-zinc-50 p-5 font-serif text-base leading-7">{printText[locale]}</pre>}
        {checked && <p className="text-sm text-emerald-700">Личность подтверждена кадровиком по документу.</p>}
        <label className="block text-sm">Подписанное бумажное заявление (PDF или фото)<input type="file" accept="application/pdf,image/jpeg,image/png" className="mt-1 block" onChange={e => { const file = e.target.files?.[0]; if (file) void uploadElectronicHireSignedCopy(applicationId, file).then(r => setUploaded(r.file_name)).catch(err => setError(message(err))); }} /></label>
        {uploaded && <p className="text-sm text-emerald-700">Прикреплено: {uploaded}</p>}
        {approvalMode === "paper" && <section className="space-y-2 rounded border p-3 text-sm">
          <h3 className="font-semibold">Подтверждение бумажного согласования</h3>
          {paperResult ? <p className="rounded bg-emerald-50 p-2 text-emerald-800">{paperResult}</p> : <>
            <label className="block">Кто согласовал<input className={field} value={paperApprover} onChange={e => setPaperApprover(e.target.value)} /></label>
            <label className="block">Дата согласования<input type="date" className={field} value={paperDate} onChange={e => setPaperDate(e.target.value)} /></label>
            <label className="block">Примечание<textarea className={field} value={paperNote} onChange={e => setPaperNote(e.target.value)} /></label>
            <label className="block">Скан или фото согласования (необязательно)<input type="file" accept="application/pdf,image/jpeg,image/png"
              onChange={e => { const file = e.target.files?.[0]; if (file) void uploadElectronicHireSignedCopy(applicationId, file)
                .then(r => { setPaperAttachmentId(r.attachment_id); setUploaded(r.file_name); }).catch(err => setError(message(err))); }} /></label>
            <button disabled={busy || !paperApprover.trim()} className="rounded bg-emerald-700 px-3 py-2 text-white disabled:opacity-50" onClick={() => void confirmPaper()}>Сохранить подтверждение</button>
          </>}
          {paperAttachmentHref && <a className="text-blue-700 underline" href={paperAttachmentHref} target="_blank" rel="noreferrer">Открыть скан согласования</a>}
        </section>}
        <PersonnelApplicationIntakeMemo />
        <div className="flex flex-wrap gap-2">{personId && <a className="rounded bg-zinc-900 px-3 py-2 text-sm text-white" href={`/directory/personnel/persons/${personId}/card`} target="_blank" rel="noreferrer">Открыть ЛК</a>}<button className="rounded border px-3 py-2 text-sm" onClick={() => setAssist(true)}>Заполнить с кадровиком</button><button className="rounded border px-3 py-2 text-sm" data-testid="electronic-hire-intake-issue" disabled={busy || intakeLinkDisplayState === "active"} onClick={() => void issue(false)}>Выдать ссылку на 24 часа</button></div>
        {link && <PersonnelApplicationIntakeLinkPanel intakeUrlPath={link} publicUrl={publicLink} copyButtonLabel="Скопировать ссылку кандидата" actionsDisabled={busy || intakeLinkDisplayState !== "active"} />}
        {intakeLinkDisplayState === "active" && <button className="text-sm underline" disabled={busy} onClick={() => void issue(true)}>Перевыпустить ссылку</button>}
        <div className="rounded border p-3 text-sm" data-testid="electronic-hire-intake-status">
          <p>Статус анкеты: {intakeDetail ? resolveIntakeDraftStatusDisplayLabel({draftStatus: intakeDetail.intake_draft_status, applicationStatus: intakeDetail.status, submittedAt: intakeDetail.intake_submitted_at}) : "Не загружен"}</p>
          <p>Дата отправки: {formatPersonnelApplicationDateTime(intakeDetail?.intake_submitted_at)}</p>
          <button className="mt-2 underline" data-testid="electronic-hire-intake-refresh" disabled={busy} onClick={() => void refreshIntake(applicationId).catch(e => setError(message(e)))}>Обновить статус анкеты</button>
          {canReviewIntake && <button className="ml-3 rounded border px-3 py-1" data-testid="electronic-hire-intake-review" onClick={() => setReviewOpen(true)}>Проверить анкету</button>}
        </div>
        {identity && <section className="space-y-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="electronic-hire-identity-review">
          <h3 className="font-semibold">Проверка личности по документу</h3>
          {identity.legacy_full_name && <p>Ранее сохранённое ФИО целиком: {identity.legacy_full_name}</p>}
          {identity.applicant_name_parts && ([
            ["last_name", "Фамилия"], ["first_name", "Имя"], ["middle_name", "Отчество"],
          ] as const).map(([key, label]) => <p key={key} className={identity.name_differences?.includes(key) ? "font-medium text-amber-900" : ""}>
            {label}: предварительно — {identity.preliminary_name_parts[key] || "не указано"}; в анкете — {identity.applicant_name_parts?.[key] || "не указано"}
            {identity.name_differences?.includes(key) ? " · отличается" : ""}
          </p>)}
          {identity.applicant_full_name && <p>ИИН: {identity.iin} · Дата рождения: {identity.birth_date}</p>}
          {identity.status === "former" && <p>Найдена прежняя карточка №{identity.existing_person_id}: {identity.existing_full_name}.</p>}
          {identity.status === "blocked" && <p role="alert" className="text-red-700">{identity.reason}</p>}
          {!identity.confirmed && identity.status !== "blocked" && <>
            <label className="flex gap-2"><input type="checkbox" checked={documentChecked} onChange={e => setDocumentChecked(e.target.checked)} />Сведения сверены с документом</label>
            {identity.status === "former" && <label className="flex gap-2"><input type="checkbox" checked={confirmReuse} onChange={e => setConfirmReuse(e.target.checked)} />Подтвердить привязку к прежней карточке</label>}
            <button type="button" className="rounded bg-blue-700 px-3 py-2 text-white disabled:opacity-50" disabled={busy || !documentChecked || (identity.status === "former" && !confirmReuse)} onClick={() => void confirmIdentity()}>Подтвердить личность</button>
          </>}
        </section>}
        {link && intakeLinkDisplayState === "active" && <button className="rounded border px-3 py-2 text-sm" onClick={() => { void sendElectronicHireLinkTelegram(applicationId).then(result => setNotification(result.status === "sent" ? "Ссылка отправлена кандидату" : result.last_error || "Доставка не удалась")).catch(e => setError(message(e))); }}>Отправить ссылку через Telegram</button>}
        <div className="border-t pt-4 space-y-3">
          <button type="button" disabled={busy} className="rounded border px-4 py-2 text-sm disabled:opacity-50" onClick={() => void previewOrder()}>Предпросмотр приказа</button>
          {orderPreview && <section className="space-y-2 rounded border p-3 text-sm" data-testid="electronic-hire-order-preview">
            <p className="font-medium">Предпросмотр · приказ не создан.{!checked ? " ФИО предварительное, личность ещё не проверена." : " ФИО взято из личной карточки."}</p>
            <h3 className="font-semibold">{orderPreview[locale].title}</h3>
            <p>{orderPreview[locale].preamble}</p>
            <p className="whitespace-pre-wrap">{orderPreview[locale].body}</p>
            <p className="whitespace-pre-wrap">{orderPreview[locale].basis}</p>
          </section>}
          {orderReadiness && !orderReadiness.ready && <div className="text-sm text-amber-800" data-testid="electronic-hire-order-readiness">
            <p className="font-medium">Для сохранения черновика приказа:</p>
            <ul className="list-disc pl-5">{orderReadiness.missing_steps.map(step => <li key={step}>{step}</li>)}</ul>
          </div>}
          {orderId == null && <label className="block text-sm">ФИО в винительном падеже RU для приказа (при необходимости уточните вручную)
            <input className={field + " mt-1"} value={hireNameAccusativeRu} onChange={e => setHireNameAccusativeRu(e.target.value)} placeholder="Кого принять на работу" />
          </label>}
          {orderId == null
            ? <button type="button" disabled={busy || !orderReadiness?.ready} className="rounded bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-50" onClick={() => void createOrder()}>Сформировать черновик приказа</button>
            : <a className="inline-block rounded bg-zinc-900 px-4 py-2 text-sm text-white" href={`/directory/personnel/orders?order_id=${orderId}`}>Открыть черновик приказа</a>}
          {orderError && <p role="alert" className="mt-2 text-sm text-red-700">{orderError}</p>}
          {orderId && <p className="mt-2 text-sm">Проект приказа №{orderId}</p>}
          {notification && <p className="mt-2 text-sm">Уведомление: {notification}</p>}
          {approvalMode === "electronic" && orderId && notification !== "sent" && <button className="mt-2 text-sm underline" onClick={() => { void retryElectronicHireNotification(applicationId).then(r => setNotification(r.status === "sent" ? "sent" : r.last_error || r.status)).catch(e => setError(message(e))); }}>Повторить отправку руководителю</button>}
        </div>
      </div>}
    </aside>
    <PersonnelApplicationIntakeOnBehalfDrawer applicationId={applicationId} open={assist} onClose={() => setAssist(false)} onSaved={() => { if (applicationId != null) void refreshIntake(applicationId); }} />
    <PersonnelApplicationIntakeReviewDrawer applicationId={applicationId} open={reviewOpen} onClose={() => { setReviewOpen(false); if (applicationId != null) { void refreshIntake(applicationId); void refreshOrderReadiness(applicationId); } }} onTransferred={() => { if (applicationId != null) { void refreshIntake(applicationId); void refreshOrderReadiness(applicationId); void loadPrintText(applicationId); } }} />
  </div>;
}
