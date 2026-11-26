"use client";

import * as React from "react";

const WIDTH = 600;
const HEIGHT = 800;
const MIN_CROP_WIDTH = 360;
const MIN_CROP_HEIGHT = 480;
const MAX_CROP_SCALE = Math.min(WIDTH / MIN_CROP_WIDTH, HEIGHT / MIN_CROP_HEIGHT);
const MAX_BYTES = 500 * 1024;

type Offset = { x: number; y: number };

function clampOffset(image: HTMLImageElement, zoom: number, offset: Offset): Offset {
  const scale = Math.max(WIDTH / image.naturalWidth, HEIGHT / image.naturalHeight) * zoom;
  const limitX = Math.max(0, (image.naturalWidth * scale - WIDTH) / 2);
  const limitY = Math.max(0, (image.naturalHeight * scale - HEIGHT) / 2);
  return {
    x: Math.max(-limitX, Math.min(limitX, offset.x)),
    y: Math.max(-limitY, Math.min(limitY, offset.y)),
  };
}

function encodeJpeg(canvas: HTMLCanvasElement, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}

export default function PhotoCropEditor({ source, onReady, onError }: {
  source: File;
  onReady: (file: File | null, preview: string | null) => void;
  onError: (message: string) => void;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const dragRef = React.useRef<{ x: number; y: number } | null>(null);
  const [image, setImage] = React.useState<HTMLImageElement | null>(null);
  const [zoom, setZoom] = React.useState(1);
  const [offset, setOffset] = React.useState<Offset>({ x: 0, y: 0 });

  React.useEffect(() => {
    if (source.type !== "image/jpeg") {
      onError("Выберите файл JPEG.");
      return;
    }
    if (source.size > 10 * 1024 * 1024) {
      onError("Исходный JPEG превышает 10 МБ.");
      return;
    }
    let active = true;
    const url = URL.createObjectURL(source);
    const loaded = new Image();
    loaded.onload = () => {
      if (!active) return;
      if (loaded.naturalWidth * loaded.naturalHeight > 20_000_000) {
        onError("Исходное фото слишком большое для обработки.");
        return;
      }
      if (Math.max(WIDTH / loaded.naturalWidth, HEIGHT / loaded.naturalHeight) > MAX_CROP_SCALE) {
        onError(`Исходное фото: ${loaded.naturalWidth} × ${loaded.naturalHeight} пикселей. Минимальный кадр: ${MIN_CROP_WIDTH} × ${MIN_CROP_HEIGHT} пикселей.`);
        return;
      }
      setZoom(1);
      setOffset({ x: 0, y: 0 });
      setImage(loaded);
    };
    loaded.onerror = () => { if (active) onError("Не удалось прочитать файл как JPEG."); };
    loaded.src = url;
    return () => { active = false; URL.revokeObjectURL(url); };
  }, [source, onError]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!image || !canvas) return;
    const context = canvas.getContext("2d");
    if (!context) { onError("Не удалось подготовить предпросмотр фото."); return; }
    const scale = Math.max(WIDTH / image.naturalWidth, HEIGHT / image.naturalHeight) * zoom;
    const width = image.naturalWidth * scale;
    const height = image.naturalHeight * scale;
    const bounded = clampOffset(image, zoom, offset);
    context.fillStyle = "#fff";
    context.fillRect(0, 0, WIDTH, HEIGHT);
    context.drawImage(image, (WIDTH - width) / 2 + bounded.x, (HEIGHT - height) / 2 + bounded.y, width, height);

    let active = true;
    const timer = window.setTimeout(() => {
      void (async () => {
        for (const quality of [0.9, 0.82, 0.74, 0.66, 0.58]) {
          const blob = await encodeJpeg(canvas, quality);
          if (!active) return;
          if (!blob) { onError("Не удалось создать итоговый JPEG."); return; }
          if (blob.size <= MAX_BYTES) {
            onReady(new File([blob], "photo-600x800.jpg", { type: "image/jpeg" }), URL.createObjectURL(blob));
            return;
          }
        }
        onError("Итоговое фото превышает 500 КБ. Уменьшите масштаб или выберите другое изображение.");
      })();
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [image, zoom, offset, onReady, onError]);

  function changeOffset(deltaX: number, deltaY: number) {
    if (!image) return;
    onReady(null, null);
    setOffset((previous) => clampOffset(image, zoom, { x: previous.x + deltaX, y: previous.y + deltaY }));
  }

  const coverScale = image ? Math.max(WIDTH / image.naturalWidth, HEIGHT / image.naturalHeight) : 1;
  const maxZoom = Math.max(1, MAX_CROP_SCALE / coverScale);
  const canZoom = maxZoom > 1 + 1e-6;
  const cropWidth = WIDTH / (coverScale * zoom);
  const cropHeight = HEIGHT / (coverScale * zoom);
  const mayLoseSharpness = cropWidth < 480 - 1e-6 || cropHeight < 640 - 1e-6;

  return image && <div className="mt-4 space-y-3">
    <p className="text-sm">Перетащите фото для выбора кадра 3:4. Масштаб задаётся ползунком.</p>
    <canvas
      ref={canvasRef} width={WIDTH} height={HEIGHT} tabIndex={0}
      role="img" aria-label="Область кадрирования фото; перетаскивайте мышью или используйте стрелки"
      className="h-auto w-52 max-w-full cursor-grab rounded border border-zinc-300 touch-none active:cursor-grabbing"
      onPointerDown={(event) => { dragRef.current = { x: event.clientX, y: event.clientY }; event.currentTarget.setPointerCapture(event.pointerId); }}
      onPointerMove={(event) => {
        if (!dragRef.current) return;
        const rect = event.currentTarget.getBoundingClientRect();
        changeOffset((event.clientX - dragRef.current.x) * WIDTH / rect.width, (event.clientY - dragRef.current.y) * HEIGHT / rect.height);
        dragRef.current = { x: event.clientX, y: event.clientY };
      }}
      onPointerUp={() => { dragRef.current = null; }}
      onPointerCancel={() => { dragRef.current = null; }}
      onKeyDown={(event) => {
        const moves: Record<string, Offset> = { ArrowLeft: { x: -20, y: 0 }, ArrowRight: { x: 20, y: 0 }, ArrowUp: { x: 0, y: -20 }, ArrowDown: { x: 0, y: 20 } };
        if (moves[event.key]) { event.preventDefault(); changeOffset(moves[event.key].x, moves[event.key].y); }
      }}
    />
    {canZoom ? <label className="block text-sm">Масштаб: {zoom.toFixed(2)}×
      <input type="range" min={1} max={maxZoom} step={0.01} value={zoom}
        onChange={(event) => {
          const next = Number(event.target.value);
          onReady(null, null);
          setZoom(next);
          setOffset((previous) => image ? clampOffset(image, next, previous) : previous);
        }} className="mt-1 block w-52" />
    </label> : <p className="text-sm text-zinc-600">Приближение недоступно: исходное фото уже даёт минимальный кадр 360 × 480 пикселей.</p>}
    {mayLoseSharpness && <p className="text-sm text-amber-700">При увеличении фото может потерять чёткость</p>}
  </div>;
}
