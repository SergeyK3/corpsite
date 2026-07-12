import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderEditorialTextEditor from "./PersonnelOrderEditorialTextEditor";
import type { PersonnelOrderEditorialState, PersonnelOrderItem } from "../_lib/personnelOrdersApi.client";

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return {
    ...actual,
    getPersonnelOrderEditorial: vi.fn(),
    generatePersonnelOrderEditorial: vi.fn(),
    patchPersonnelOrderEditorialBlock: vi.fn(),
    resetPersonnelOrderEditorialBlock: vi.fn(),
  };
});

import {
  generatePersonnelOrderEditorial,
  getPersonnelOrderEditorial,
  patchPersonnelOrderEditorialBlock,
  resetPersonnelOrderEditorialBlock,
} from "../_lib/personnelOrdersApi.client";

const items: PersonnelOrderItem[] = [
  {
    item_id: 10,
    order_id: 42,
    item_number: 1,
    item_type_code: "HIRE",
    item_status: "ACTIVE",
    employee_name: "Петрова Анна",
  },
];

function sampleState(overrides?: Partial<PersonnelOrderEditorialState>): PersonnelOrderEditorialState {
  return {
    order_id: 42,
    order_status: "DRAFT",
    editable: true,
    order_blocks: [
      {
        block_id: 1,
        scope: "order",
        locale: "kk",
        block_type: "title",
        generated_text: "Жұмысқа қабылдау туралы",
        override_text: null,
        effective_text: "Жұмысқа қабылдау туралы",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 2,
        scope: "order",
        locale: "kk",
        block_type: "preamble",
        generated_text: "ҚР Еңбек кодексіне сәйкес",
        override_text: null,
        effective_text: "ҚР Еңбек кодексіне сәйкес",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 3,
        scope: "order",
        locale: "kk",
        block_type: "closing",
        generated_text: "",
        override_text: null,
        effective_text: "",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 101,
        scope: "order",
        locale: "ru",
        block_type: "title",
        generated_text: "О приёме на работу",
        override_text: null,
        effective_text: "О приёме на работу",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 102,
        scope: "order",
        locale: "ru",
        block_type: "preamble",
        generated_text: "В соответствии с ТК РК",
        override_text: null,
        effective_text: "В соответствии с ТК РК",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 103,
        scope: "order",
        locale: "ru",
        block_type: "closing",
        generated_text: "",
        override_text: null,
        effective_text: "",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
    ],
    items: [
      {
        order_item_id: 10,
        item_number: 1,
        item_type_code: "HIRE",
        basis_required: true,
        blocks: [
          {
            block_id: 11,
            scope: "item",
            order_item_id: 10,
            locale: "kk",
            block_type: "body",
            generated_text: "Петрова Аннаны қабылдау",
            override_text: null,
            effective_text: "Петрова Аннаны қабылдау",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 12,
            scope: "item",
            order_item_id: 10,
            locale: "kk",
            block_type: "basis",
            generated_text: "Негіз: жеке өтініш.",
            override_text: null,
            effective_text: "Негіз: жеке өтініш.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 111,
            scope: "item",
            order_item_id: 10,
            locale: "ru",
            block_type: "body",
            generated_text: "Принять Петрову Анну",
            override_text: null,
            effective_text: "Принять Петрову Анну",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 112,
            scope: "item",
            order_item_id: 10,
            locale: "ru",
            block_type: "basis",
            generated_text: "Основание: личное заявление.",
            override_text: null,
            effective_text: "Основание: личное заявление.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
      },
    ],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelOrderEditorialTextEditor", () => {
  it("loads editorial state and shows document structure without technical fields", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-editor")).toBeInTheDocument();
    });

    expect(screen.getByText("Текст приказа")).toBeInTheDocument();
    expect(
      screen.getByText(/Редактирование казахского текста приказа/),
    ).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-editorial-locale-tabs")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-editorial-locale-kk")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-editorial-locale-ru")).toBeInTheDocument();
    expect(
      screen.queryByText(/Русский язык будет доступен на следующем этапе/i),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Заголовок")).toBeInTheDocument();
    expect(screen.getByText("Преамбула")).toBeInTheDocument();
    expect(screen.getByText("Пункт №1")).toBeInTheDocument();
    expect(screen.getByText("Петрова Анна")).toBeInTheDocument();
    expect(screen.getByText("Основание")).toBeInTheDocument();
    expect(screen.getByText("Заключительная часть")).toBeInTheDocument();

    expect(screen.queryByText(/fingerprint/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/generator_key/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/block_type/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Generated").length).toBeGreaterThan(0);
  });

  it("auto-generates full editorial state when required locales are missing in DRAFT", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    });
    vi.mocked(generatePersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42);
    });
    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
  });

  it("does not auto-generate again when both locales already exist", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
  });

  it("asks for confirmation before manual generate and regenerates all locales", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.mocked(generatePersonnelOrderEditorial).mockResolvedValue(sampleState());
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-generate")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-order-editorial-generate"));

    expect(confirmSpy).toHaveBeenCalled();
    const message = String(confirmSpy.mock.calls[0]?.[0] ?? "");
    expect(message).toContain("Пересформировать текст приказа?");
    expect(message).toContain("Будут обновлены автоматически сформированные тексты приказа.");
    expect(message).toContain("Продолжить?");
    expect(message).not.toContain("Ручные изменения");

    await waitFor(() => {
      expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42);
    });
  });

  it("shows only kk blocks on kk tab even when ru blocks are present in state", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
    expect(screen.queryByText("О приёме на работу")).not.toBeInTheDocument();
  });

  it("shows ru blocks when Russian tab is selected", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-locale-ru")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));

    await waitFor(() => {
      expect(screen.getByText("О приёме на работу")).toBeInTheDocument();
    });
    expect(screen.queryByText("Жұмысқа қабылдау туралы")).not.toBeInTheDocument();
  });

  it("saves Russian override with expected revision", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    const afterSave = sampleState();
    afterSave.order_blocks = afterSave.order_blocks.map((b) =>
      b.block_id === 101
        ? {
            ...b,
            override_text: "Новый заголовок",
            effective_text: "Новый заголовок",
            revision: 2,
            review_status: "CURRENT",
          }
        : b,
    );
    vi.mocked(patchPersonnelOrderEditorialBlock).mockResolvedValue(afterSave);

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-locale-ru")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));

    await waitFor(() => {
      expect(screen.getByText("О приёме на работу")).toBeInTheDocument();
    });

    const titleSection = screen.getByTestId("personnel-order-editorial-block-Заголовок");
    fireEvent.click(titleSection.querySelector('[data-testid="personnel-order-editorial-edit"]')!);

    const textarea = screen.getByTestId("personnel-order-editorial-textarea");
    fireEvent.change(textarea, { target: { value: "Новый заголовок" } });
    fireEvent.click(screen.getByTestId("personnel-order-editorial-save"));

    await waitFor(() => {
      expect(patchPersonnelOrderEditorialBlock).toHaveBeenCalledWith(42, 101, {
        override_text: "Новый заголовок",
        expected_revision: 1,
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Новый заголовок")).toBeInTheDocument();
      expect(screen.getByText("Edited")).toBeInTheDocument();
    });
  });

  it("auto-generates when only one locale is present", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [
        {
          block_id: 1,
          scope: "order",
          locale: "kk",
          block_type: "title",
          generated_text: "Жұмысқа қабылдау туралы",
          override_text: null,
          effective_text: "Жұмысқа қабылдау туралы",
          review_status: "CURRENT",
          editable: true,
          revision: 1,
        },
      ],
      items: [],
    });
    vi.mocked(generatePersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42);
    });
  });

  it("skips generate when user declines confirmation", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-generate")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-order-editorial-generate"));
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
  });

  it("saves override with expected revision and updates status to Edited", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    const afterSave = sampleState();
    afterSave.order_blocks = afterSave.order_blocks.map((b) =>
      b.block_type === "title"
        ? {
            ...b,
            override_text: "Жаңа тақырып",
            effective_text: "Жаңа тақырып",
            revision: 2,
            review_status: "CURRENT",
          }
        : b,
    );
    vi.mocked(patchPersonnelOrderEditorialBlock).mockResolvedValue(afterSave);

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });

    const titleSection = screen.getByTestId("personnel-order-editorial-block-Заголовок");
    fireEvent.click(titleSection.querySelector('[data-testid="personnel-order-editorial-edit"]')!);

    const textarea = screen.getByTestId("personnel-order-editorial-textarea");
    fireEvent.change(textarea, { target: { value: "Жаңа тақырып" } });
    fireEvent.click(screen.getByTestId("personnel-order-editorial-save"));

    await waitFor(() => {
      expect(patchPersonnelOrderEditorialBlock).toHaveBeenCalledWith(42, 1, {
        override_text: "Жаңа тақырып",
        expected_revision: 1,
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Жаңа тақырып")).toBeInTheDocument();
      expect(screen.getByText("Edited")).toBeInTheDocument();
    });
  });

  it("resets override to generated text", async () => {
    const withOverride = sampleState();
    withOverride.order_blocks = withOverride.order_blocks.map((b) =>
      b.block_type === "title"
        ? {
            ...b,
            override_text: "Қолмен",
            effective_text: "Қолмен",
            revision: 2,
          }
        : b,
    );
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(withOverride);
    vi.mocked(resetPersonnelOrderEditorialBlock).mockResolvedValue(sampleState());
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Қолмен")).toBeInTheDocument();
    });

    const titleSection = screen.getByTestId("personnel-order-editorial-block-Заголовок");
    fireEvent.click(titleSection.querySelector('[data-testid="personnel-order-editorial-reset"]')!);

    await waitFor(() => {
      expect(resetPersonnelOrderEditorialBlock).toHaveBeenCalledWith(42, 1);
    });
    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
  });

  it("hides edit actions when not DRAFT-editable", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(
      sampleState({ order_status: "READY_FOR_SIGNATURE", editable: false }),
    );

    render(<PersonnelOrderEditorialTextEditor orderId={42} items={items} editable={false} />);

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("personnel-order-editorial-edit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-editorial-generate")).not.toBeInTheDocument();
    expect(screen.getByText(/только для просмотра/i)).toBeInTheDocument();
  });
});
