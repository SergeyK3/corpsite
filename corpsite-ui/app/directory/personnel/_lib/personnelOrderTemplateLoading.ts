export const TEMPLATE_REQUEST_TIMEOUT_MS = 15000;

/** A stalled read must become a retryable error instead of blocking the form. */
export function loadTemplateWithTimeout<T>(request: Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Превышено время ожидания ответа сервера. Повторите загрузку шаблона.")), TEMPLATE_REQUEST_TIMEOUT_MS);
    request.then(resolve, reject).finally(() => clearTimeout(timer));
  });
}
