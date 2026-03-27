"use client";

import { startTransition, useCallback, type MouseEvent } from "react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { SidebarMenuButton, useSidebar } from "@/components/ui/sidebar";

function isCurrentRoute(pathname: string, url: string): boolean {
  if (url === "/") {
    return pathname === url;
  }

  return pathname === url || pathname.startsWith(`${url}/`);
}

export function SidebarNavLink({
  title,
  url,
  icon: Icon,
  tooltip,
}: {
  title: string;
  url: string;
  icon?: LucideIcon;
  tooltip?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { isMobile, setOpenMobile } = useSidebar();

  const prefetchRoute = useCallback(() => {
    router.prefetch(url);
  }, [router, url]);

  const handleClick = useCallback(
    (event: MouseEvent<HTMLAnchorElement>) => {
      prefetchRoute();

      const isModifiedClick =
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey;

      if (isModifiedClick || !isMobile) {
        return;
      }

      startTransition(() => {
        setOpenMobile(false);
      });
    },
    [isMobile, prefetchRoute, setOpenMobile],
  );

  return (
    <SidebarMenuButton tooltip={tooltip ?? title} asChild isActive={isCurrentRoute(pathname, url)}>
      <Link
        href={url}
        prefetch
        onMouseEnter={prefetchRoute}
        onFocus={prefetchRoute}
        onTouchStart={prefetchRoute}
        onClick={handleClick}
      >
        {Icon ? <Icon /> : null}
        <span>{title}</span>
      </Link>
    </SidebarMenuButton>
  );
}
