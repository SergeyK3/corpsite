import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CurrentUserProvider } from "@/lib/currentUser";
import {
  ControlListExportUiError,
  exportControlListFile,
} from "../_lib/controlListExport.client";
import ControlListExportPageClient from "./ControlListExportPageClient";

vi.mock("../_lib/controlListExport.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/controlListExport.client")>();
  return { ...actual, exportControlListFile: vi.fn() };
});

function renderPage(allowed: boolean) {
  return render(
    <CurrentUserProvider value={{ user_id: 7, has_control_list_export: allowed }}>
      <ControlListExportPageClient />
    </CurrentUserProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ControlListExportPageClient", () => {
  it("shows the compact PII warning and accessible action only with capability", () => {
    const { rerender } = renderPage(false);
    expect(screen.queryByRole("button", { name: "Экспортировать в Excel" })).not.toBeInTheDocument();

    rerender(
      <CurrentUserProvider value={{ user_id: 7, has_control_list_export: true }}>
        <ControlListExportPageClient />
      </CurrentUserProvider>,
    );
    expect(screen.getByRole("heading", { name: "Экспорт контрольного списка" })).toBeInTheDocument();
    expect(screen.getByText(/данные активного персонала/i)).toBeInTheDocument();
    expect(screen.getByText(/содержит персональные данные/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Экспортировать в Excel" })).toBeEnabled();
  });

  it("locks immediately against double click and exposes a textual loading state", async () => {
    let resolve!: (value: "downloaded") => void;
    vi.mocked(exportControlListFile).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    renderPage(true);
    const button = screen.getByRole("button", { name: "Экспортировать в Excel" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(exportControlListFile).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Формирование файла…" })).toBeDisabled();
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
    resolve("downloaded");
    expect(await screen.findByRole("status")).toHaveTextContent("Сохранение выполняется браузером");
  });

  it.each([
    ["FORBIDDEN", "Недостаточно прав для экспорта контрольного списка"],
    ["CONFLICT", "Обнаружены ошибки основных назначений. Файл не сформирован."],
    ["SERVER", "Не удалось сформировать файл. Повторите попытку или обратитесь к администратору"],
    ["INTEGRITY", "Не удалось проверить целостность файла. Файл не сохранён."],
    ["WRITE", "Не удалось записать выбранный файл. Повторный запрос к серверу не выполнялся."],
  ] as const)("shows a safe message for %s", async (kind, message) => {
    vi.mocked(exportControlListFile).mockRejectedValue(new ControlListExportUiError(kind));
    renderPage(true);
    fireEvent.click(screen.getByRole("button", { name: "Экспортировать в Excel" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("alert")).not.toHaveTextContent(/SQL|traceback|employee_id|ИИН/i);
  });

  it("shows no error when the system picker is cancelled", async () => {
    vi.mocked(exportControlListFile).mockResolvedValue("cancelled");
    renderPage(true);
    fireEvent.click(screen.getByRole("button", { name: "Экспортировать в Excel" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Экспортировать в Excel" })).toBeEnabled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
