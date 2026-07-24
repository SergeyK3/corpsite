import { resolveApiUrl } from "@/lib/apiBase";
import type { PersonnelOrderPdfAuthContext } from "@/app/directory/personnel/_lib/personnelOrderPdfAuth";
import type { IntakeDraftPayload, IntakeSessionResponse } from "./intakeApi.client";
import { buildIntakePdfFilename } from "./intakePdfFilename";
import { buildIntakePdfCalculatedSummaries } from "./intakePdfSummaries";
import { buildIntakePdfViewModel, type IntakePdfViewModel } from "./intakePdfViewModel";

export class IntakePdfDataError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "IntakePdfDataError";
    this.status = status;
    this.code = code;
  }
}

type IntakeDraftOut = {
  application_id: number;
  payload: IntakeDraftPayload;
};

function authHeaders(auth: PersonnelOrderPdfAuthContext): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (auth.authorizationHeader) headers.Authorization = auth.authorizationHeader;
  if (auth.devUserId) headers["X-User-Id"] = auth.devUserId;
  return headers;
}

async function fetchJson<T>(
  pathName: string,
  init: { headers?: Record<string, string>; fallback: string },
): Promise<T> {
  const res = await fetch(resolveApiUrl(pathName, { serverSide: true }), {
    method: "GET",
    headers: init.headers,
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new IntakePdfDataError(401, "UNAUTHORIZED", "Требуется авторизация.");
    }
    if (res.status === 403) {
      throw new IntakePdfDataError(403, "FORBIDDEN", "Недостаточно прав для доступа к анкете.");
    }
    if (res.status === 404) {
      throw new IntakePdfDataError(404, "NOT_FOUND", "Анкета не найдена.");
    }
    throw new IntakePdfDataError(res.status, "UPSTREAM_ERROR", init.fallback);
  }
  return res.json() as Promise<T>;
}

async function fetchBinary(
  pathName: string,
  init: { headers?: Record<string, string>; fallback: string },
): Promise<Buffer | null> {
  const res = await fetch(resolveApiUrl(pathName, { serverSide: true }), {
    method: "GET",
    headers: init.headers,
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    if (res.status === 401) {
      throw new IntakePdfDataError(401, "UNAUTHORIZED", "Требуется авторизация.");
    }
    if (res.status === 403) {
      throw new IntakePdfDataError(403, "FORBIDDEN", "Недостаточно прав для доступа к анкете.");
    }
    throw new IntakePdfDataError(res.status, "UPSTREAM_ERROR", init.fallback);
  }
  const arrayBuffer = await res.arrayBuffer();
  return Buffer.from(arrayBuffer);
}

/** Photo failures must never abort personal-card PDF generation. */
async function fetchPhotoBinarySoft(
  pathName: string,
  init: { headers?: Record<string, string> } = {},
): Promise<Buffer | null> {
  try {
    const res = await fetch(resolveApiUrl(pathName, { serverSide: true }), {
      method: "GET",
      headers: init.headers,
      cache: "no-store",
    });
    if (!res.ok) return null;
    const arrayBuffer = await res.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    if (!buffer.length || buffer[0] !== 0xff || buffer[1] !== 0xd8) return null;
    return buffer;
  } catch {
    return null;
  }
}

function buildIntakePhotoDataUrl(content: Buffer | null): string | null {
  if (!content || content.length === 0) return null;
  return `data:image/jpeg;base64,${content.toString("base64")}`;
}

async function loadIntakePhotoDataUrlByToken(token: string): Promise<string | null> {
  const content = await fetchPhotoBinarySoft(`/intake/${encodeURIComponent(token)}/photo`);
  return buildIntakePhotoDataUrl(content);
}

async function loadIntakePhotoDataUrlByApplicationId(
  applicationId: number,
  auth: PersonnelOrderPdfAuthContext,
): Promise<string | null> {
  const content = await fetchPhotoBinarySoft(
    `/directory/personnel-applications/${applicationId}/intake/photo`,
    { headers: authHeaders(auth) },
  );
  return buildIntakePhotoDataUrl(content);
}

export type IntakePdfLoadedModel = {
  model: IntakePdfViewModel;
  filename: string;
};

export async function loadIntakePdfModelByToken(token: string): Promise<IntakePdfLoadedModel> {
  const trimmed = String(token ?? "").trim();
  if (!trimmed) {
    throw new IntakePdfDataError(422, "INVALID_TOKEN", "Некорректная ссылка анкеты.");
  }

  const session = await fetchJson<IntakeSessionResponse>(`/intake/${encodeURIComponent(trimmed)}`, {
    fallback: "Не удалось загрузить анкету.",
  });

  const generatedAt = new Date();
  const summaries = await buildIntakePdfCalculatedSummaries(session.payload, generatedAt);
  const photoDataUrl = await loadIntakePhotoDataUrlByToken(trimmed);
  const model = buildIntakePdfViewModel({
    applicationId: session.application_id,
    payload: session.payload,
    generatedAt,
    summaries,
    photoDataUrl,
  });
  return {
    model,
    filename: buildIntakePdfFilename(model.applicationId, model.fullName),
  };
}

export async function loadIntakePdfModelByApplicationId(
  applicationId: number,
  auth: PersonnelOrderPdfAuthContext,
): Promise<IntakePdfLoadedModel> {
  if (!Number.isFinite(applicationId) || applicationId <= 0 || !Number.isInteger(applicationId)) {
    throw new IntakePdfDataError(422, "INVALID_APPLICATION_ID", "Некорректный идентификатор обращения.");
  }

  const draft = await fetchJson<IntakeDraftOut>(
    `/directory/personnel-applications/${applicationId}/intake/draft`,
    {
      headers: authHeaders(auth),
      fallback: "Не удалось загрузить черновик анкеты.",
    },
  );

  const generatedAt = new Date();
  const summaries = await buildIntakePdfCalculatedSummaries(draft.payload, generatedAt);
  const photoDataUrl = await loadIntakePhotoDataUrlByApplicationId(applicationId, auth);
  const model = buildIntakePdfViewModel({
    applicationId: draft.application_id ?? applicationId,
    payload: draft.payload,
    generatedAt,
    summaries,
    photoDataUrl,
  });
  return {
    model,
    filename: buildIntakePdfFilename(model.applicationId, model.fullName),
  };
}
