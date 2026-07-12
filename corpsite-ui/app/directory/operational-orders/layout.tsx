import OperationalOrdersLayoutShell from "./_components/OperationalOrdersLayoutShell";

export const dynamic = "force-dynamic";

export default function OperationalOrdersLayout({ children }: { children: React.ReactNode }) {
  return <OperationalOrdersLayoutShell>{children}</OperationalOrdersLayoutShell>;
}
