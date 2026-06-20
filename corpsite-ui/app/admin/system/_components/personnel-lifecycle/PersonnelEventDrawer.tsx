// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/PersonnelEventDrawer.tsx
"use client";

import type { PersonnelEventDetail } from "../../_lib/personnelLifecycleApi.client";
import { formatActorLabel, formatDateTime } from "../../_lib/adminSystemLabels";
import JsonViewer from "../shared/JsonViewer";

type PersonnelEventDrawerProps = {
  event: PersonnelEventDetail | null;
  loading?: boolean;
  open: boolean;
  onClose: () => void;
};

export default function PersonnelEventDrawer({
  event,
  loading = false,
  open,
  onClose,
}: PersonnelEventDrawerProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/30"
      role="dialog"
      aria-modal="true"
      data-testid="personnel-event-drawer"
    >
      <div className="h-full w-full max-w-xl overflow-y-auto border-l border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">
            Event #{event?.personnel_event_id ?? "…"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded border px-2 py-1 text-sm dark:border-zinc-600"
          >
            Закрыть
          </button>
        </div>

        {loading ? (
          <p className="text-sm text-zinc-500" data-testid="personnel-event-drawer-loading">
            Загрузка…
          </p>
        ) : !event ? (
          <p className="text-sm text-zinc-500">Событие не найдено.</p>
        ) : (
          <div className="space-y-4 text-sm">
            <dl className="grid gap-2 sm:grid-cols-2">
              <Field label="event_type" value={event.event_type} />
              <Field label="status" value={event.status} />
              <Field label="person_key" value={event.person_key} />
              <Field label="assignment_key" value={event.assignment_key ?? "—"} />
              <Field label="previous_snapshot_id" value={String(event.previous_snapshot_id)} />
              <Field label="snapshot_id" value={String(event.snapshot_id)} />
              <Field label="detected_at" value={formatDateTime(event.detected_at)} />
              <Field label="resolved_at" value={formatDateTime(event.resolved_at)} />
              <Field label="source_event_id" value={event.source_event_id != null ? String(event.source_event_id) : "—"} />
              <Field
                label="resolved_by"
                value={formatActorLabel(event.resolved_by_user_id)}
              />
            </dl>

            <JsonViewer title="old value" value={event.old_value} testId="personnel-event-old-value" />
            <JsonViewer title="new value" value={event.new_value} testId="personnel-event-new-value" />
            <JsonViewer
              title="effective old value"
              value={event.effective_old_value}
              testId="personnel-event-effective-old-value"
            />
            <JsonViewer
              title="effective new value"
              value={event.effective_new_value}
              testId="personnel-event-effective-new-value"
            />
            <JsonViewer title="metadata" value={event.metadata} testId="personnel-event-metadata" />
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="font-medium break-all">{value}</dd>
    </div>
  );
}
