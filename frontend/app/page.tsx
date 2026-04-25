import { AppShell } from "@/components/app-shell";
import { DashboardScreen } from "@/components/dashboard-screen";

export default function HomePage() {
  return (
    <AppShell>
      <DashboardScreen />
    </AppShell>
  );
}
