import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PprPersonPhoto from "./PprPersonPhoto";

const getPprPersonPhotoMock = vi.fn();
const uploadPprPersonPhotoMock = vi.fn();
vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprPersonPhoto: (...args: unknown[]) => getPprPersonPhotoMock(...args),
  uploadPprPersonPhoto: (...args: unknown[]) => uploadPprPersonPhotoMock(...args),
}));

describe("PprPersonPhoto", () => {
  beforeEach(() => {
    getPprPersonPhotoMock.mockReset();
    uploadPprPersonPhotoMock.mockReset();
    let photoUrlCounter = 0;
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => `blob:protected-person-photo-${++photoUrlCounter}`),
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
    expect(image).toHaveAttribute("src", "blob:protected-person-photo-1");
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

  it("uploads the selected JPEG to the exact Person card and refreshes the image", async () => {
    getPprPersonPhotoMock
      .mockResolvedValueOnce(new Blob(["old-jpeg"], { type: "image/jpeg" }))
      .mockResolvedValueOnce(new Blob(["new-jpeg"], { type: "image/jpeg" }));
    uploadPprPersonPhotoMock.mockResolvedValue({ person_id: 501, person_photo_id: 23, status: "committed" });

    render(<PprPersonPhoto personId={501} fullName="Иванов Иван" canManagePhoto />);

    await screen.findByRole("img", { name: "Фото сотрудника Иванов Иван" });
    fireEvent.change(screen.getByLabelText("Выбрать фотографию"), {
      target: { files: [new File(["jpeg"], "portrait.jpg", { type: "image/jpeg" })] },
    });

    await waitFor(() => {
      expect(uploadPprPersonPhotoMock).toHaveBeenCalledWith(501, expect.any(File));
      expect(getPprPersonPhotoMock).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText("Фотография успешно заменена.")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute("src", "blob:protected-person-photo-2");
  });

  it("does not expose upload controls without photo-management permission", async () => {
    getPprPersonPhotoMock.mockRejectedValue({ status: 404 });

    render(<PprPersonPhoto personId={501} fullName="Иванов Иван" canManagePhoto={false} />);

    await screen.findByText("Фото отсутствует");
    expect(screen.queryByRole("button", { name: /Загрузить фото|Заменить фото/ })).not.toBeInTheDocument();
  });

  it("rejects an unsupported file with a textual message before upload", async () => {
    getPprPersonPhotoMock.mockRejectedValue({ status: 404 });

    render(<PprPersonPhoto personId={501} fullName="Иванов Иван" canManagePhoto />);
    await screen.findByText("Фото отсутствует");
    fireEvent.change(screen.getByLabelText("Выбрать фотографию"), {
      target: { files: [new File(["png"], "portrait.png", { type: "image/png" })] },
    });

    expect(await screen.findByText("Можно загрузить только JPEG-файл.")).toBeInTheDocument();
    expect(uploadPprPersonPhotoMock).not.toHaveBeenCalled();
  });
});
