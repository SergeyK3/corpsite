"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import {
  buildPersonCardHrefFromLegacySearchParams,
  legacyCardQueryStringToSearchParams,
} from "@/lib/employeeCardNav";
import { getPprByEmployeeId } from "../_lib/pprQueryApi.client";
import { mapPprCardError } from "../_lib/pprCardPresentation";

type Props = {
  employeeId: string;
  /** Serialized legacy query string from the compatibility route (section, return_to, ...). */
  legacyQueryString?: string;
};

export default function EmployeePersonalCardRedirectClient({
  employeeId,
  legacyQueryString = "",
}: Props) {
  const router = useRouter();
  const [errorView, setErrorView] = React.useState<ReturnType<typeof mapPprCardError> | null>(null);
  const [retryKey, setRetryKey] = React.useState(0);
  const redirectStartedRef = React.useRef(false);

  React.useEffect(() => {
    redirectStartedRef.current = false;
  }, [employeeId, legacyQueryString, retryKey]);

  React.useEffect(() => {
    if (redirectStartedRef.current) return;

    const controller = new AbortController();
    setErrorView(null);

    void (async () => {
      try {
        const data = await getPprByEmployeeId(employeeId, { signal: controller.signal });
        const resolvedPersonId = data.identity.resolved_person_id;
        if (!Number.isFinite(resolvedPersonId) || resolvedPersonId <= 0) {
          setErrorView(mapPprCardError({ status: 404 }));
          return;
        }
        redirectStartedRef.current = true;
        const target = buildPersonCardHrefFromLegacySearchParams(
          resolvedPersonId,
          legacyCardQueryStringToSearchParams(legacyQueryString),
        );
        router.replace(target);
      } catch (error) {
        if (controller.signal.aborted) return;
        setErrorView(mapPprCardError(error));
      }
    })();

    return () => controller.abort();
  }, [employeeId, legacyQueryString, router, retryKey]);

  if (errorView) {
    return (
      <div className="px-4 py-8 sm:px-6">
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            errorView.kind === "access_denied" || errorView.kind === "not_found"
              ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100"
              : "border-red-200 bg-red-50 text-red-700 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200"
          }`}
          data-testid="employee-card-redirect-error"
        >
          <p>{errorView.message}</p>
          {errorView.retryable ? (
            <button
              type="button"
              className="mt-2 rounded border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700"
              onClick={() => setRetryKey((value) => value + 1)}
            >
              Повторить
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div
      className="px-4 py-16 text-center text-sm text-zinc-500"
      data-testid="employee-card-redirect-loading"
    >
      Переход к личной карточке…
    </div>
  );
}
