"use client";

import { useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";

type NotificationType = "info" | "warning" | "error" | "success";

interface NotificationItem {
  id: number;
  title: string;
  message: string;
  type: NotificationType;
  read: boolean;
  created_at: string | null;
}

interface NotificationPageResponse {
  items: NotificationItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

const POLLING_INTERVAL_MS = 10000;

function showNativeBrowserNotification(notification: NotificationItem) {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return;
  }

  if (Notification.permission !== "granted") {
    return;
  }

  try {
    new Notification(notification.title, {
      body: notification.message,
      tag: `hunt-notification-${notification.id}`,
    });
  } catch {
    // noop
  }
}

export function NotificationsRealtimeListener() {
  const firstSyncRef = useRef(true);
  const knownUnreadIdsRef = useRef<Set<number>>(new Set());

  const pollUnreadNotifications = useCallback(async () => {
    try {
      const response = await api.get<NotificationPageResponse>("/api/v1/notifications/", {
        params: {
          status: "unread",
          page: 1,
          per_page: 20,
        },
      });

      const unreadItems = Array.isArray(response.data?.items) ? response.data.items : [];
      const currentIds = new Set(unreadItems.map((item) => item.id));

      if (firstSyncRef.current) {
        firstSyncRef.current = false;
        knownUnreadIdsRef.current = currentIds;
        return;
      }

      const freshItems = unreadItems.filter((item) => !knownUnreadIdsRef.current.has(item.id));
      knownUnreadIdsRef.current = currentIds;

      if (freshItems.length === 0) {
        return;
      }

      const sortedFreshItems = [...freshItems].sort((a, b) => a.id - b.id);
      sortedFreshItems.slice(0, 3).forEach((item) => {
        toast.info(item.title, {
          description: item.message,
          duration: 7000,
        });
        showNativeBrowserNotification(item);
      });

      if (sortedFreshItems.length > 3) {
        const remaining = sortedFreshItems.length - 3;
        toast.info(`Mais ${remaining} nova(s) notificação(ões) recebida(s).`);
      }

      window.dispatchEvent(new Event("hunt:notifications-updated"));
    } catch {
      // noop: keep polling without noisy errors
    }
  }, []);

  useEffect(() => {
    pollUnreadNotifications();
    const interval = window.setInterval(pollUnreadNotifications, POLLING_INTERVAL_MS);
    return () => {
      window.clearInterval(interval);
    };
  }, [pollUnreadNotifications]);

  return null;
}
