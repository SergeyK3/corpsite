"use client";

import * as React from "react";
import Link from "next/link";
import { classifierCatalog, manageClassifiers, fileError, type ClassifierCatalog } from "../_lib/personnelFilesApi.client";

const field = "mt-1 w-full rounded border border-zinc-400 bg-transparent p-2 dark:border-zinc-700";
const button = "rounded border border-zinc-400 px-3 py-2 disabled:opacity-50";

export default function CertificateClassifiersPage() {
  const [catalog,setCatalog] = React.useState<ClassifierCatalog | null>(null);
  const [error,setError] = React.useState<string | null>(null);
  const [notice,setNotice] = React.useState<string | null>(null);
  const [busy,setBusy] = React.useState(false);
  const load = React.useCallback(async () => setCatalog(await classifierCatalog()),[]);
  React.useEffect(() => {void load().catch(e => setError(fileError(e)));},[load]);
  const save = async (path: string, body: Record<string, unknown>) => {
    setBusy(true);setError(null);setNotice(null);
    try {await manageClassifiers(path,body);await load();setNotice("Сохранено централизованно. Ранее выданные сертификаты не изменены.");}
    catch(e) {setError(fileError(e));} finally {setBusy(false);}
  };
  const entryLabel = (id:number) => {const e=catalog?.entries.find(row => row.entry_id===id);return e ? `${e.specialty_name} · ${e.specialty_code} · ${e.edition_code}` : `№ ${id}`;};
  return <main className="mx-auto max-w-6xl space-y-5 p-5">
    <Link href="/directory/personnel/file-review" className="underline">К проверке карточек</Link>
    <h1 className="text-2xl font-semibold">Редакции и соответствия специальностей</h1>
    <p>Централизованный справочник ведёт уполномоченный сотрудник отдела кадров с отдельным разрешением. Соответствие действует только в указанном направлении; совпадение названий не создаёт его автоматически.</p>
    {error ? <p role="alert" className="text-red-600">{error}</p> : null}{notice ? <p role="status">{notice}</p> : null}
    {!catalog ? <p>Загрузка…</p> : <>
      {!catalog.can_manage ? <p>Доступен только просмотр. Для изменений нужны кадровое полномочие и центральное разрешение.</p> : null}
      <section><h2 className="text-lg font-semibold">Редакции</h2><ul className="space-y-2">{catalog.editions.map(row => <li key={row.edition_id} className="rounded border p-3">
        <p>{row.title} · {row.code} · с {row.effective_from}</p><p className="text-sm">Источник: {row.source_reference}</p>
        <p>{row.accepts_new ? "Доступна для новых записей" : "Закрыта для новых записей; прежние документы сохранены"}</p>
        {catalog.can_manage ? <button className={button} disabled={busy} onClick={() => void save(`editions/${row.edition_id}/availability`,{accepts_new:!row.accepts_new,reason:row.accepts_new ? "Редакция закрыта для новых записей уполномоченным кадровиком" : "Редакция открыта уполномоченным кадровиком"})}>{row.accepts_new ? "Закрыть для новых записей" : "Открыть для новых записей"}</button> : null}
      </li>)}</ul></section>
      <section><h2 className="text-lg font-semibold">Подтверждённые соответствия</h2><ul className="space-y-3">{catalog.mappings.map(row => <li key={row.mapping_id} className="rounded border p-3">
        <p>{entryLabel(row.from_entry_id)} → {entryLabel(row.to_entry_id)}</p><p>Источник: {row.source_reference}</p><p>{row.reason}</p>
        <p className="text-sm">С {row.effective_from} · подтвердил сотрудник #{row.confirmed_by} · {row.confirmed_at} · {row.active ? "Действует" : "Отозвано"}</p>
        {catalog.can_manage && row.active ? <button className={button} disabled={busy} onClick={() => void save(`mappings/${row.mapping_id}/revoke`,{reason:"Соответствие отозвано уполномоченным сотрудником отдела кадров"})}>Отозвать соответствие</button> : null}
      </li>)}</ul></section>
      {catalog.can_manage ? <div className="grid gap-5 lg:grid-cols-2">
        <form className="space-y-3 rounded border p-4" onSubmit={e => {e.preventDefault();const f=new FormData(e.currentTarget);void save("editions",Object.fromEntries(f));}}>
          <h2 className="font-semibold">Добавить редакцию</h2>
          <label className="block">Код редакции<input name="code" required maxLength={100} className={field}/></label>
          <label className="block">Название редакции<input name="title" required maxLength={500} className={field}/></label>
          <label className="block">Источник редакции<input name="source_reference" required maxLength={2000} className={field}/></label>
          <label className="block">Действует с<input name="effective_from" type="date" required className={field}/></label>
          <button className={button} disabled={busy}>Сохранить редакцию</button>
        </form>
        <form className="space-y-3 rounded border p-4" onSubmit={e => {e.preventDefault();const f=new FormData(e.currentTarget);void save("entries",{...Object.fromEntries(f),edition_id:Number(f.get("edition_id")),medical_specialty_id:Number(f.get("medical_specialty_id"))});}}>
          <h2 className="font-semibold">Добавить специальность в редакцию</h2>
          <label className="block">Редакция<select name="edition_id" required className={field}><option value="">Выберите</option>{catalog.editions.map(row => <option key={row.edition_id} value={row.edition_id}>{row.code}</option>)}</select></label>
          <label className="block">Специальность реестра<select name="medical_specialty_id" required className={field}><option value="">Выберите</option>{catalog.medical_specialties.map(row => <option key={row.medical_specialty_id} value={row.medical_specialty_id}>{row.name}</option>)}</select></label>
          <label className="block">Код специальности<input name="specialty_code" required maxLength={100} className={field}/></label>
          <label className="block">Название специальности в редакции<input name="specialty_name" required maxLength={500} className={field}/></label>
          <button className={button} disabled={busy}>Сохранить специальность</button>
        </form>
        <form className="space-y-3 rounded border p-4 lg:col-span-2" onSubmit={e => {e.preventDefault();const f=new FormData(e.currentTarget);void save("mappings",{...Object.fromEntries(f),from_entry_id:Number(f.get("from_entry_id")),to_entry_id:Number(f.get("to_entry_id"))});}}>
          <h2 className="font-semibold">Подтвердить соответствие</h2>
          <div className="grid gap-3 md:grid-cols-2">{[["from_entry_id","Прежняя специальность"],["to_entry_id","Новая специальность"]].map(([name,label]) => <label key={name} className="block">{label}<select name={name} required className={field}><option value="">Выберите</option>{catalog.entries.map(row => <option key={row.entry_id} value={row.entry_id}>{entryLabel(row.entry_id)}</option>)}</select></label>)}</div>
          <label className="block">Документ основание<input name="source_reference" required maxLength={2000} className={field}/></label>
          <label className="block">Пояснение подтверждения<textarea name="reason" required maxLength={2000} className={field}/></label>
          <label className="block">Дата начала соответствия<input name="effective_from" type="date" required className={field}/></label>
          <p className="text-sm">Подтверждайте только проверенное соответствие на основании указанного документа. Это действие записывается в историю и применяется к будущим решениям по файлам.</p>
          <button className={button} disabled={busy}>Подтвердить соответствие централизованно</button>
        </form>
      </div> : null}
    </>}
  </main>;
}
