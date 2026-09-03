import {
  buildHeaders,
  buildUrl,
  handleAuthFailureIfNeeded,
} from "@/lib/api";

const EXPORT_PATH = "/directory/personnel/control-list/export";
const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const SAFE_FALLBACK_FILENAME = "Контрольный_список.xlsx";

export type ControlListExportErrorKind =
  | "FORBIDDEN"
  | "CONFLICT"
  | "SERVER"
  | "INTEGRITY"
  | "WRITE";

export class ControlListExportUiError extends Error {
  constructor(public readonly kind: ControlListExportErrorKind) {
    super(kind);
    this.name = "ControlListExportUiError";
  }
}

type FileSystemWritable = {
  write(data: Blob): Promise<void>;
  close(): Promise<void>;
  abort?(): Promise<void>;
};

type SaveFileHandle = {
  createWritable(): Promise<FileSystemWritable>;
};

type SaveFilePickerOptions = {
  suggestedName: string;
  excludeAcceptAllOption: boolean;
  types: Array<{
    description: string;
    accept: Record<string, string[]>;
  }>;
};

type PickerWindow = Window & {
  showSaveFilePicker?: (options: SaveFilePickerOptions) => Promise<SaveFileHandle>;
};

type ExportDependencies = {
  browserWindow?: PickerWindow;
  browserDocument?: Document;
  fetchImpl?: typeof fetch;
  cryptoImpl?: Crypto;
  urlApi?: Pick<typeof URL, "createObjectURL" | "revokeObjectURL">;
  scheduleCleanup?: (callback: () => void) => void;
  now?: Date;
};

export type ControlListExportOutcome = "saved" | "downloaded" | "cancelled";

function almatyDateParts(now: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Almaty",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}`;
}

export function suggestedControlListFilename(now = new Date()): string {
  return `Контрольный_список_${almatyDateParts(now)}.xlsx`;
}

function safeXlsxFilename(candidate: string | null): string {
  const leaf = (candidate ?? "").split(/[\\/]/).pop() ?? "";
  const cleaned = leaf
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .replace(/[<>:"|?*]/g, "_")
    .trim()
    .replace(/[. ]+$/g, "")
    .slice(0, 180);
  if (!cleaned) return SAFE_FALLBACK_FILENAME;
  if (/\.xlsx$/i.test(cleaned)) return cleaned;
  const stem = cleaned.replace(/\.[^.]*$/, "").replace(/[. ]+$/g, "");
  return stem ? `${stem}.xlsx` : SAFE_FALLBACK_FILENAME;
}

export function filenameFromContentDisposition(value: string | null): string {
  if (!value || /[\r\n]/.test(value)) return SAFE_FALLBACK_FILENAME;

  const encoded = value.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)?.[1]?.trim();
  if (encoded) {
    try {
      return safeXlsxFilename(decodeURIComponent(encoded.replace(/^"|"$/g, "")));
    } catch {
      // A malformed RFC 5987 value must not suppress a valid ASCII fallback.
    }
  }

  const quoted = value.match(/filename\s*=\s*"([^"]*)"/i)?.[1];
  const plain = quoted ?? value.match(/filename\s*=\s*([^;]+)/i)?.[1]?.trim() ?? null;
  return safeXlsxFilename(plain);
}

function bytesToHex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function readBlob(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

async function verifyChecksum(blob: Blob, expected: string, cryptoImpl?: Crypto): Promise<void> {
  if (!/^[a-f0-9]{64}$/i.test(expected) || !cryptoImpl?.subtle) {
    throw new ControlListExportUiError("INTEGRITY");
  }
  let actual: string;
  try {
    actual = bytesToHex(await cryptoImpl.subtle.digest("SHA-256", await readBlob(blob)));
  } catch {
    throw new ControlListExportUiError("INTEGRITY");
  }
  if (actual !== expected.toLowerCase()) {
    throw new ControlListExportUiError("INTEGRITY");
  }
}

async function requestExport(deps: ExportDependencies): Promise<{ blob: Blob; filename: string }> {
  const fetchImpl = deps.fetchImpl ?? fetch;
  let response: Response;
  try {
    response = await fetchImpl(buildUrl(EXPORT_PATH), {
      method: "POST",
      headers: buildHeaders(),
      cache: "no-store",
    });
  } catch {
    throw new ControlListExportUiError("SERVER");
  }

  if (!response.ok) {
    handleAuthFailureIfNeeded(response.status);
    if (response.status === 403) throw new ControlListExportUiError("FORBIDDEN");
    if (response.status === 409) throw new ControlListExportUiError("CONFLICT");
    throw new ControlListExportUiError("SERVER");
  }

  const contentType = response.headers.get("Content-Type")?.split(";", 1)[0]?.trim();
  if (contentType !== XLSX_MIME) throw new ControlListExportUiError("SERVER");

  const blob = await response.blob();
  const expectedChecksum = response.headers.get("X-Content-SHA256")?.trim();
  if (expectedChecksum) {
    await verifyChecksum(blob, expectedChecksum, deps.cryptoImpl ?? globalThis.crypto);
  }
  return {
    blob,
    filename: filenameFromContentDisposition(response.headers.get("Content-Disposition")),
  };
}

function triggerBrowserDownload(
  blob: Blob,
  filename: string,
  browserDocument: Document,
  urlApi: Pick<typeof URL, "createObjectURL" | "revokeObjectURL">,
  scheduleCleanup: (callback: () => void) => void,
): void {
  const objectUrl = urlApi.createObjectURL(blob);
  const link = browserDocument.createElement("a");
  try {
    link.href = objectUrl;
    link.download = filename;
    browserDocument.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    // Revoking synchronously can race the browser's processing of link.click().
    scheduleCleanup(() => urlApi.revokeObjectURL(objectUrl));
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function exportControlListFile(
  deps: ExportDependencies = {},
): Promise<ControlListExportOutcome> {
  const browserWindow = deps.browserWindow ?? (window as PickerWindow);
  const picker = browserWindow.showSaveFilePicker;
  let handle: SaveFileHandle | null = null;

  if (picker) {
    try {
      handle = await picker.call(browserWindow, {
        suggestedName: suggestedControlListFilename(deps.now),
        excludeAcceptAllOption: true,
        types: [
          {
            description: "Книга Excel",
            accept: { [XLSX_MIME]: [".xlsx"] },
          },
        ],
      });
    } catch (error) {
      if (isAbortError(error)) return "cancelled";
      throw new ControlListExportUiError("WRITE");
    }
  }

  const download = await requestExport(deps);
  if (handle) {
    let writable: FileSystemWritable | null = null;
    try {
      writable = await handle.createWritable();
      await writable.write(download.blob);
      await writable.close();
    } catch {
      if (writable?.abort) await writable.abort().catch(() => undefined);
      throw new ControlListExportUiError("WRITE");
    }
    return "saved";
  }

  triggerBrowserDownload(
    download.blob,
    download.filename,
    deps.browserDocument ?? document,
    deps.urlApi ?? URL,
    deps.scheduleCleanup ?? ((callback) => globalThis.setTimeout(callback, 0)),
  );
  return "downloaded";
}
