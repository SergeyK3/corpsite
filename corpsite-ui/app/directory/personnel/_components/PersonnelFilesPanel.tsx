"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import {
  acknowledgeFileNotifications, fileKinds, fileError, listFiles, submitFile, decideFile, fileBlob, fileHistory, applyFileName, reviewQueue,
  classifierCatalog, registryCertificates, certificateComparison,
  type PersonnelFile, type FileKind, type FileList, type FileEvent, type NameProposal,
  type CertificateFacts, type CertificateComparison, type ClassifierEntry, type CertificateInput,
} from "../_lib/personnelFilesApi.client";

const states = { pending: "На проверке", returned: "Возвращён", approved: "Одобрен", superseded: "Заменён", revoked: "Отозван", archived: "В архиве" };
const eventLabels: Record<string, string> = { submitted: "Файл принят на проверку", approve: "Одобрен", return: "Возвращён", revoke: "Отозван", archive: "Архивирован", superseded: "Заменён", name_applied: "Изменение ФИО подтверждено", view: "Просмотр", download: "Скачивание", print: "Запрос страницы для печати", list: "Список файлов", history: "История", access_denied: "Отказ в доступе", technical_rejected: "Техническая проверка не пройдена" };
const inputClass = "w-full rounded border border-zinc-300 bg-transparent p-2 text-sm dark:border-zinc-700";
const buttonClass = "rounded border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700";

const dateLabel = (value: string | null) => value ? value.split("-").reverse().join(".") : "Неизвестно";
function CertificateSummary({facts}: {facts?: CertificateFacts | null}) {
  return <dl className="my-2 space-y-1 text-sm">
    <div><dt className="inline font-medium">Запись реестра: </dt><dd className="inline">{facts?.document_id ?? "Не связана"}</dd></div>
    <div><dt className="inline font-medium">Название в выданном сертификате: </dt><dd className="inline">{facts?.specialty_name_at_issue || "Неизвестно"}</dd></div>
    <div><dt className="inline font-medium">Код и редакция: </dt><dd className="inline">{facts?.specialty_code_at_issue || "Неизвестно"} / {facts?.classifier_edition_at_issue || "Неизвестно"}</dd></div>
    <div><dt className="inline font-medium">Выдан: </dt><dd className="inline">{dateLabel(facts?.issued_at ?? null)}</dd><dt className="ml-3 inline font-medium">Действует до: </dt><dd className="inline">{dateLabel(facts?.valid_until ?? null)}</dd></div>
  </dl>;
}

function nameDisplay(value: NameProposal | null) {
  return value ? [value.last_name, value.first_name, value.middle_name].filter(Boolean).join(" ") : "";
}

type Props = { personId: number | null; fullName: string; onChanged?: () => void; queue?: boolean };

