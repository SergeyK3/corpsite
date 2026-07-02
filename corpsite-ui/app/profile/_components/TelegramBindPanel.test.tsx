import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelegramBindPanel from "@/components/TelegramBindPanel";
import { apiCreateTelegramBindCode } from "@/lib/api";
import type { MeInfo } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiCreateTelegramBindCode: vi.fn(),
  };
});

const mockedCreate = vi.mocked(apiCreateTelegramBindCode);

const me: MeInfo = {
  user_id: 1,
  login: "qm_amb@corp.local",
  telegram_bound: false,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TelegramBindPanel", () => {
  it('calls API again and replaces activeCode when clicking "Создать новый код"', async () => {
    mockedCreate
      .mockResolvedValueOnce({ code: "AAAA-BBBB", expires_at: "2026-06-26T12:00:00Z" })
      .mockResolvedValueOnce({ code: "CCCC-DDDD", expires_at: "2026-06-26T12:30:00Z" });

    render(
      <TelegramBindPanel
        me={me}
        loading={false}
        onRefresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));

    await waitFor(() => {
      expect(screen.getByText("AAAA-BBBB")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Создать новый код" }));

    await waitFor(() => {
      expect(screen.getByText("CCCC-DDDD")).toBeInTheDocument();
    });

    expect(screen.queryByText("AAAA-BBBB")).not.toBeInTheDocument();
    expect(mockedCreate).toHaveBeenCalledTimes(2);
  });
});
