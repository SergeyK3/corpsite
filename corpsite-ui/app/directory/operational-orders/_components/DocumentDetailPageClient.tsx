"use client";

import * as React from "react";
import Link from "next/link";

import { apiAuthMe } from "@/lib/api";
import type { MeInfo } from "@/lib/types";
import ConfirmDialog from "@/app/admin/system/_components/shared/ConfirmDialog";
import ErrorBanner, { InfoBanner, SuccessBanner } from "@/app/admin/system/_components/shared/ErrorBanner";

import {
  assignSigningAuthority,
  getDocument,
  getDocumentLocalizations,
  mapOoApiError,
  markReadyForSignature,
  returnToCreated,
  validateReadyForSignature,
} from "../_lib/api";
import { isVersionConflictError } from "../_lib/errors";
import {
  canAssignSigningAuthority,
  canMarkReadyForSignature,
  canReturnFromSignature,
} from "../_lib/permissions";
import { formatDateTime, formatPartyReference } from "../_lib/mappers";
import { buildDocumentLifecycleTimeline, documentTimelineStatusHint } from "../_lib/documentTimeline";
import type { DocumentDetail, DocumentLocalization } from "../_lib/types";
import { auditActionLabel } from "../_lib/actionLabels";
import CompactFingerprint from "./CompactFingerprint";
import DocumentLifecycleTimeline from "./DocumentLifecycleTimeline";
import DocumentStatusBadge from "./DocumentStatusBadge";
import ValidationPanel from "./ValidationPanel";

type Props = { documentId: number };

