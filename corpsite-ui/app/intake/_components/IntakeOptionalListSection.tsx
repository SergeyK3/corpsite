"use client";

import * as React from "react";

type Props = {
  title: string;
  declaredEmpty: boolean;
  readOnly?: boolean;
  testIdPrefix: string;
  onDeclaredEmptyChange: (declaredEmpty: boolean) => void;
  children: React.ReactNode;
};

export default function IntakeOptionalListSection({
  title,
  declaredEmpty,
  readOnly,
  testIdPrefix,
  onDeclaredEmptyChange,
  children,
}: Props) {
  return (
    <section className="space-y-3" data-testid={`${testIdPrefix}-section`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{title}</h2>
        {!readOnly ? (
          <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
            <input
              type="checkbox"
              checked={declaredEmpty}
              data-testid={`${testIdPrefix}-none-checkbox`}
              onChange={(event) => onDeclaredEmptyChange(event.target.checked)}
            />
            Нет сведений
          </label>
        ) : declaredEmpty ? (
          <span className="text-sm text-zinc-500" data-testid={`${testIdPrefix}-none-label`}>
            Нет сведений
          </span>
        ) : null}
      </div>
      {declaredEmpty ? (
        <p className="text-sm text-zinc-500" data-testid={`${testIdPrefix}-none-message`}>
          Раздел отмечен как «Нет сведений».
        </p>
      ) : (
        children
      )}
    </section>
  );
}
