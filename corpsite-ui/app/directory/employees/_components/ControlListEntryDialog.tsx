"use client";

import * as React from "react";
import Link from "next/link";

import { buildEmployeeCardHref } from "@/lib/employeeCardNav";
import { getEmployees, mapApiErrorToMessage } from "../_lib/api.client";
import type { EmployeeDTO } from "../_lib/types";
import ControlListProfilePreviewDialog from "./ControlListProfilePreviewDialog";
import ImportEnrollEmployeeWizard from "../../personnel/_components/ImportEnrollEmployeeWizard";
import {
  getEducationProfileDetail,
  getNormalizedRecord,
  listEducationProfiles,
  listNormalizedRecords,
  mapImportApiError,
  type EducationProfileDetail,
  type NormalizedRecord,
} from "../../personnel/_lib/importApi.client";

type Props = { open: boolean; onClose: () => void; onEnrolled?: () => void };

type ControlListPerson = {
  key: string;
  fullName: string;
  iin: string;
  records: NormalizedRecord[];
  importIds: number[];
};

type ImportProfileOption = {
  key: string;
  batchId: number;
  profileId: number;
  department: string;
  position: string;
  rowIds: number[];
  record: NormalizedRecord;
};

function groupControlListPeople(records: NormalizedRecord[]): ControlListPerson[] {
  const people = new Map<string, ControlListPerson>();
  for (const record of records) {
    const iin = record.iin.trim();
    const key = iin ? `iin:${iin}` : `record:${record.normalized_record_id}`;
    const current = people.get(key);
    if (current) {
      current.records.push(record);
      if (!current.importIds.includes(record.batch_id)) current.importIds.push(record.batch_id);
      continue;
    }
    people.set(key, {
      key,
      fullName: record.full_name || "—",
      iin,
      records: [record],
      importIds: [record.batch_id],
    });
  }
  return [...people.values()];
}

