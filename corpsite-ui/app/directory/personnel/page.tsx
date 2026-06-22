// FILE: corpsite-ui/app/directory/personnel/page.tsx
import PersonnelRootRedirectClient from "./_components/PersonnelRootRedirectClient";

export const dynamic = "force-dynamic";

/** Role-aware legacy bookmark: HR → journal, managers → staff, else → tasks via resolver. */
export default function PersonnelPage() {
  return <PersonnelRootRedirectClient />;
}
