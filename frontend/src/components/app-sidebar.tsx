"use client";

import {
  BriefcaseIcon,
  BotIcon,
  DatabaseIcon,
  FileTextIcon,
  LayoutDashboardIcon,
} from "lucide-react";
import Link from "next/link";

import { NavMain } from "@/components/nav-main";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const data = {
  navMain: [
    {
      title: "Dashboard",
      url: "/",
      icon: LayoutDashboardIcon,
    },
    {
      title: "Vagas",
      url: "/vagas",
      icon: BriefcaseIcon,
    },
    {
      title: "Currículo",
      url: "/resume",
      icon: FileTextIcon,
    },
  ],
  navSecondary: [
    {
      title: "Fontes",
      url: "/sources",
      icon: DatabaseIcon,
    },
    {
      title: "Scrapings",
      url: "/scrapings",
      icon: BotIcon,
    },
  ],
};

function BrandMark() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0 text-sidebar-foreground"
    >
      <path d="M12 4 4 8.5 12 13l8-4.5L12 4Z" />
      <path d="M4 15.5 12 20l8-4.5" />
      <path d="M4 8.5v7" />
      <path d="M20 8.5v7" />
    </svg>
  );
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props} variant="inset">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild className="[&>svg]:size-5 [&>svg]:-ml-0.5">
              <Link href="/">
                <BrandMark />
                <div className="flex flex-1 items-center justify-between text-left text-sm leading-tight">
                  <span className="truncate font-semibold text-base">Jobs</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} label="Empregos" className="py-1.5" />
        <NavMain items={data.navSecondary} label="Operação" className="py-1.5" />
      </SidebarContent>
    </Sidebar>
  );
}
