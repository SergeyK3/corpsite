"use client";

import { TaskListItem } from "@/lib/types";

type Props = {
  items: TaskListItem[];
  selectedTaskId: number | null;
  onSelect: (taskId: number) => void;
};

export default function TaskList({ items, selectedTaskId, onSelect }: Props) {
  return (
    <div className="list">
      {items.length === 0 ? (
        <div className="muted">Нет задач.</div>
      ) : (
        items.map((t) => {
          const active = selectedTaskId === t.task_id;
          const deadline = t.deadline ? String(t.deadline) : "";
          return (
            <button
              key={t.task_id}
              className={`list__item ${active ? "list__item--active" : ""}`}
              onClick={() => onSelect(t.task_id)}
            >
              <div className="list__top">
                <div className="list__title">
                  <span className="mono">#{t.task_id}</span> {t.title}
                </div>
                <div className="badge">{t.status}</div>
              </div>
              <div className="list__meta">
                {deadline ? <span>срок: {deadline}</span> : <span className="muted">срок: —</span>}
              </div>
            </button>
          );
        })
      )}
    </div>
  );
}
