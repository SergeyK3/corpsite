"use client";
import { useId } from "react";
import type { HireNewEmployee } from "../_lib/personnelOrderHireNewEmployee";

export default function PersonnelOrderHireEmployeeFields({ isNew, value, onModeChange, onChange, newDisabled = false, disabled = false }: {
  isNew: boolean; value: HireNewEmployee; onModeChange: (isNew: boolean) => void;
  onChange: (value: HireNewEmployee) => void; newDisabled?: boolean; disabled?: boolean;
}) {
  const name = useId();
  return <fieldset disabled={disabled} className="space-y-3" data-testid="hire-employee-fields">
    <legend className="text-sm font-medium">Сотрудник</legend>
    <div className="flex flex-wrap gap-4 text-sm">
      <label><input type="radio" name={name} checked={!isNew} onChange={() => onModeChange(false)} /> Сотрудник из списка</label>
      <label><input type="radio" name={name} checked={isNew} disabled={newDisabled} onChange={() => onModeChange(true)} data-testid="personnel-order-pending-new-employee" /> Новый сотрудник</label>
    </div>
    {newDisabled ? <p className="text-xs text-zinc-500" data-testid="personnel-order-pending-new-employee-reset-blocked">Сброс сотрудника в сохранённом пункте пока не поддерживается.</p> : null}
    {isNew ? <>
      <div className="grid gap-3 sm:grid-cols-3">{([
        ["last_name", "Фамилия"], ["first_name", "Имя"], ["middle_name", "Отчество (необязательно)"],
      ] as const).map(([key, label]) => <label key={key} className="space-y-1 text-sm">{label}
        <input aria-label={label} value={value[key]} maxLength={100} required={key !== "middle_name"} autoComplete="off"
          onChange={event => onChange({ ...value, [key]: event.target.value })}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100" />
      </label>)}</div>
      <p className="text-xs text-zinc-500">ФИО используется в RU и KK в указанном написании. Карточка создаётся только при применении приказа после проверки возможного дубликата.</p>
    </> : null}
  </fieldset>;
}
