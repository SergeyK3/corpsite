import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import IntakePhotoUpload from "./IntakePhotoUpload";
import { emptyIntakeDraftPayload } from "../_lib/intakeApi.client";

vi.mock("../_lib/intakePhotoApi.client", () => ({
  buildIntakePhotoPublicUrl: (token: string, cacheBust?: string) =>
    `/mock/photo/${token}?v=${cacheBust ?? "0"}`,
  deleteIntakePhotoPublic: vi.fn(),
  deleteIntakePhotoOnBehalf: vi.fn(),
  fetchIntakePhotoOnBehalfBlob: vi.fn(),
  uploadIntakePhotoPublic: vi.fn(),
  uploadIntakePhotoOnBehalf: vi.fn(),
}));

vi.mock("./IntakePhotoCropEditor", () => ({
  default: ({
    onCancel,
    onReplace,
  }: {
    onCancel: () => void;
    onReplace: () => void;
  }) => (
    <div data-testid="intake-photo-crop-editor">
      <button type="button" onClick={onCancel}>
        cancel
      </button>
      <button type="button" onClick={onReplace}>
        replace
      </button>
    </div>
  ),
  readIntakePhotoSourceFile: vi.fn(async () => "blob:mock-source"),
}));

import * as photoApi from "../_lib/intakePhotoApi.client";
import { readIntakePhotoSourceFile } from "./IntakePhotoCropEditor";

describe("IntakePhotoUpload", () => {
  beforeEach(() => {
    if (typeof URL.revokeObjectURL !== "function") {
      URL.revokeObjectURL = vi.fn();
    }
    if (typeof URL.createObjectURL !== "function") {
      URL.createObjectURL = vi.fn(() => "blob:mock");
    }
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows empty slot and opens file picker", () => {
    render(
      <IntakePhotoUpload
        mode="public"
        intakeToken="abc-token"
        payload={emptyIntakeDraftPayload()}
        onPayloadChange={vi.fn()}
      />,
    );

    expect(screen.getByTestId("intake-photo-empty-slot")).toHaveTextContent("Место для фотографии 3×4");
    fireEvent.click(screen.getByTestId("intake-photo-upload-button"));
    expect(screen.getByTestId("intake-photo-file-input")).toBeInTheDocument();
  });

  it("enters crop editor after file selection", async () => {
    render(
      <IntakePhotoUpload
        mode="public"
        intakeToken="abc-token"
        payload={emptyIntakeDraftPayload()}
        onPayloadChange={vi.fn()}
      />,
    );

    const root = screen.getByTestId("intake-photo-upload");
    const input = within(root).getByTestId("intake-photo-file-input") as HTMLInputElement;
    const file = new File([new Uint8Array([1, 2, 3])], "photo.jpg", { type: "image/jpeg" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(readIntakePhotoSourceFile).toHaveBeenCalledWith(file);
      expect(screen.getByTestId("intake-photo-crop-editor")).toBeInTheDocument();
    });
  });

  it("shows saved preview when photo_file_id is present", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.photo_file_id = "abc123";

    render(
      <IntakePhotoUpload
        mode="public"
        intakeToken="abc-token"
        payload={payload}
        onPayloadChange={vi.fn()}
      />,
    );

    const preview = screen.getByTestId("intake-photo-preview").querySelector("img");
    expect(preview).toHaveAttribute("src", expect.stringContaining("/mock/photo/abc-token"));
    expect(screen.getByTestId("intake-photo-delete")).toBeInTheDocument();
    expect(photoApi.uploadIntakePhotoPublic).not.toHaveBeenCalled();
  });
});
