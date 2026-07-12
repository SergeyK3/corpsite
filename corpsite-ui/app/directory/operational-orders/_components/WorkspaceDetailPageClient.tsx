"use client";

import * as React from "react";
import Link from "next/link";

import { apiAuthMe } from "@/lib/api";
import type { MeInfo } from "@/lib/types";
import ConfirmDialog from "@/app/admin/system/_components/shared/ConfirmDialog";
import ErrorBanner, { SuccessBanner } from "@/app/admin/system/_components/shared/ErrorBanner";

import {
  getDocument,
  getWorkspace,
  mapOoApiError,
  markEditorialPackageReady,
  promoteWorkspace,
  resolveClarification,
  validateEditorialPackage,
  validateWorkspace,
  patchBlockEffectiveText,
} from "../_lib/api";
import { isVersionConflictError } from "../_lib/errors";
import {
  canOperateWorkspace,
  canPromoteWorkspace,
  getOperationalOrdersPermissions,
} from "../_lib/permissions";
import { formatDateTime, formatPartyReference } from "../_lib/mappers";
import { draftingPathLabel, isWorkspaceFrozen } from "../_lib/status";
import { buildWorkspaceTimeline } from "../_lib/workspaceTimeline";
import type { DocumentDetail, DraftBlock, WorkspaceDetail } from "../_lib/types";
import AuditSections from "./AuditSections";
import BilingualReconciliationsSection from "./BilingualReconciliationsSection";
import ContentConfirmationsSection from "./ContentConfirmationsSection";
import FrozenWorkspaceBanner from "./FrozenWorkspaceBanner";
import TranslationAssignmentsSection from "./TranslationAssignmentsSection";
import ValidationPanel from "./ValidationPanel";
import WorkspaceProgressTimeline from "./WorkspaceProgressTimeline";
import WorkspaceStageBadge from "./WorkspaceStageBadge";

type Props = { workspaceId: number };

