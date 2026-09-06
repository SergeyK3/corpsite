import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PprPersonPhoto from "./PprPersonPhoto";

const getPprPersonPhotoMock = vi.fn();
vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprPersonPhoto: (...args: unknown[]) => getPprPersonPhotoMock(...args),
}));

describe("PprPersonPhoto", () => {
  beforeEach(() => {
    getPprPersonPhotoMock.mockReset();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:protected-person-photo"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
    Reflect.deleteProperty(URL, "createObjectURL");
    Reflect.deleteProperty(URL, "revokeObjectURL");
    vi.restoreAllMocks();
  });

  it("renders the protected photo returned for an exact Person ID", async () => {
    getPprPersonPhotoMock.mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));

    render(<PprPersonPhoto personId={501} fullName="Иванов Иван" />);

    const image = await screen.findByRole("img", { name: "Фото сотрудника Иванов Иван" });
    expect(image).toHaveAttribute("src", "blob:protected-person-photo");
    expect(getPprPersonPhotoMock).toHaveBeenCalledWith(
      501,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows a textual placeholder when the photo is absent or unavailable", async () => {
    getPprPersonPhotoMock.mockRejectedValue({ status: 404 });

    render(<PprPersonPhoto personId={501} fullName="Иванов Иван" />);

    await waitFor(() => {
      expect(screen.getByText("Фото отсутствует")).toBeInTheDocument();
    });
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("keeps a fixed, shrink-safe photo frame for narrow layouts", () => {
    render(<PprPersonPhoto personId={null} fullName="Иванов Иван" />);

    const frame = screen.getByTestId("ppr-person-photo");
    expect(frame).toHaveClass("w-24", "shrink-0", "sm:h-40");
    expect(screen.getByText("Фото отсутствует")).toBeInTheDocument();
  });
});
