import {
  INTAKE_PHOTO_OUTPUT_HEIGHT,
  INTAKE_PHOTO_OUTPUT_MAX_BYTES,
  INTAKE_PHOTO_OUTPUT_WIDTH,
  type IntakePhotoCropState,
} from "./intakePhotoTypes";

function createCanvas(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

function canvasToBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("Не удалось сформировать JPEG."));
          return;
        }
        resolve(blob);
      },
      "image/jpeg",
      quality,
    );
  });
}

function getRadianAngle(degree: number): number {
  return (degree * Math.PI) / 180;
}

function rotateSize(width: number, height: number, rotation: number) {
  const rot = getRadianAngle(rotation);
  return {
    width: Math.abs(Math.cos(rot) * width) + Math.abs(Math.sin(rot) * height),
    height: Math.abs(Math.sin(rot) * width) + Math.abs(Math.cos(rot) * height),
  };
}

export async function exportIntakePhotoJpeg(
  image: HTMLImageElement,
  crop: IntakePhotoCropState,
  viewportWidth: number,
  viewportHeight: number,
): Promise<Blob> {
  const naturalWidth = image.naturalWidth;
  const naturalHeight = image.naturalHeight;
  if (!naturalWidth || !naturalHeight) {
    throw new Error("Не удалось прочитать изображение.");
  }

  const rotRad = getRadianAngle(crop.rotation);
  const { width: bBoxWidth, height: bBoxHeight } = rotateSize(naturalWidth, naturalHeight, crop.rotation);
  const canvas = createCanvas(bBoxWidth, bBoxHeight);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas недоступен.");

  ctx.translate(bBoxWidth / 2, bBoxHeight / 2);
  ctx.rotate(rotRad);
  ctx.drawImage(image, -naturalWidth / 2, -naturalHeight / 2);

  const scale = Math.max(viewportWidth / naturalWidth, viewportHeight / naturalHeight) * crop.zoom;
  const cropWidth = viewportWidth / scale;
  const cropHeight = viewportHeight / scale;
  const cropX = bBoxWidth / 2 - cropWidth / 2 - crop.position.x / scale;
  const cropY = bBoxHeight / 2 - cropHeight / 2 - crop.position.y / scale;

  const output = createCanvas(INTAKE_PHOTO_OUTPUT_WIDTH, INTAKE_PHOTO_OUTPUT_HEIGHT);
  const outputCtx = output.getContext("2d");
  if (!outputCtx) throw new Error("Canvas недоступен.");
  outputCtx.drawImage(
    canvas,
    cropX,
    cropY,
    cropWidth,
    cropHeight,
    0,
    0,
    INTAKE_PHOTO_OUTPUT_WIDTH,
    INTAKE_PHOTO_OUTPUT_HEIGHT,
  );

  let quality = 0.92;
  let blob = await canvasToBlob(output, quality);
  for (let attempt = 0; attempt < 8 && blob.size > INTAKE_PHOTO_OUTPUT_MAX_BYTES; attempt += 1) {
    quality = Math.max(0.45, quality - 0.08);
    blob = await canvasToBlob(output, quality);
  }
  if (blob.size > INTAKE_PHOTO_OUTPUT_MAX_BYTES) {
    throw new Error("Не удалось сжать фото до 500 КБ.");
  }
  return blob;
}
