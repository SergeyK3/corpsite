"use client";

import { useRef, useState } from "react";
import { downloadTableExcel, EXCEL_BUTTON_CLASS, type ExcelTable } from "@/lib/tableExport";

export default function ExportExcelButton({ load, filename, disabled = false }: {
  load: () => Promise<ExcelTable>;
  filename: string;
  disabled?: boolean;
}) {
  const busy = useRef(false);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  async function exportExcel() {
    if (busy.current) return;
    busy.current = true;
    setExporting(true);
    setMessage(null);
    try {
      await downloadTableExcel(await load(), filename);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Не удалось выгрузить список в Excel.");
    } finally {
      busy.current = false;
      setExporting(false);
    }
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-3">
      <button type="button" disabled={disabled || exporting} onClick={() => void exportExcel()} className={EXCEL_BUTTON_CLASS}>
        {exporting ? "Выгрузка…" : "Выгрузить в Excel"}
      </button>
      {message ? <span role="status" className="text-sm">{message}</span> : null}
    </span>
  );
}
