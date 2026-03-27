import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { SiteHeader } from "@/components/site-header";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader />
        <div className="flex min-w-0 min-h-0 flex-1 flex-col">
          <div className="@container/main flex min-w-0 min-h-0 flex-1 flex-col gap-2">
            <div className="flex min-w-0 min-h-0 flex-1 flex-col gap-3 py-2 md:gap-4 md:py-3">{children}</div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
