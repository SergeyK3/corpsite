"use client";
import { useState } from "react";

export default function PersonnelOrderAllowancePercent({value, onChange, inputClassName}: {
  value: string; onChange: (value: string) => void; inputClassName: string;
}) {
  const [custom, setCustom] = useState(false);
  const other = custom || (value !== "" && !["25", "50"].includes(value));
  return <div className="space-y-2">
    <label className="block text-sm font-medium">Доплата
      <select aria-label="Доплата" required className={inputClassName} value={other ? "other" : value}
        onChange={event => {
          const next = event.target.value;
          setCustom(next === "other");
          onChange(next === "other" ? (other ? value : "") : next);
        }}>
        <option value="">Выберите доплату</option>
        <option value="25">+25%</option><option value="50">+50%</option>
        <option value="other">Другое</option>
      </select>
    </label>
    {other ? <label className="block text-sm font-medium">Процент доплаты
      <input aria-label="Процент доплаты" type="number" required min={1} max={100} step={1}
        value={value} onChange={event => onChange(event.target.value)} className={inputClassName}/>
    </label> : null}
  </div>;
}
