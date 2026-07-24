export const INTAKE_PHOTO_OUTPUT_WIDTH = 600;
export const INTAKE_PHOTO_OUTPUT_HEIGHT = 800;
export const INTAKE_PHOTO_OUTPUT_MAX_BYTES = 500 * 1024;
export const INTAKE_PHOTO_SOURCE_MAX_BYTES = 10 * 1024 * 1024;
export const INTAKE_PHOTO_ASPECT = 3 / 4;

export type IntakePhotoCropState = {
  zoom: number;
  rotation: number;
  position: { x: number; y: number };
};

export type IntakePhotoFaceWarningCode =
  | "NO_FACE"
  | "MULTIPLE_FACES"
  | "OFF_CENTER"
  | "CHECK_UNAVAILABLE";

export type IntakePhotoFaceAnalysis = {
  level: "ok" | "warning";
  code: IntakePhotoFaceWarningCode | null;
  message: string | null;
  faceCount: number | null;
};

export function createDefaultIntakePhotoCropState(): IntakePhotoCropState {
  return { zoom: 1, rotation: 0, position: { x: 0, y: 0 } };
}