export default function DocumentDetailPageClient({ documentId }: Props) {
  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [detail, setDetail] = React.useState<DocumentDetail | null>(null);
  const [localizations, setLocalizations] = React.useState<DocumentLocalization[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);
  const [readyOpen, setReadyOpen] = React.useState(false);
  const [returnOpen, setReturnOpen] = React.useState(false);
  const [returnReason, setReturnReason] = React.useState("");
  const [readinessPreview, setReadinessPreview] = React.useState(detail?.readiness_validation ?? null);

  const [authorityRef, setAuthorityRef] = React.useState("");
  const [authorityName, setAuthorityName] = React.useState("");

  const reload = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDocument(documentId);
      setDetail(data);
      const loc = await getDocumentLocalizations(documentId);
      setLocalizations(loc.items);
      setReadinessPreview(data.readiness_validation);
    } catch (e) {
      setDetail(null);
      setLocalizations([]);
      setError(mapOoApiError(e, "Не удалось загрузить документ"));
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  React.useEffect(() => {
    apiAuthMe().then(setMe).catch(() => setMe(null));
  }, []);

  React.useEffect(() => {
    void reload();
  }, [reload]);

  async function runAction(fn: () => Promise<void>) {
    setPending(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      if (isVersionConflictError(e)) {
        setError("Документ изменился. Обновите страницу.");
      } else {
        setError(mapOoApiError(e, "Не удалось выполнить действие"));
      }
    } finally {
      setPending(false);
    }
  }

  if (loading && !detail) {
    return <div className="py-8 text-center text-sm text-zinc-500">Загрузка…</div>;
  }

  if (error && !detail) {
    return <ErrorBanner message={error} />;
  }

  if (!detail) return null;

  const doc = detail.document;
  const ruText = localizations.filter((l) => l.locale === "ru");
  const kkText = localizations.filter((l) => l.locale === "kk");
  const blockers = readinessPreview?.issues.filter((i) => i.severity.toUpperCase() === "ERROR") ?? [];
  const lifecycleSteps = buildDocumentLifecycleTimeline(detail);

  return (
    <div className="space-y-6" data-testid="document-detail">
      <div>
        <Link href="/directory/operational-orders?tab=documents" className="text-sm text-blue-600 hover:underline">
          ← К списку документов
        </Link>
        <h2 className="mt-1 text-lg font-semibold">Document #{doc.document_id}</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          <DocumentStatusBadge status={doc.status} />
          <span className="text-xs text-zinc-500">aggregate v{doc.version}</span>
        </div>
      </div>

      {detail.revision_recommended ? (
        <InfoBanner message="Рабочее пространство отличается от официального снимка. Функция создания новой редакции ещё не реализована." />
      ) : null}
      <ErrorBanner message={error} />
      <SuccessBanner message={toast} />

      <section className="grid gap-2 rounded-xl border p-4 text-sm md:grid-cols-2 dark:border-zinc-800">
        <div>
          Workspace:{" "}
          <Link href={`/directory/operational-orders/workspaces/${doc.workspace_id}`} className="text-blue-600 hover:underline">
            #{doc.workspace_id}
          </Link>
        </div>
        <div>Подразделение: #{doc.submitting_org_unit_id ?? "—"}</div>
        <div>Создан: {formatDateTime(doc.created_at)}</div>
        <div>{documentTimelineStatusHint(doc.status)}</div>
        {detail.current_version ? (
          <div className="md:col-span-2">
            Version {detail.current_version.version_number}
            {" · "}
            <CompactFingerprint value={detail.current_version.snapshot_fingerprint} label="snapshot fp" />
          </div>
        ) : null}
      </section>

      <DocumentLifecycleTimeline steps={lifecycleSteps} />

      <OfficialTextSection title="Official RU text" items={ruText} />
      <OfficialTextSection title="Official KK text" items={kkText} />

      <section className="rounded-xl border p-4 dark:border-zinc-800">
        <h3 className="mb-3 text-sm font-semibold">Signing authority</h3>
        {detail.signing_authority ? (
          <div className="text-sm">
            <div>{detail.signing_authority.authority_display_name || detail.signing_authority.authority_party_reference}</div>
            <div className="text-xs text-zinc-500">
              {formatPartyReference(
                detail.signing_authority.authority_party_type,
                detail.signing_authority.authority_party_reference,
                detail.signing_authority.authority_display_name,
              )}
            </div>
            <div className="text-xs text-zinc-500">Назначен: {formatDateTime(detail.signing_authority.assigned_at)}</div>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">Не назначен</p>
        )}
        {canAssignSigningAuthority(me) && doc.status === "CREATED" ? (
          <div className="mt-3 space-y-2">
            <input
              className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              placeholder="PERSON reference (user id)"
              value={authorityRef}
              onChange={(e) => setAuthorityRef(e.target.value)}
            />
            <input
              className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              placeholder="Display name (optional)"
              value={authorityName}
              onChange={(e) => setAuthorityName(e.target.value)}
            />
            <button
              type="button"
              data-testid="assign-signing-authority-button"
              className="rounded border px-3 py-1.5 text-sm disabled:opacity-50"
              disabled={pending || !authorityRef.trim()}
              onClick={() =>
                void runAction(async () => {
                  const result = await assignSigningAuthority(documentId, {
                    authority: {
                      reference_type: "PERSON",
                      reference: authorityRef.trim(),
                      display_name: authorityName.trim() || null,
                    },
                    expected_document_version: doc.version,
                  });
                  if (result.idempotent_replay) setToast("Подписант уже назначен (replay)");
                  else setToast("Подписант назначен");
                  await reload();
                })
              }
            >
              Назначить подписанта
            </button>
          </div>
        ) : null}
      </section>

      <ValidationPanel
        title="Signature Readiness Validation"
        validation={readinessPreview}
        onRevalidate={
          doc.status === "CREATED"
            ? () =>
                void runAction(async () => {
                  const res = await validateReadyForSignature(documentId, doc.version);
                  setReadinessPreview(res.readiness_validation);
                })
            : undefined
        }
        revalidateDisabled={pending}
        revalidatePending={pending}
      />

      {doc.status === "CREATED" ? (
        <section className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg border px-3 py-1.5 text-sm dark:border-zinc-700"
            disabled={pending}
            onClick={() =>
              void runAction(async () => {
                const res = await validateReadyForSignature(documentId, doc.version);
                setReadinessPreview(res.readiness_validation);
              })
            }
          >
            Проверить готовность
          </button>
          {canMarkReadyForSignature(me) ? (
            <button
              type="button"
              data-testid="mark-ready-button"
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              disabled={pending}
              onClick={() => setReadyOpen(true)}
            >
              Передать на подпись
            </button>
          ) : null}
        </section>
      ) : null}

      {doc.status === "READY_FOR_SIGNATURE" && canReturnFromSignature(me) ? (
        <section>
          <button
            type="button"
            data-testid="return-to-created-button"
            className="rounded-lg border border-amber-300 px-3 py-1.5 text-sm text-amber-900"
            disabled={pending}
            onClick={() => setReturnOpen(true)}
          >
            Вернуть из очереди подписи
          </button>
        </section>
      ) : null}

      {detail.latest_lifecycle_transition ? (
        <section className="rounded-xl border p-4 dark:border-zinc-800">
          <h3 className="mb-3 text-sm font-semibold">Lifecycle audit (последнее событие)</h3>
          <div className="text-sm font-medium">{auditActionLabel(detail.latest_lifecycle_transition.action)}</div>
          <div className="text-sm text-zinc-600">
            {detail.latest_lifecycle_transition.transition_from ?? "—"} → {detail.latest_lifecycle_transition.transition_to ?? "—"}
          </div>
          {detail.latest_lifecycle_transition.reason ? (
            <div className="text-sm text-zinc-600">{detail.latest_lifecycle_transition.reason}</div>
          ) : null}
          <div className="text-xs text-zinc-500">{formatDateTime(detail.latest_lifecycle_transition.created_at)}</div>
          <div className="text-[10px] text-zinc-400">{detail.latest_lifecycle_transition.action}</div>
        </section>
      ) : (
        <p className="text-sm text-zinc-500" data-testid="document-lifecycle-empty">
          {doc.status === "CREATED" ? "Документ ещё не передан на подпись" : "Lifecycle history пока отсутствует"}
        </p>
      )}

      {detail.promotion ? (
        <section className="rounded-xl border p-4 dark:border-zinc-800">
          <h3 className="mb-3 text-sm font-semibold">Promotion provenance</h3>
          <div className="text-sm">
            Promotion #{detail.promotion.id} · workspace v{detail.promotion.workspace_version}
            <div className="text-xs text-zinc-500">{formatDateTime(detail.promotion.promoted_at)}</div>
          </div>
        </section>
      ) : null}

      <ConfirmDialog
        open={readyOpen}
        title="Передать на подпись"
        message="Документ перейдёт в статус READY_FOR_SIGNATURE."
        details={
          blockers.length ? (
            <div className="text-red-700" data-testid="readiness-blockers">
              Блокеры: {blockers.map((b) => b.code).join(", ")}
            </div>
          ) : null
        }
        confirmLabel="Передать"
        onCancel={() => setReadyOpen(false)}
        onConfirm={() => {
          if (blockers.length) {
            setError("Документ не прошёл проверку готовности");
            setReadyOpen(false);
            return;
          }
          void runAction(async () => {
            const preview = await validateReadyForSignature(documentId, doc.version);
            setReadinessPreview(preview.readiness_validation);
            if (preview.readiness_validation.has_errors) {
              setError("Документ не прошёл проверку готовности");
              setReadyOpen(false);
              return;
            }
            const result = await markReadyForSignature(documentId, doc.version);
            setDetail(result.document);
            setToast(result.idempotent_replay ? "Уже в очереди подписи (replay)" : "Документ передан на подпись");
            setReadyOpen(false);
            await reload();
          });
        }}
      />

      <ConfirmDialog
        open={returnOpen}
        title="Вернуть из очереди подписи"
        message="Официальный текст не изменяется. Workspace не размораживается. Возврат только снимает документ с очереди подписи."
        details={
          <textarea
            className="mt-2 w-full rounded border p-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            rows={3}
            placeholder="Причина (обязательно)"
            value={returnReason}
            onChange={(e) => setReturnReason(e.target.value)}
          />
        }
        confirmLabel="Вернуть"
        onCancel={() => setReturnOpen(false)}
        onConfirm={() => {
          const reason = returnReason.trim();
          if (!reason) {
            setError("Укажите причину возврата");
            return;
          }
          void runAction(async () => {
            await returnToCreated(documentId, reason, doc.version);
            setToast("Документ возвращён в CREATED");
            setReturnOpen(false);
            setReturnReason("");
            await reload();
          });
        }}
      />
    </div>
  );
}

function OfficialTextSection({ title, items }: { title: string; items: DocumentLocalization[] }) {
  return (
    <section className="rounded-xl border p-4 dark:border-zinc-800">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {!items.length ? (
        <p className="text-sm text-zinc-500">Нет локализаций</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="rounded-lg border p-3 dark:border-zinc-700">
              <div className="mb-1 text-xs text-zinc-500">
                {item.block_type} · seq {item.sequence}
              </div>
              <CompactFingerprint value={item.content_fingerprint} label="fp" />
              <textarea readOnly className="w-full rounded border bg-zinc-50 p-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" rows={4} value={item.official_text} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
