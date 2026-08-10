import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ControlListEntryDialog from "./ControlListEntryDialog";
import { getEmployees } from "../_lib/api.client";

vi.mock("../_lib/api.client", () => ({
  getEmployees: vi.fn(),
  mapApiErrorToMessage: (error: unknown) => String(error),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  vi.mocked(getEmployees).mockReset();
});

function searchFor(surname: string) {
  fireEvent.change(screen.getByPlaceholderText("Фамилия"), { target: { value: surname } });
  fireEvent.click(screen.getByRole("button", { name: "Найти" }));
}

describe("ControlListEntryDialog", () => {
  it("shows active operational employees and their personnel card links", async () => {
    vi.mocked(getEmployees).mockResolvedValue({
      items: [
        {
          id: "42",
          fio: "Иванова Анна Сергеевна",
          department: { id: 7, name: "Отдел кадров" },
          position: { id: 11, name: "Менеджер УЧР" },
          org_unit: null,
          rate: 1,
          status: "active",
          date_from: null,
          date_to: null,
        },
      ],
      total: 1,
    });

    render(<ControlListEntryDialog open onClose={vi.fn()} />);
    searchFor("Иванова");

    expect(await screen.findByText("Сотрудник уже существует в оперативном контуре")).toBeInTheDocument();
    expect(screen.getByText("Иванова Анна Сергеевна")).toBeInTheDocument();
    expect(screen.getByText("Отделение: Отдел кадров")).toBeInTheDocument();
    expect(screen.getByText("Должность: Менеджер УЧР")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть карточку" })).toHaveAttribute(
      "href",
      "/directory/personnel/employees/42/card"
    );
    expect(getEmployees).toHaveBeenCalledTimes(1);
    expect(getEmployees).toHaveBeenCalledWith({
      status: "active",
      q: "Иванова",
      include_applicants: false,
    });
    expect(screen.queryByText("Импортная карточка с расширенными сведениями будет подключена на следующем этапе")).not.toBeInTheDocument();
    expect(screen.queryByText("Перенос проверенных документов в постоянное досье будет подключён на следующем этапе")).not.toBeInTheDocument();
  });

  it("shows the control-list enrollment steps when no active operational employee is found", async () => {
    vi.mocked(getEmployees).mockResolvedValue({ items: [], total: 0 });

    render(<ControlListEntryDialog open onClose={vi.fn()} />);
    searchFor("Несуществующая");

    expect(await screen.findByText("Сотрудник в оперативном контуре не найден")).toBeInTheDocument();
    expect(screen.getByText("1. Поиск в контрольном списке")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Найти в контрольном списке" })).toBeInTheDocument();
    expect(screen.getByText("2. Импортная карточка с расширенными сведениями")).toBeInTheDocument();
    expect(screen.getByText("Сначала выберите человека из контрольного списка.")).toBeInTheDocument();
    expect(screen.getByText("3. Добавление сотрудника в раздел «Персонал»")).toBeInTheDocument();
    expect(screen.getByText("Сначала выберите импортную карточку.")).toBeInTheDocument();
    expect(getEmployees).toHaveBeenCalledTimes(1);
    expect(getEmployees).toHaveBeenCalledWith({
      status: "active",
      q: "Несуществующая",
      include_applicants: false,
    });
  });
});
