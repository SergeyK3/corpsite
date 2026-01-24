"use client";

import { useEffect, useMemo, useState } from "react";

type Props = {
  initialUserId: number;
  onApply: (userId: number) => void;
};

const LS_KEY = "corpsite.devUserId";

export default function DevUserSwitcher({ initialUserId, onApply }: Props) {
  const [value, setValue] = useState<string>(String(initialUserId));

  useEffect(() => {
    try {
      const v = localStorage.getItem(LS_KEY);
      if (v && /^\d+$/.test(v)) setValue(v);
    } catch {}
  }, []);

  const parsed = useMemo(() => {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : null;
  }, [value]);

  const canApply = parsed !== null;

  return (
    <div className="devbar">
      <div className="devbar__left">
        <div className="brand">Corpsite / ЛК задач</div>
      </div>

      <div className="devbar__right">
        <label className="devbar__label">Dev User ID</label>
        <input
          className="input"
          value={value}
          onChange={(e) => setValue(e.target.value.replace(/[^\d]/g, ""))}
          placeholder="34"
          inputMode="numeric"
        />
        <button
          className="btn"
          disabled={!canApply}
          onClick={() => {
            if (parsed === null) return;
            try {
              localStorage.setItem(LS_KEY, String(parsed));
            } catch {}
            onApply(parsed);
          }}
        >
          Apply
        </button>
      </div>
    </div>
  );
}