export default function ControlListEntryDialog({ open, onClose, onEnrolled }: Props) {
  const [surname, setSurname] = React.useState("");
  const [items, setItems] = React.useState<EmployeeDTO[] | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [people, setPeople] = React.useState<ControlListPerson[] | null>(null);
  const [controlListLoading, setControlListLoading] = React.useState(false);
  const [selectedPerson, setSelectedPerson] = React.useState<ControlListPerson | null>(null);
  const [profileOptions, setProfileOptions] = React.useState<ImportProfileOption[] | null>(null);
  const [profileSelection, setProfileSelection] = React.useState<ImportProfileOption | null>(null);
  const [profileLoading, setProfileLoading] = React.useState(false);
  const [profilePreview, setProfilePreview] = React.useState<EducationProfileDetail | null>(null);
  const requestIdRef = React.useRef(0);
  const previewRequestIdRef = React.useRef(0);
  const profileSelectionKeyRef = React.useRef<string | null>(null);

  const invalidateProfilePreview = React.useCallback(() => {
    previewRequestIdRef.current += 1;
    setProfilePreview(null);
  }, []);

  const handleProfileSelectionChange = React.useCallback((option: ImportProfileOption | null) => {
    invalidateProfilePreview();
    profileSelectionKeyRef.current = option?.key ?? null;
    setProfileSelection(option);
  }, [invalidateProfilePreview]);

  React.useEffect(() => {
    profileSelectionKeyRef.current = profileSelection?.key ?? null;
  }, [profileSelection]);

  const handleClose = React.useCallback(() => {
    requestIdRef.current += 1;
    onClose();
  }, [onClose]);

  React.useEffect(() => {
    if (!open) return;
    requestIdRef.current += 1;
    setSurname("");
    setItems(null);
    setError(null);
    setPeople(null);
    setSelectedPerson(null);
    setProfileOptions(null);
    handleProfileSelectionChange(null);
  }, [open, handleProfileSelectionChange]);

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && open) handleClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, handleClose]);

  if (!open) return null;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const q = surname.trim();
    if (!q) return;
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    setItems(null);
    setPeople(null);
    setSelectedPerson(null);
    setProfileOptions(null);
    handleProfileSelectionChange(null);
    try {
      const response = await getEmployees({ status: "active", q, include_applicants: false });
      if (requestId === requestIdRef.current) setItems(response.items ?? []);
    } catch (cause) {
      if (requestId === requestIdRef.current) setError(mapApiErrorToMessage(cause));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }

  async function searchControlList() {
    const q = surname.trim();
    if (!q) return;
    const requestId = ++requestIdRef.current;
    setControlListLoading(true);
    setError(null);
    setPeople(null);
    setSelectedPerson(null);
    setProfileOptions(null);
    handleProfileSelectionChange(null);
    try {
      const response = await listNormalizedRecords({ q_name: q, limit: 50 });
      if (requestId === requestIdRef.current) setPeople(groupControlListPeople(response.items ?? []));
    } catch (cause) {
      if (requestId === requestIdRef.current) setError(mapImportApiError(cause));
    } finally {
      if (requestId === requestIdRef.current) setControlListLoading(false);
    }
  }

  async function selectPerson(person: ControlListPerson) {
    const requestId = ++requestIdRef.current;
    setSelectedPerson(person);
    setProfileOptions(null);
    handleProfileSelectionChange(null);
    setProfileLoading(true);
    setError(null);
    try {
      const records = await Promise.all(person.records.map((record) => getNormalizedRecord(record.normalized_record_id)));
      if (requestId !== requestIdRef.current) return;
      const profilesByBatch = new Map<number, Awaited<ReturnType<typeof listEducationProfiles>>>();
      await Promise.all(
        [...new Set(records.map((record) => record.batch_id))].map(async (batchId) => {
          profilesByBatch.set(batchId, await listEducationProfiles(batchId, { q_name: surname.trim(), limit: 100 }));
        }),
      );
      if (requestId !== requestIdRef.current) return;
      const options = new Map<string, ImportProfileOption>();
      for (const record of records) {
        const matches = (profilesByBatch.get(record.batch_id)?.items ?? []).filter((profile) =>
          (profile.source_row_ids ?? []).includes(record.row_id),
        );
        if (matches.length !== 1) continue;
        const profile = matches[0];
        const key = `${record.batch_id}:${profile.profile_id}`;
        const existing = options.get(key);
        if (existing) {
          if (!existing.rowIds.includes(record.row_id)) existing.rowIds.push(record.row_id);
          continue;
        }
        options.set(key, {
          key,
          batchId: record.batch_id,
          profileId: profile.profile_id,
          department: profile.org_unit_name || profile.department_source || "",
          position: profile.position_raw || "",
          rowIds: [record.row_id],
          record,
        });
      }
      const next = [...options.values()];
      if (requestId !== requestIdRef.current) return;
      setProfileOptions(next);
      if (next.length === 1) handleProfileSelectionChange(next[0]);
    } catch (cause) {
      if (requestId === requestIdRef.current) setError(mapImportApiError(cause));
    } finally {
      if (requestId === requestIdRef.current) setProfileLoading(false);
    }
  }

  async function openSelectedProfile() {
    if (!profileSelection) return;
    const requestedKey = profileSelection.key;
    const previewRequestId = ++previewRequestIdRef.current;
    setProfileLoading(true);
    setError(null);
    setProfilePreview(null);
    try {
      const detail = await getEducationProfileDetail(profileSelection.batchId, profileSelection.profileId);
      if (previewRequestId !== previewRequestIdRef.current) return;
      if (profileSelectionKeyRef.current !== requestedKey) return;
      setProfilePreview(detail);
    } catch (cause) {
      if (previewRequestId !== previewRequestIdRef.current) return;
      setError(mapImportApiError(cause));
    } finally {
      if (previewRequestId === previewRequestIdRef.current) setProfileLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden p-4">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50" onClick={handleClose} />
      <section role="dialog" aria-modal="true" aria-labelledby="control-list-entry-title" className="relative flex max-h-[calc(100dvh-2rem)] w-full min-w-0 max-w-2xl flex-col overflow-y-auto overscroll-contain rounded-2xl border border-zinc-200 bg-white p-5 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="sticky top-0 z-10 flex shrink-0 items-start justify-between gap-4 bg-white pb-3 dark:bg-zinc-950">
          <div><h2 id="control-list-entry-title" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Из контр. списка</h2><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Сначала проверьте, есть ли действующий сотрудник в оперативном контуре.</p></div>
          <button type="button" onClick={handleClose} className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50">Закрыть</button>
        </div>
        <form onSubmit={handleSubmit} className="mt-5 flex gap-2">
          <input value={surname} onChange={(event) => setSurname(event.target.value)} placeholder="Фамилия" className="h-10 min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50" />
          <button type="submit" disabled={loading || !surname.trim()} className="h-10 rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900">{loading ? "Поиск…" : "Найти"}</button>
        </form>
        {error ? <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950/40 dark:text-red-200">{error}</p> : null}
        {items && items.length > 0 ? <section className="mt-5"><p className="font-medium text-amber-800 dark:text-amber-200">Сотрудник уже существует в оперативном контуре</p><ul className="mt-3 space-y-2">{items.map((employee) => <li key={employee.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"><p className="font-medium text-zinc-900 dark:text-zinc-50">{employee.fio || "—"}</p><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Отделение: {employee.department?.name ?? employee.org_unit?.name ?? "—"}</p><p className="text-sm text-zinc-600 dark:text-zinc-400">Должность: {employee.position?.name ?? "—"}</p>{employee.id ? <Link href={buildEmployeeCardHref(employee.id)} className="mt-2 inline-block text-sm font-medium text-blue-700 hover:underline dark:text-blue-300">Открыть карточку</Link> : null}</li>)}</ul></section> : null}
        {items && items.length === 0 ? <section className="mt-5 space-y-3">
          <p className="font-medium text-zinc-900 dark:text-zinc-50">Сотрудник в оперативном контуре не найден</p>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"><p className="font-medium text-zinc-900 dark:text-zinc-50">1. Поиск в контрольном списке</p><button type="button" disabled={controlListLoading} onClick={() => void searchControlList()} className="mt-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900">{controlListLoading ? "Поиск…" : "Найти в контрольном списке"}</button>
            {people && people.length === 0 ? <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">В контрольном списке записи не найдены.</p> : null}
            {people ? <ul className="mt-3 space-y-2">{people.map((person) => <li key={person.key} className="flex items-start justify-between gap-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"><div><p className="font-medium text-zinc-900 dark:text-zinc-50">{person.fullName}</p>{person.iin ? <p className="text-sm text-zinc-600 dark:text-zinc-400">ИИН: {person.iin}</p> : null}<p className="text-sm text-zinc-600 dark:text-zinc-400">Импорты: {person.importIds.join(", ")}</p>{person.records.length > 1 ? <p className="text-sm text-zinc-600 dark:text-zinc-400">Исходных записей: {person.records.length}</p> : null}</div><button type="button" disabled={profileLoading} onClick={() => void selectPerson(person)} className="shrink-0 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-800 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-100">Выбрать</button></li>)}</ul> : null}
          </div>
          <div className={`rounded-lg border p-3 ${selectedPerson ? "border-zinc-200 dark:border-zinc-800" : "border-dashed border-zinc-300 text-zinc-500 dark:border-zinc-700 dark:text-zinc-400"}`}><p className="font-medium text-zinc-900 dark:text-zinc-50">2. Импортная карточка с расширенными сведениями</p>{!selectedPerson ? <p className="mt-1 text-sm">Сначала выберите человека из контрольного списка.</p> : null}{profileLoading ? <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Поиск импортных карточек…</p> : null}{selectedPerson && profileOptions && profileOptions.length === 0 ? <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Связанная импортная карточка не найдена.</p> : null}{profileOptions && profileOptions.length > 0 ? <div className="mt-3 space-y-2">{profileOptions.map((option) => <label key={option.key} className="flex cursor-pointer gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"><input type="radio" name="import-profile" checked={profileSelection?.key === option.key} onChange={() => handleProfileSelectionChange(option)} /><span className="text-sm"><span className="block font-medium">Импорт: {option.batchId}</span>{option.department ? <span className="block">Подразделение: {option.department}</span> : null}{option.position ? <span className="block">Должность: {option.position}</span> : null}{option.rowIds.length > 1 ? <span className="block">Связанных исходных записей: {option.rowIds.length}</span> : null}</span></label>)}<button type="button" disabled={!profileSelection || profileLoading} onClick={() => void openSelectedProfile()} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900">Открыть импортную карточку</button></div> : null}</div>
          <div className={`min-w-0 rounded-lg border p-3 ${profileSelection ? "border-zinc-200 dark:border-zinc-800" : "border-dashed border-zinc-300 text-zinc-500 dark:border-zinc-700 dark:text-zinc-400"}`}><p className="font-medium text-zinc-900 dark:text-zinc-50">3. Добавление сотрудника в раздел «Персонал»</p>{profileSelection ? <ImportEnrollEmployeeWizard mode="enroll-only" record={profileSelection.record} onReviewed={() => onEnrolled?.()} onToast={(message, kind) => { if (kind === "error") setError(message); }} /> : <p className="mt-1 text-sm">Сначала выберите импортную карточку.</p>}</div>
        </section> : null}
      </section>
      <ControlListProfilePreviewDialog detail={profilePreview} open={profilePreview !== null} onClose={invalidateProfilePreview} />
    </div>
  );
}




