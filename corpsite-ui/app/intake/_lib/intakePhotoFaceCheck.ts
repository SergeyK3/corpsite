import type { IntakePhotoFaceAnalysis } from "./intakePhotoTypes";

type FaceDetectorLike = {
  detect(source: CanvasImageSource): Promise<Array<{ boundingBox: DOMRectReadOnly }>>;
};

declare global {
  interface Window {
    FaceDetector?: new (options?: { fastMode?: boolean; maxDetectedFaces?: number }) => FaceDetectorLike;
  }
}

function isFaceCentered(box: DOMRectReadOnly, width: number, height: number): boolean {
  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  const horizontalOk = Math.abs(centerX - width / 2) <= width * 0.22;
  const verticalOk = centerY >= height * 0.18 && centerY <= height * 0.62;
  return horizontalOk && verticalOk;
}

export async function analyzeIntakePhotoFace(
  source: CanvasImageSource,
  size: { width: number; height: number },
): Promise<IntakePhotoFaceAnalysis> {
  if (typeof window === "undefined" || typeof window.FaceDetector !== "function") {
    return {
      level: "warning",
      code: "CHECK_UNAVAILABLE",
      message: "Автоматическая проверка лица недоступна в этом браузере. Кадровик сможет принять фото вручную.",
      faceCount: null,
    };
  }

  const detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 5 });
  const faces = await detector.detect(source);
  if (faces.length === 0) {
    return {
      level: "warning",
      code: "NO_FACE",
      message: "Лицо не обнаружено. Проверьте кадрирование или загрузите другое фото.",
      faceCount: 0,
    };
  }
  if (faces.length > 1) {
    return {
      level: "warning",
      code: "MULTIPLE_FACES",
      message: "Обнаружено несколько лиц. Допустимо одно лицо в кадре.",
      faceCount: faces.length,
    };
  }
  if (!isFaceCentered(faces[0].boundingBox, size.width, size.height)) {
    return {
      level: "warning",
      code: "OFF_CENTER",
      message: "Лицо смещено от центра кадра. Рекомендуется выровнять фото.",
      faceCount: 1,
    };
  }
  return { level: "ok", code: null, message: null, faceCount: 1 };
}