export default function WorkspaceDetailPageClient({ workspaceId }: Props) {
  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [detail, setDetail] = React.useState<WorkspaceDetail | null>(null);
  const [linkedDocument, setLinkedDocument] = React.useState<DocumentDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [actionPending, setActionPending] = React.useState(false);
  const [editorialValidation, setEditorialValidation] = React.useState<WorkspaceDetail["validation"] | null>(null);
  const [promoteOpen, setPromoteOpen] = React.useState(false);
  const [promotionResult, setPromotionResult] = React.useState<{
    documentId: number;
    replay: boolean;
    revisionRecommended: boolean;
  } | null>(null);

  const reload = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWorkspace(workspaceId);
      setDetail(data);
      setEditorialValidation(null);
      if (data.workspace.document_id && isWorkspaceFrozen(data.workspace.stage)) {
        try {
          const doc = await getDocument(data.workspace.document_id);
          setLinkedDocument(doc);
        } catch {
          setLinkedDocument(null);
        }
      } else {
        setLinkedDocument(null);
      }
    } catch (e) {
      setDetail(null);
      setLinkedDocument(null);
      setError(mapOoApiError(e, "Не удалось загрузить рабочее пространство"));
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  React.useEffect(() => {
    apiAuthMe().then(setMe).catch(() => setMe(null));
  }, []);

  React.useEffect(() => {
    void reload();
  }, [reload]);

  const frozen = detail ? isWorkspaceFrozen(detail.workspace.stage) : false;
  const canOperate = detail ? canOperateWorkspace(me, detail.workspace.record_creator_user_id) : false;
  const perms = getOperationalOrdersPermissions(me);

  async function runAction(fn: () => Promise<void>) {
    setActionPending(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      if (isVersionConflictError(e)) {
        setError("Рабочее пространство изменилось. Обновите страницу.");
      } else {
        setError(mapOoApiError(e, "Не удалось выполнить действие"));
      }
    } finally {
      setActionPending(false);
    }
  }

  function handleSectionError(err: unknown) {
    setError(mapOoApiError(err, "Не удалось выполнить действие"));
  }

  async function saveBlock(block: DraftBlock, text: string) {
    if (!detail) return;
    await runAction(async () => {
      const updated = await patchBlockEffectiveText(workspaceId, block.block_id, text, detail.workspace.version);
      setDetail(updated);
      setToast("Текст блока сохранён");
    });
  }

  async function handlePromote() {
    if (!detail) return;
    await runAction(async () => {
      const result = await promoteWorkspace(workspaceId, detail.workspace.version);
      setPromotionResult({
        documentId: result.document.document.document_id,
        replay: result.idempotent_replay,
        revisionRecommended: result.revision_recommended,
      });
      setToast(result.idempotent_replay ? "Официальный проект уже существует" : "Официальный проект создан");
      await reload();
    });
    setPromoteOpen(false);
  }

  if (loading && !detail) {
    return <div className="py-8 text-center text-sm text-zinc-500">Загрузка…</div>;
  }

  if (error && !detail) {
    return <ErrorBanner message={error} />;
  }

  if (!detail) return null;

  const ws = detail.workspace;
  const ruBlocks = detail.blocks.filter((b) => b.locale === "ru");
  const kkBlocks = detail.blocks.filter((b) => b.locale === "kk");
  const openClarifications = detail.clarifications.filter((c) => c.status === "OPEN");
  const timeline = buildWorkspaceTimeline(ws.stage);
  const revisionRecommended =
    promotionResult?.revisionRecommended ||
    linkedDocument?.revision_recommended ||
    false;

  return (
    <div className="space-y-6" data-testid="workspace-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/directory/operational-orders" className="text-sm text-blue-600 hover:underline">
            ← К списку
          </Link>
          <h2 className="mt-1 text-lg font-semibold">Workspace #{ws.workspace_id}</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <WorkspaceStageBadge stage={ws.stage} />
            <span className="text-xs text-zinc-500">v{ws.version}</span>
          </div>
        </div>
        <button type="button" onClick={() => void reload()} className="rounded-lg border px-3 py-1.5 text-sm dark:border-zinc-700">
          Обновить
        </button>
      </div>

      {frozen ? (
        <FrozenWorkspaceBanner
          documentId={ws.document_id}
          promotedAt={linkedDocument?.promotion?.promoted_at}
          workspaceDriftDetected={linkedDocument?.workspace_drift_detected}
          revisionRecommended={revisionRecommended}
        />
      ) : null}

      <ErrorBanner message={error} />
      <SuccessBanner message={toast} />

      <WorkspaceProgressTimeline steps={timeline} />

      <section className="grid gap-2 rounded-xl border p-4 text-sm md:grid-cols-2 dark:border-zinc-800">
        <div>Подразделение: #{ws.submitting_org_unit_id}</div>
        <div>Автор: {formatPartyReference(ws.content_author_type, ws.content_author_reference)}</div>
        <div>Создатель записи: #{ws.record_creator_user_id}</div>
        <div>Путь: {draftingPathLabel(ws.drafting_path)}</div>
        <div>Создан: {formatDateTime(ws.created_at)}</div>
        <div>Обновлён: {formatDateTime(ws.updated_at)}</div>
      </section>

      <BlockSection title="Текст RU" blocks={ruBlocks} frozen={frozen} canEdit={canOperate && !frozen} onSave={saveBlock} pending={actionPending} />
      <BlockSection title="Текст KK" blocks={kkBlocks} frozen={frozen} canEdit={canOperate && !frozen} onSave={saveBlock} pending={actionPending} />

      <ValidationPanel
        title="Intake Validation"
        validation={detail.validation}
        onRevalidate={
          canOperate && !frozen
            ? () =>
                void runAction(async () => {
                  const updated = await validateWorkspace(workspaceId, detail.workspace.version);
                  setDetail(updated);
                })
            : undefined
        }
        revalidateDisabled={actionPending}
        revalidatePending={actionPending}
      />

      <ValidationPanel
        title="Editorial Package Validation"
        validation={editorialValidation}
        onRevalidate={
          perms.intake_read || perms.intake_operate
            ? () =>
                void runAction(async () => {
                  const res = await validateEditorialPackage(workspaceId, detail.workspace.version);
                  setEditorialValidation(res.validation);
                })
            : undefined
        }
        revalidateDisabled={actionPending}
        revalidatePending={actionPending}
      />

      <section className="rounded-xl border p-4 dark:border-zinc-800" id="section-clarifications">
        <h3 className="mb-3 text-sm font-semibold">Уточнения</h3>
        {!openClarifications.length ? (
          <p className="text-sm text-zinc-500" data-testid="clarifications-empty">
            Открытых уточнений нет
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {detail.clarifications.map((c) => (
              <li key={c.clarification_id} className="rounded-lg border px-3 py-2 dark:border-zinc-700">
                <div className="font-medium">
                  {c.code} · {c.status}
                </div>
                <div>{c.message}</div>
                {c.status === "OPEN" && canOperate && !frozen ? (
                  <button
                    type="button"
                    className="mt-2 rounded border px-2 py-1 text-xs"
                    disabled={actionPending}
                    onClick={() =>
                      void runAction(async () => {
                        const updated = await resolveClarification(workspaceId, c.clarification_id, "Resolved via UI", detail.workspace.version);
                        setDetail(updated);
                      })
                    }
                  >
                    Закрыть уточнение
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <TranslationAssignmentsSection
        detail={detail}
        frozen={frozen}
        perms={perms}
        me={me}
        pending={actionPending}
        onUpdated={setDetail}
        onError={handleSectionError}
      />

      <ContentConfirmationsSection
        detail={detail}
        frozen={frozen}
        perms={perms}
        pending={actionPending}
        onUpdated={setDetail}
        onError={handleSectionError}
      />

      <BilingualReconciliationsSection
        detail={detail}
        frozen={frozen}
        perms={perms}
        pending={actionPending}
        onUpdated={setDetail}
        onError={handleSectionError}
      />

      <AuditSections audit={detail.audit} provenance={detail.provenance} />

      {!frozen ? (
        <section className="rounded-xl border p-4 dark:border-zinc-800">
          <h3 className="mb-3 text-sm font-semibold">Promotion</h3>
          {ws.stage === "EDITORIAL_PACKAGE_READY" && canPromoteWorkspace(me) ? (
            <button
              type="button"
              data-testid="promote-button"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              disabled={actionPending}
              onClick={() => setPromoteOpen(true)}
            >
              Создать официальный проект
            </button>
          ) : (
            <p className="text-sm text-zinc-500">
              {ws.document_id ? `Документ #${ws.document_id} создан` : "Promotion недоступен на текущей стадии"}
            </p>
          )}
          {canOperate && perms.editorial_ready && ws.stage !== "EDITORIAL_PACKAGE_READY" ? (
            <button
              type="button"
              className="mt-2 block rounded-lg border px-3 py-1.5 text-sm dark:border-zinc-700"
              disabled={actionPending}
              onClick={() =>
                void runAction(async () => {
                  const updated = await markEditorialPackageReady(workspaceId, detail.workspace.version);
                  setDetail(updated);
                  setToast("Редакционный пакет готов");
                })
              }
            >
              Отметить редакционный пакет готовым
            </button>
          ) : null}
        </section>
      ) : null}

      <ConfirmDialog
        open={promoteOpen}
        title="Создать официальный проект"
        message="Workspace будет заморожен. Будет создан immutable Document Version 1."
        confirmLabel="Создать"
        onCancel={() => setPromoteOpen(false)}
        onConfirm={() => void handlePromote()}
      />
    </div>
  );
}

function BlockSection({
  title,
  blocks,
  frozen,
  canEdit,
  onSave,
  pending,
}: {
  title: string;
  blocks: DraftBlock[];
  frozen: boolean;
  canEdit: boolean;
  onSave: (block: DraftBlock, text: string) => Promise<void>;
  pending: boolean;
}) {
  return (
    <section className="rounded-xl border p-4 dark:border-zinc-800">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {!blocks.length ? (
        <p className="text-sm text-zinc-500">Нет блоков</p>
      ) : (
        <div className="space-y-4">
          {blocks.map((block) => (
            <BlockEditor key={block.block_id} block={block} frozen={frozen} canEdit={canEdit} onSave={onSave} pending={pending} />
          ))}
        </div>
      )}
    </section>
  );
}

function BlockEditor({
  block,
  frozen,
  canEdit,
  onSave,
  pending,
}: {
  block: DraftBlock;
  frozen: boolean;
  canEdit: boolean;
  onSave: (block: DraftBlock, text: string) => Promise<void>;
  pending: boolean;
}) {
  const [text, setText] = React.useState(block.workspace_effective_text ?? block.submitted_text);

  React.useEffect(() => {
    setText(block.workspace_effective_text ?? block.submitted_text);
  }, [block]);

  return (
    <div className="rounded-lg border p-3 dark:border-zinc-700" data-testid={`block-${block.block_id}`}>
      <div className="mb-2 flex flex-wrap gap-2 text-xs text-zinc-500">
        <span>{block.block_type}</span>
        <span>seq {block.sequence}</span>
        <span>v{block.version}</span>
        <span>{block.review_state}</span>
      </div>
      <label className="block text-xs text-zinc-500">submitted_text (read-only)</label>
      <textarea readOnly className="mt-1 w-full rounded border bg-zinc-50 p-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" rows={2} value={block.submitted_text} />
      <label className="mt-2 block text-xs text-zinc-500">workspace_effective_text</label>
      <textarea
        readOnly={!canEdit || frozen}
        className="mt-1 w-full rounded border p-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        rows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {canEdit && !frozen ? (
        <button type="button" className="mt-2 rounded border px-2 py-1 text-xs disabled:opacity-50" disabled={pending} onClick={() => void onSave(block, text)}>
          Сохранить
        </button>
      ) : null}
    </div>
  );
}
