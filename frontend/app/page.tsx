import { AppShell } from "@/components/app-shell";
import { OperatorConsole } from "@/components/operator-console";

export default function HomePage() {
  return (
    <AppShell activeKey="engagements">
      <OperatorConsole />
    </AppShell>
  );
}