export default function PersonnelFilesPanel({ personId, fullName, onChanged, queue = false }: Props) {
  const [data, setData] = React.useState<FileList | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [kind, setKind] = React.useState<FileKind>("certificate");
  const [title, setTitle] = React.useState("");
  const [file, setFile] = React.useState<File | null>(null);
  const [replacement, setReplacement] = React.useState<PersonnelFile | null>(null);
  const [proposal, setProposal] = React.useState<NameProposal>({ last_name: "", first_name: "", middle_name: "" });
  const [history, setHistory] = React.useState<FileEvent[] | null>(null);
  const [selected, setSelected] = React.useState<PersonnelFile | null>(null);
  const [page, setPage] = React.useState(1);
  const [preview, setPreview] = React.useState<string | null>(null);
  const [decision, setDecision] = React.useState<{ file: PersonnelFile; action: string } | null>(null);
  const [effectiveDate, setEffectiveDate] = React.useState("");
  const [effectiveFullName, setEffectiveFullName] = React.useState(fullName);
  const [reason, setReason] = React.useState("");
  const [showHistory, setShowHistory] = React.useState(false);
  const [entries, setEntries] = React.useState<ClassifierEntry[]>([]);
  const [registry, setRegistry] = React.useState<CertificateFacts[]>([]);
  const [registryId, setRegistryId] = React.useState("");
  const [entryId, setEntryId] = React.useState("");
  const [originalSpecialty, setOriginalSpecialty] = React.useState("");
  const [issuedAt, setIssuedAt] = React.useState("");
  const [validUntil, setValidUntil] = React.useState("");
  const [documentNumber, setDocumentNumber] = React.useState("");
  const [comparison, setComparison] = React.useState<CertificateComparison | null>(null);
  const [comparisonLoading, setComparisonLoading] = React.useState(false);
  const [comparisonError, setComparisonError] = React.useState<string | null>(null);
  const comparisonRequest = React.useRef(0);
  const uploadForm = React.useRef<HTMLFormElement>(null);
  const nextQueue = React.useRef<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      if (queue) {
        const result = await reviewQueue();
        nextQueue.current = result.next;
        setData({ items: result.items, can_review: true, can_upload: false });
      } else {
        const result = await listFiles(personId); setData(result);
        if (result.can_upload) {
          const [catalog, options] = await Promise.all([classifierCatalog(), registryCertificates(personId)]);
          setEntries(catalog.entries.filter(row => row.accepts_new)); setRegistry(options.items);
        }
      }
    } catch (caught) { setError(fileError(caught)); }
    finally { setLoading(false); }
  }, [personId, queue]);
  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => {
    if (!selected) { setPreview(null); return; }
    let cancelled = false;
    let url: string | null = null;
    setPreview(null);
    void fileBlob(selected, "preview", page).then(blob => {
      if (!cancelled) { url = URL.createObjectURL(blob); setPreview(url); }
    }).catch(caught => { if (!cancelled) setError(fileError(caught)); });
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [selected, page]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(null); setNotice(null);
    try { await action(); } catch (caught) { setError(fileError(caught)); }
    finally { setBusy(false); }
  };
  const refresh = async () => { setSelected(null); setHistory(null); await load(); onChanged?.(); };
  const replace = (row: PersonnelFile) => {
    setReplacement(row); setKind(row.kind); setTitle(row.title); setFile(null);
    setRegistryId(""); setEntryId(""); setOriginalSpecialty(""); setIssuedAt(""); setValidUntil(""); setDocumentNumber("");
    setProposal(row.proposed_name ?? { last_name: "", first_name: "", middle_name: "" });
    uploadForm.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const openDecision = (row: PersonnelFile, action: string) => {
    const request = ++comparisonRequest.current;
    setDecision({file: row, action}); setReason(""); setError(null); setComparison(null); setComparisonError(null);
    if (row.kind === "certificate" && action === "approve") {
      setComparisonLoading(true);
      void certificateComparison(row).then(value => {if (comparisonRequest.current === request) setComparison(value);})
        .catch(caught => {if (comparisonRequest.current === request) setComparisonError(fileError(caught));})
        .finally(() => {if (comparisonRequest.current === request) setComparisonLoading(false);});
    } else setComparisonLoading(false);
  };
  const download = async (row: PersonnelFile) => {
    const blob = await fileBlob(row, "download");
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url;
    anchor.download = `${row.kind}-${row.version_no}.${({ "image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf" } as Record<string, string>)[row.mime_type]}`;
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const print = (row: PersonnelFile) => {
    const popup = window.open("", "_blank");
    if (!popup) { setError("Разрешите открытие окна печати для этого сайта."); return; }
    popup.opener = null;
    popup.document.title = "Печать документа";
    popup.document.body.textContent = "Подготовка страниц…";
    void run(async () => {
      const urls: string[] = [];
      try {
        const blobs = [];
        for (let index = 1; index <= row.page_count; index++) blobs.push(await fileBlob(row, "print", index));
        popup.document.body.textContent = "";
        await Promise.all(blobs.map(blob => new Promise<void>((resolve, reject) => {
          const image = popup.document.createElement("img");
          const url = URL.createObjectURL(blob); urls.push(url);
          image.style.width = "100%"; image.style.breakAfter = "page";
          image.onload = () => resolve(); image.onerror = () => reject(new Error("Не удалось подготовить страницу."));
          image.src = url; popup.document.body.append(image);
        })));
        popup.focus(); popup.print();
      } catch (caught) { popup.close(); throw caught; }
      finally { setTimeout(() => urls.forEach(url => URL.revokeObjectURL(url)), 60000); }
    });
  };
  const latest = new Map<string, number>();
  data?.items.forEach(row => latest.set(row.set_id, Math.max(latest.get(row.set_id) ?? 0, row.version_no)));

  return <section id="personnel-files" className="my-5 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800" aria-label="Фото и документы">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold">{queue ? "Проверка карточек" : "Фото и документы"}</h2>
      <div className="flex flex-wrap gap-2">
        {queue ? <Link className={buttonClass} href="/directory/personnel/certificate-classifiers">Редакции и соответствия специальностей</Link> : null}
        <button type="button" className={buttonClass} onClick={() => void load()} disabled={busy}>Обновить</button>
        {!queue && data?.can_review ? <Link className={buttonClass} href="/directory/personnel/file-review">Проверка карточек</Link> : null}
        {!queue && data && data.can_history ? <button className={buttonClass} type="button" disabled={busy} onClick={() => void run(async () => setHistory(await fileHistory(personId)))}>История действий</button> : null}
      </div>
    </div>
    <p className="mt-2 text-sm text-zinc-500">JPEG, PNG или PDF до 10 МиБ и 20 страниц. Фото лица — JPEG 600 × 800, до 500 КиБ. Новая версия появится в карточке после одобрения кадровиком.</p>
    {error ? <p role="alert" className="my-3 text-sm text-red-700">{error}</p> : null}
    {notice ? <p role="status" className="my-3 text-sm text-emerald-700">{notice}</p> : null}
    {personId == null && !queue && data?.notifications?.length ? <div role="status" className="my-3 rounded border border-blue-300 p-3"><p className="font-medium">Новые решения по вашим файлам</p><ul>{data.notifications.map(item => <li key={item.event_id}>{eventLabels[item.action] ?? item.action}{typeof item.detail.reason === "string" && item.detail.reason ? `: ${item.detail.reason}` : ""}</li>)}</ul><button className={buttonClass} type="button" disabled={busy} onClick={() => void run(async () => { await acknowledgeFileNotifications(Math.max(...data.notifications!.map(item => item.event_id))); await load(); })}>Отметить прочитанным</button></div> : null}
    {loading ? <p role="status" className="my-3">Загрузка файлов…</p> : null}
    {!loading && data?.items.length === 0 ? <p className="my-4 text-sm">{queue ? "В этой части очереди доступных заданий нет." : "Файлы ещё не загружены."}</p> : null}
    {!queue && data?.items.some(row => ["returned", "approved", "revoked"].includes(row.state)) ? <p className="my-3 text-sm" role="status">Решения кадровика и пояснения показаны у соответствующих версий ниже.</p> : null}
    {!queue && data ? <label className="my-3 flex gap-2 text-sm"><input type="checkbox" checked={showHistory} onChange={e => setShowHistory(e.target.checked)} />Показывать предыдущие версии</label> : null}
    <div className="space-y-3">{data?.items.filter(row => queue || showHistory || row.state === "approved" || row.version_no === latest.get(row.set_id)).map(row => <article key={row.version_id} className="rounded border border-zinc-200 p-3 dark:border-zinc-700">
      {queue ? <Link className="text-blue-700 underline" href={`/directory/personnel/persons/${row.person_id}/card#personnel-files`}>{row.full_name}</Link> : null}
      <h3 className="font-medium">{row.title} <span className="text-sm font-normal">· {fileKinds[row.kind]} · версия {row.version_no}</span></h3>
      <p className="text-sm">{states[row.state]} · {row.page_count} стр. · {new Date(row.created_at).toLocaleString("ru-RU")}</p>
      {row.kind === "certificate" ? <CertificateSummary facts={row.certificate} /> : null}
      {row.reason ? <p className="mt-2 text-sm">Пояснение: {row.reason}</p> : null}
      {row.proposed_name ? <p className="mt-2 text-sm">Предлагаемое ФИО: {nameDisplay(row.proposed_name)}. {row.name_applied_at ? "Изменение ФИО подтверждено." : "ФИО не изменено автоматически."}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={buttonClass} disabled={busy} onClick={() => { setPage(1); setSelected(row); }}>Просмотреть</button>
        {row.can_export ? <><button type="button" className={buttonClass} disabled={busy} onClick={() => void run(() => download(row))}>Скачать</button><button type="button" className={buttonClass} disabled={busy} onClick={() => print(row)}>Печать</button></> : null}
        {!queue && row.can_replace && row.state !== "pending" && row.version_no === latest.get(row.set_id) ? <button type="button" className={buttonClass} disabled={busy} onClick={() => replace(row)}>Загрузить новую версию</button> : null}
        {row.can_review ? (row.state === "pending" ? [["approve", "Одобрить"], ["return", "Вернуть с пояснением"]] : row.state === "approved" ? [["revoke", "Отозвать"]] : row.state !== "archived" ? [["archive", "Архивировать"]] : []).map(([action, label]) => <button key={action} type="button" className={buttonClass} disabled={busy} onClick={() => openDecision(row, action)}>{label}</button>) : null}
        {row.can_review && row.kind === "name_change" && row.state === "approved" && row.proposed_name && !row.name_applied_at ? <button type="button" className={buttonClass} disabled={busy} onClick={() => { setEffectiveFullName(fullName); setEffectiveDate(""); setDecision({ file: row, action: "apply-name" }); setReason(""); }}>Подтвердить изменение ФИО</button> : null}
      </div>
    </article>)}</div>
    {queue && nextQueue.current != null ? <button type="button" className={`${buttonClass} mt-3`} disabled={busy} onClick={() => void run(async () => { const result = await reviewQueue(nextQueue.current!); nextQueue.current = result.next; setData({ items: result.items, can_review: true, can_upload: false }); })}>Следующая часть очереди</button> : null}
    {data?.can_upload && !queue ? <form ref={uploadForm} className="mt-5 space-y-3 border-t border-zinc-200 pt-4 dark:border-zinc-800" onSubmit={e => {
      e.preventDefault(); if (!file) { setError("Выберите файл."); return; }
      void run(async () => {
        if (file.size > 10 * 1024 * 1024) throw new Error("Максимальный размер файла — 10 МиБ.");
        const certificate: CertificateInput | undefined = kind !== "certificate" ? undefined : registryId ? {employee_document_id: Number(registryId)} : {
          entry_id: Number(entryId), specialty_name_at_issue: originalSpecialty, issued_at: issuedAt, valid_until: validUntil, document_number: documentNumber || undefined,
        };
        await submitFile(personId, file, kind, title, replacement, kind === "name_change" ? proposal : undefined, certificate);
        uploadForm.current?.reset(); setFile(null); setReplacement(null); setTitle("");
        setRegistryId(""); setEntryId(""); setOriginalSpecialty(""); setIssuedAt(""); setValidUntil(""); setDocumentNumber("");
        await refresh(); setNotice("Файл принят на проверку. Действующая версия сохраняется до одобрения новой.");
      });
    }}>
      <h3 className="font-medium">{replacement ? `Новая версия: ${replacement.title}` : "Загрузить файл"}</h3>
      <label className="block text-sm">Назначение<select className={inputClass} value={kind} disabled={!!replacement || busy} onChange={e => setKind(e.target.value as FileKind)}>{Object.entries(fileKinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label className="block text-sm">Название<input className={inputClass} required maxLength={300} value={title} disabled={!!replacement || busy} onChange={e => setTitle(e.target.value)} /></label>
      {kind === "certificate" ? <fieldset className="space-y-3 rounded border p-3"><legend>Реквизиты сертификата в реестре</legend>
        <label className="block text-sm">Связь с реестром<select className={inputClass} value={registryId} onChange={e => setRegistryId(e.target.value)} disabled={busy}>
          <option value="">Создать новую запись сертификата</option>
          {registry.map(row => <option key={row.document_id} value={row.document_id}>№ {row.document_id} · {row.specialty_name_at_issue || "Исходное название неизвестно"} · до {dateLabel(row.valid_until)}</option>)}
        </select></label>
        {registryId ? <><CertificateSummary facts={registry.find(row => row.document_id === Number(registryId))} /><p className="text-sm">Реквизиты берутся из существующей записи и при загрузке не изменяются. Неизвестные сведения не восстанавливаются автоматически.</p></> : <>
          <label className="block text-sm">Специальность и редакция классификатора<select className={inputClass} required value={entryId} onChange={e => setEntryId(e.target.value)} disabled={busy}>
            <option value="">Выберите по выданному сертификату</option>{entries.map(row => <option key={row.entry_id} value={row.entry_id}>{row.specialty_name} · {row.specialty_code} · {row.edition_code}</option>)}
          </select></label>
          <label className="block text-sm">Название специальности в выданном сертификате<input className={inputClass} required maxLength={500} value={originalSpecialty} onChange={e => setOriginalSpecialty(e.target.value)} /></label>
          <div className="grid gap-3 sm:grid-cols-2"><label className="block text-sm">Дата выдачи<input className={inputClass} required type="date" value={issuedAt} onChange={e => setIssuedAt(e.target.value)} /></label>
          <label className="block text-sm">Действует до<input className={inputClass} required type="date" min={issuedAt || undefined} value={validUntil} onChange={e => setValidUntil(e.target.value)} /></label></div>
          <label className="block text-sm">Номер сертификата<input className={inputClass} maxLength={200} value={documentNumber} onChange={e => setDocumentNumber(e.target.value)} /></label>
        </>}
        <p className="text-sm">Соответствия между редакциями ведёт уполномоченный сотрудник отдела кадров централизованно. Название файла и должность не подтверждают соответствие.</p>
      </fieldset> : null}
      {kind === "name_change" ? <fieldset className="space-y-2"><legend className="text-sm">Предлагаемое ФИО</legend>{([["last_name", "Фамилия"], ["first_name", "Имя"], ["middle_name", "Отчество"]] as const).map(([key, label]) => <label className="block text-sm" key={key}>{label}<input className={inputClass} required={key !== "middle_name"} maxLength={100} value={proposal[key]} onChange={e => setProposal({ ...proposal, [key]: e.target.value })} /></label>)}</fieldset> : null}
      <label className="block text-sm">Файл<input className="mt-1 block w-full" type="file" accept={kind === "photo" ? "image/jpeg" : "image/jpeg,image/png,application/pdf"} required disabled={busy} onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
      <div className="flex gap-2"><button type="submit" className={buttonClass} disabled={busy}>{busy ? "Обработка…" : "Отправить кадровику"}</button>{replacement ? <button type="button" className={buttonClass} onClick={() => { setReplacement(null); setTitle(""); }}>Отменить замену</button> : null}</div>
    </form> : null}
    {selected ? <div role="dialog" aria-modal="true" aria-label="Просмотр файла" className="fixed inset-0 z-[60] overflow-y-auto bg-white p-5 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3>{selected.title}</h3><button type="button" className={buttonClass} onClick={() => setSelected(null)}>Закрыть просмотр</button></div>
      <div className="my-3 flex items-center gap-3"><button type="button" className={buttonClass} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Предыдущая</button><span>{page} / {selected.page_count}</span><button type="button" className={buttonClass} disabled={page >= selected.page_count} onClick={() => setPage(p => p + 1)}>Следующая</button></div>
      {preview ? <Image src={preview} width={1400} height={1800} alt={`Страница ${page} документа ${selected.title}`} unoptimized className="mx-auto h-auto max-h-none w-full max-w-4xl object-contain" /> : <p role="status">Загрузка страницы…</p>}
    </div> : null}
    {decision ? <form role="dialog" aria-modal="true" aria-label="Решение по файлу" className={`fixed inset-x-4 top-8 z-50 mx-auto max-h-[90vh] overflow-y-auto space-y-3 rounded-lg border bg-white p-5 shadow-xl dark:bg-zinc-950 ${decision.file.kind === "certificate" && decision.action === "approve" ? "max-w-5xl" : "max-w-lg"}`} onSubmit={e => {
      e.preventDefault(); void run(async () => {
        if (decision.action === "apply-name") await applyFileName(decision.file, effectiveFullName, reason, effectiveDate);
        else if (decision.action === "approve" && decision.file.kind === "certificate") await decideFile(decision.file, decision.action, reason, comparison);
        else await decideFile(decision.file, decision.action, reason);
        setDecision(null); await refresh(); setNotice("Решение сохранено.");
      });
    }}>
      <h3 className="font-semibold">{decision.action === "apply-name" ? "Подтвердить изменение ФИО" : "Решение по файлу"}</h3>
      {error ? <p role="alert" className="text-red-600">{error}</p> : null}
      <p className="text-sm">{decision.file.title} · версия {decision.file.version_no}</p>
      {decision.file.kind === "certificate" && decision.action === "approve" ? <>
        {comparisonLoading ? <p role="status">Проверка прежнего сертификата и основания замены…</p> : null}
        {comparisonError ? <p role="alert">{comparisonError}</p> : null}
        {comparison ? <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded border p-3"><h4 className="font-semibold">Прежний одобренный сертификат</h4>
              {comparison.previous ? <><p>{comparison.previous.title} · версия {comparison.previous.version_no}</p><CertificateSummary facts={comparison.previous.certificate} /><button type="button" className={buttonClass} onClick={() => {setPage(1); setSelected(comparison.previous);}}>Просмотреть прежний сертификат</button></> : <p>Не заменяется: самостоятельная запись.</p>}
            </div>
            <div className="rounded border p-3"><h4 className="font-semibold">Новый сертификат</h4><CertificateSummary facts={comparison.new_certificate} /><button type="button" className={buttonClass} onClick={() => {setPage(1); setSelected(decision.file);}}>Просмотреть новый сертификат</button></div>
          </div>
          <div className={`rounded border p-3 text-sm ${comparison.can_approve ? "border-emerald-600" : "border-red-600"}`}><h4 className="font-semibold">Основание замены</h4><p>{comparison.basis.description}</p>
            {comparison.basis.source_reference ? <p>Источник: {comparison.basis.source_reference}</p> : null}
            {comparison.basis.reason ? <p>Подтверждение: {comparison.basis.reason}</p> : null}
            {comparison.basis.mapping_id ? <p>Соответствие № {comparison.basis.mapping_id} · подтвердил сотрудник #{comparison.basis.confirmed_by} · действует с {dateLabel(comparison.basis.effective_from ?? null)}</p> : null}
            {!comparison.can_approve ? <p>Сервер отклонит одобрение замены. Прежний сертификат сохранится. Верните заявку с пояснением; новый сертификат можно подать отдельно.</p> : null}
          </div>
        </> : null}
      </> : null}
      {decision.action === "apply-name" ? <p className="text-sm">Было: {fullName}. Будет: {nameDisplay(decision.file.proposed_name)}. Это отдельное изменение персональных данных.</p> : null}
      {decision.action === "apply-name" ? <><label className="block text-sm">Текущее ФИО для проверки<input className={inputClass} required value={effectiveFullName} onChange={e => setEffectiveFullName(e.target.value)} /></label><label className="block text-sm">Дата действия изменения<input type="date" className={inputClass} required value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} /></label><p className="text-sm">Для подтверждения требуется одобренное удостоверение личности.</p></> : null}
      <label className="block text-sm">Пояснение<textarea className={inputClass} maxLength={2000} required={decision.action !== "approve"} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button type="submit" className={buttonClass} disabled={busy || comparisonLoading || (decision.file.kind === "certificate" && decision.action === "approve" && !comparison)}>Подтвердить решение</button><button type="button" className={buttonClass} disabled={busy} onClick={() => {++comparisonRequest.current;setDecision(null);}}>Отмена</button>
    </form> : null}
    {history ? <div className="mt-4"><h3 className="font-medium">История действий</h3><button type="button" className={buttonClass} onClick={() => setHistory(null)}>Скрыть историю</button><ol className="mt-3 space-y-2 text-sm">{history.map(item => <li key={item.event_id}>{new Date(item.created_at).toLocaleString("ru-RU")} · {eventLabels[item.action] ?? item.action} · пользователь #{item.actor_id}{typeof item.detail.reason === "string" ? ` · ${item.detail.reason}` : ""}</li>)}</ol></div> : null}
  </section>;
}
