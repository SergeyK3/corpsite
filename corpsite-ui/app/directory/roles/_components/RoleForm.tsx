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
      description: values.description.trim(),
      is_active: !!values.is_active,
    };

    await onSubmit(payload);
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-[#050816] text-zinc-100">
      <div className="flex items-start justify-between border-b border-zinc-800 px-6 py-6">
        <div>
          <h2 className="text-2xl font-semibold leading-tight text-zinc-100">
            {mode === "create" ? "Создание записи" : "Редактирование записи"}
          </h2>
          <p className="mt-1 text-sm text-zinc-400">Роли</p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
        >
          Закрыть
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          {!!error && (
            <div className="rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label htmlFor="role_code" className="text-sm font-medium text-zinc-200">
              Код роли <span className="text-red-400">*</span>
            </label>
            <input
              id="role_code"
              name="role_code"
              type="text"
              value={values.role_code}
              onChange={(e) => setField("role_code", e.target.value)}
              placeholder="Например: TEST_ROLE"
              autoComplete="off"
              spellCheck={false}
              className="h-12 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
              style={{ colorScheme: "dark" }}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="role_name" className="text-sm font-medium text-zinc-200">
              Название <span className="text-red-400">*</span>
            </label>
            <input
              id="role_name"
              name="role_name"
              type="text"
              value={values.role_name}
              onChange={(e) => setField("role_name", e.target.value)}
              placeholder="Например: Тестовая роль"
              autoComplete="off"
              spellCheck={false}
              className="h-12 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
              style={{ colorScheme: "dark" }}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="description" className="text-sm font-medium text-zinc-200">
              Описание
            </label>
            <textarea
              id="description"
              name="description"
              value={values.description}
              onChange={(e) => setField("description", e.target.value)}
              placeholder="Краткое описание роли"
              rows={6}
              spellCheck={false}
              className="min-h-[140px] rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
              style={{ colorScheme: "dark" }}
            />
          </div>

          <label className="flex items-center gap-3 text-sm text-zinc-200">
            <input
              type="checkbox"
              checked={values.is_active}
              onChange={(e) => setField("is_active", e.target.checked)}
              className="h-4 w-4 rounded border-zinc-700 bg-zinc-900"
            />
            Активна
          </label>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-zinc-800 px-6 py-4">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
          disabled={saving}
        >
          Закрыть
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