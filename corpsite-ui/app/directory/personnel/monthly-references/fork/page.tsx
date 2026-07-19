import { Suspense } from "react";

import MrdForkWizardPageClient from "../../_components/MrdForkWizardPageClient";

function ForkWizardFallback() {
  return (
    <div className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500">
      Загрузка…
    </div>
  );
}

export default function MrdForkWizardPage() {
  return (
    <div className="px-4 py-3">
      <Suspense fallback={<ForkWizardFallback />}>
        <MrdForkWizardPageClient />
      </Suspense>
    </div>
  );
}
