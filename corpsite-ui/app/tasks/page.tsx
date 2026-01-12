"use client";

import { useEffect, useMemo, useState } from "react";
import DevUserSwitcher from "@/components/DevUserSwitcher";
import TaskList from "@/components/TaskList";
import TaskPanel from "@/components/TaskPanel";
import { apiGetTask, apiGetTasks, apiPostTaskAction } from "@/lib/api";
import { APIError, TaskDetails, TaskListItem, TaskAction } from "@/lib/types";

function envNum(name: string, fallback: number): number {
  const v = (process.env[name] ?? "").toString().trim();
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

export default function TasksPage() {
  const defaultUserId = useMemo(() => envNum("NEXT_PUBLIC_DEV_X_USER_ID", 34), []);
  const [devUserId, setDevUserId] = useState<number>(defaultUserId);

  const [items, setItems] = useState<TaskListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<APIError | null>(null);

  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [task, setTask] = useState<TaskDetails | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [taskError, setTaskError] = useState<APIError | null>(null);

  async function loadList(userId: number) {
    setListLoading(true);
    setListError(null);
    try {
      const data = await apiGetTasks({ devUserId: userId, limit: 50, offset: 0 });
      setItems(data);
      if (!selectedTaskId && data.length > 0) {
        setSelectedTaskId(data[0].task_id);
      }
    } catch (e: any) {
      setListError(e);
      setItems([]);
      setSelectedTaskId(null);
      setTask(null);
    } finally {
      setListLoading(false);
    }
  }

  async function loadTask(userId: number, taskId: number) {
    setTaskLoading(true);
    setTaskError(null);
    try {
      const data = await apiGetTask({ devUserId: userId, taskId });
      setTask(data);
    } catch (e: any) {
      setTaskError(e);
      setTask(null);
    } finally {
      setTaskLoading(false);
    }
  }

  async function runAction(action: TaskAction, payload: { report_link?: string; current_comment?: string }) {
    if (!selectedTaskId) return;
    setTaskError(null);
    try {
      await apiPostTaskAction({ devUserId, taskId: selectedTaskId, action, payload });
      await loadTask(devUserId, selectedTaskId);
      await loadList(devUserId);
    } catch (e: any) {
      setTaskError(e);
    }
  }

  useEffect(() => {
    loadList(devUserId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devUserId]);

  useEffect(() => {
    if (!selectedTaskId) return;
    loadTask(devUserId, selectedTaskId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTaskId, devUserId]);

  return (
    <div className="app">
      <DevUserSwitcher
        initialUserId={defaultUserId}
        onApply={(uid) => {
          setDevUserId(uid);
          setSelectedTaskId(null);
          setTask(null);
        }}
      />

      <div className="content">
        <div className="left">
          <div className="sectionTitle">Все задачи</div>
          {listLoading && <div>Loading…</div>}
          {listError && <div className="error">Ошибка списка: ({listError.status}) {listError.message}</div>}
          <TaskList items={items} selectedTaskId={selectedTaskId} onSelect={(id) => setSelectedTaskId(id)} />
        </div>

        <div className="right">
          <div className="sectionTitle">Карточка</div>
          <TaskPanel task={task} loading={taskLoading} error={taskError} onAction={runAction} />
        </div>
      </div>
    </div>
  );
}
