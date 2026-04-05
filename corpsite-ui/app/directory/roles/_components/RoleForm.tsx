// FILE: corpsite-ui/app/directory/roles/_components/RoleForm.tsx
"use client";

import * as React from "react";

export type RoleFormValues = {
  role_code: string;
  role_name: string;
  description: string;
  is_active: boolean;
};

type RoleFormProps = {
  mode: "create" | "edit";
  initialValues: RoleFormValues;
  saving?: boolean;
  error?: string | null;
  onSubmit: (values: RoleFormValues) => Promise<void> | void;
  onCancel: () => void;
};

export default function RoleForm({
  mode,
  initialValues,
  saving = false,
  error = null,
  onSubmit,
  onCancel,
}: RoleFormProps) {
  const [values, setValues] = React.useState<RoleFormValues>(initialValues);

  React.useEffect(() => {
    setValues(initialValues);
  }, [initialValues]);

  function setField<K extends keyof RoleFormValues>(key: K, value: RoleFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const payload: RoleFormValues = {
      role_code: values.role_code.trim(),
      role_name: values.role_name.trim(),
      description: "",
      is_active: !!values.is_active,
    };

    await onSubmit(payload);
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white text-zinc-900">
      <div className="flex items-start justify-between border-b border-zinc-200 px-6 py-5">
        <div>
          <h2 className="text-2xl font-semibold leading-tight text-zinc-900">
            {mode === "create" ? "Создать роль" : "Редактировать роль"}
          </h2>
          <p className="mt-1 text-sm text-zinc-600">Справочник ролей</p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-800 transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Закрыть
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          {!!error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label htmlFor="role_code" className="text-sm font-medium text-zinc-800">
              Код роли <span className="text-red-400">*</span>
            </label>
            <input
              id="role_code"
              name="role_code"
              type="text"
              value={values.role_code}
              onChange={(e) => setField("role_code", e.target.value)}
              placeholder="Например: QUALITY_EXPERT"
              autoComplete="off"
              spellCheck={false}
              disabled={saving}
              className="h-11 rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-60"
              style={{ colorScheme: "dark" }}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="role_name" className="text-sm font-medium text-zinc-800">
              Название <span className="text-red-400">*</span>
            </label>
            <input
              id="role_name"
              name="role_name"
              type="text"
              value={values.role_name}
              onChange={(e) => setField("role_name", e.target.value)}
              placeholder="Например: Эксперт по качеству"
              autoComplete="off"
              spellCheck={false}
              disabled={saving}
              className="h-11 rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-60"
              style={{ colorScheme: "dark" }}
              required
            />
          </div>

          <label className="flex items-center gap-3 text-sm text-zinc-800">
            <input
              type="checkbox"
              checked={values.is_active}
              onChange={(e) => setField("is_active", e.target.checked)}
              disabled={saving}
              className="h-4 w-4 rounded border-zinc-300 bg-zinc-100 disabled:cursor-not-allowed"
            />
            Активна
          </label>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-zinc-200 px-6 py-4">
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-800 transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Отмена
        </button>

        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
      </div>
    </form>
  );
}