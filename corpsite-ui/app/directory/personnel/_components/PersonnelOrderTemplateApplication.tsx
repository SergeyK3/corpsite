"use client";

import { useEffect, useState } from "react";

import {
  applyPersonnelOrderTemplateApplication,
  previewPersonnelOrderTemplateApplication,
  type PersonnelOrderEditorialState,
  type PersonnelOrderTemplateApplicationPreview,
} from "../_lib/personnelOrdersApi.client";

const BLOCKS = [["title", "Заголовок"], ["preamble", "Преамбула"], ["body", "Распорядительный текст"], ["basis", "Основание"]] as const;

type PreviewProblem = { kind: "missing" | "unpublished" | "readonly" | "unexpected"; message: string };

function currentText(preview: PersonnelOrderTemplateApplicationPreview, locale: "ru" | "kk", block: string) {
  const entry = preview.current[`${locale}:${block}`];
  return entry?.override_text ?? entry?.generated_text ?? "—";
}

function proposedText(preview: PersonnelOrderTemplateApplicationPreview, locale: "ru" | "kk", block: string) {
  const templateKey = block === "body" || block === "basis"
    ? `${block}_template_${locale}`
    : `${block}_${locale}`;
  return preview.proposed[templateKey] ?? "—";
}

function ComparisonRow({ preview, block, label }: { preview: PersonnelOrderTemplateApplicationPreview; block: string; label: string }) {
  const cell = (locale: "ru" | "kk", kind: "proposed" | "current", heading: string) => {
    const text = kind === "proposed" ? proposedText(preview, locale, block) : currentText(preview, locale, block);
    const differs = proposedText(preview, locale, block) !== currentText(preview, locale, block);
    const colour = kind === "proposed" ? "border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30" : "border-amber-300 bg-amber-50 dark:bg-amber-950/30";
    return <div data-testid={`template-application-${locale}-${block}-${kind}`} className={`h-full min-w-0 rounded border p-2 text-sm ${differs ? colour : ""}`}><div className="font-medium">{locale.toUpperCase()} · {heading}</div><div className="mt-1 whitespace-pre-wrap break-words">{text}</div></div>;
  };
  return <section className="grid grid-cols-1 gap-2 border-t border-zinc-200 pt-3 first:border-t-0 first:pt-0 dark:border-zinc-800" data-testid={`template-application-row-${block}`}>
    <h4 className="text-sm font-semibold">{label}</h4>
    <div className="grid grid-cols-1 items-stretch gap-2 md:grid-cols-4" data-testid={`template-application-grid-${block}`}>
      {cell("ru", "proposed", "По шаблону")}{cell("ru", "current", "Было")}{cell("kk", "proposed", "По шаблону")}{cell("kk", "current", "Было")}
    </div>
  </section>;
}

function previewProblem(error: unknown): PreviewProblem {
  const detail = error instanceof Error ? error.message : String(error || "");
  const missing = detail.match(/Required template data is missing:\s*(.+)$/i);
  if (missing) {
    const labels: Record<string, string> = {
      "termination.reason": "причина увольнения",
      "termination.unused_leave_days": "количество дней неиспользованного отпуска",
    };
    const fields = missing[1].split(",").map((field) => labels[field.trim()] || field.trim());
    return { kind: "missing", message: `Не хватает реквизита: ${fields.join(", ")}.` };
  }
  if (/No PUBLISHED template/i.test(detail)) return { kind: "unpublished", message: "Опубликованный шаблон не найден." };
  if (/available only for a non-archived DRAFT order|requires exactly one ACTIVE item/i.test(detail)) {
    return { kind: "readonly", message: "Предпросмотр шаблона недоступен для текущего состояния приказа." };
  }
  return { kind: "unexpected", message: "Не удалось проверить шаблон приказа. Повторите попытку позже или обратитесь к администратору." };
}

export default function PersonnelOrderTemplateApplication({ orderId, refreshKey = 0, onApplied }: { orderId: number; refreshKey?: number; onApplied: (state: PersonnelOrderEditorialState) => void }) {
  const [preview, setPreview] = useState<PersonnelOrderTemplateApplicationPreview | null>(null);
  const [problem, setProblem] = useState<PreviewProblem | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [replaceOverrides, setReplaceOverrides] = useState(false);
  const [confirmReapply, setConfirmReapply] = useState(false);

  useEffect(() => {
    let active = true;
    setPreview(null); setProblem(null); setLoading(true); setApplyError(""); setReplaceOverrides(false); setConfirmReapply(false);
    void previewPersonnelOrderTemplateApplication(orderId)
      .then((result) => { if (active) setPreview(result); })
      .catch((cause) => { if (active) setProblem(previewProblem(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [orderId, refreshKey]);

  const apply = () => {
    if (!preview || busy) return;
    setBusy(true); setApplyError("");
    void applyPersonnelOrderTemplateApplication(orderId, {
      expected_document_revision: preview.order_revision,
      confirm_replace_overrides: !preview.has_overrides || replaceOverrides,
      confirm_reapply: !preview.has_prior_application || confirmReapply,
    }).then((state) => {
      onApplied(state); setPreview(null); setReplaceOverrides(false); setConfirmReapply(false);
    }).catch(() => {
      setApplyError("Не удалось применить шаблон. Данные приказа не были изменены.");
    }).finally(() => setBusy(false));
  };

  return <section className="mb-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" data-testid="personnel-order-template-application">
    <h3 className="font-semibold">Шаблон приказа</h3>
    {loading ? <p className="mt-2 text-sm text-zinc-500">Проверка доступности шаблона…</p> : null}
    {problem ? <p role="alert" className={problem.kind === "unexpected" ? "mt-2 text-sm text-red-700" : "mt-2 text-sm text-amber-700"}>{problem.message}</p> : null}
    {preview ? <>
      <p className="mt-2 text-sm" data-testid="template-application-template-meta">Тип: {preview.template.item_type_code} · PUBLISHED · версия {preview.template.version_number}</p>
      {preview.has_overrides ? <div className="mt-2 text-sm text-amber-700" role="alert"><p>Ручные изменения будут заменены только после подтверждения.</p><ul data-testid="template-application-override-blocks">{preview.override_blocks.map((block) => <li key={`${block.scope}-${block.block_id}`}>{block.scope} · {block.block_type} · {block.language}</li>)}</ul><label className="mt-2 flex gap-2"><input type="checkbox" checked={replaceOverrides} onChange={(e) => setReplaceOverrides(e.target.checked)} disabled={busy} /> Подтверждаю замену ручных правок</label></div> : null}
      {preview.has_prior_application ? <div className="mt-2 text-sm text-amber-700" role="alert"><p>Шаблон уже применялся: версия {preview.last_application?.template_version_number ?? "—"} · {preview.last_application?.applied_at ?? "—"}.</p><label className="mt-2 flex gap-2"><input type="checkbox" checked={confirmReapply} onChange={(e) => setConfirmReapply(e.target.checked)} disabled={busy} /> Подтверждаю повторное применение</label></div> : null}
      <div className="mt-3 space-y-3" data-testid="template-application-diff">{BLOCKS.map(([block, label]) => <ComparisonRow key={block} preview={preview} block={block} label={label} />)}</div>
      <button type="button" className="mt-3 rounded bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-60" onClick={apply} disabled={busy || (preview.has_overrides && !replaceOverrides) || (preview.has_prior_application && !confirmReapply)}>{busy ? "Применение…" : "Применить шаблон"}</button>
    </> : null}
    {applyError ? <p role="alert" className="mt-2 text-sm text-red-700">{applyError}</p> : null}
  </section>;
}
