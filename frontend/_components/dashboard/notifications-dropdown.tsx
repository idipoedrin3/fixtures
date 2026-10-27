"use client";

import {useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {Icon} from "@iconify/react";
import {formatDistanceToNow} from "date-fns";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {NOTIFICATIONS_API, INotification} from "#/_api/notifications.utils";
import {getNotificationPath} from "#/_lib/notifications-path-matcher";
import {Button} from "@/components/ui/button";
import {showErrorToast} from "#/_lib/utils";

export default function NotificationsDropdown() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<INotification[]>([]);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const res = await NOTIFICATIONS_API.fetch();

        setNotifications(res?.results ?? []);
      } catch (error) {
        showErrorToast({error, defaultMessage: "Failed to load notifications."});
      }
    })();
  }, [open]);

  useEffect(() => {
    const unread = notifications.filter((n) => !n.is_read).length;

    setUnreadCount(unread);
  }, [notifications]);

  const handleNotificationClick = async (notification: INotification) => {
    if (!notification.is_read) {
      try {
        await NOTIFICATIONS_API.markAsRead({notificationId: notification.id});
      } catch (err) {
        console.error("Failed to mark notification as read:", err);
      }
    }

    const path = getNotificationPath(notification);

    setOpen(false);
    if (path) router.push(path);
  };

  const getNotificationTimestamp = (notification: INotification): string => {
    return notification.created_at || new Date().toISOString();
  };

  // Get user display name - only show if we have proper display names (not IDs)
  const getUserDisplayName = (notification: INotification): string | null => {
    return notification?.user?.fullname ?? "-";
  };

  // Separate unread and read notifications, then sort each group by timestamp
  const unreadNotifications = notifications
    .filter((notification) => !notification.is_read)
    .sort(
      (a, b) =>
        new Date(getNotificationTimestamp(b)).getTime() -
        new Date(getNotificationTimestamp(a)).getTime(),
    );

  const readNotifications = notifications
    .filter((notification) => notification.is_read)
    .sort(
      (a, b) =>
        new Date(getNotificationTimestamp(b)).getTime() -
        new Date(getNotificationTimestamp(a)).getTime(),
    );

  const sortedNotifications = [...unreadNotifications, ...readNotifications];

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="p-2 relative">
          <Icon
            icon="hugeicons:notification-02"
            width={24}
            height={24}
            className="!w-6 !h-6 relative"
          />
          <span className="absolute top-1 right-2 w-3 h-3 bg-primary-700 rounded-full " />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        className="w-96 rounded-xl shadow-lg border border-gray-200 bg-white max-h-[32rem] overflow-hidden flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 bg-gray-50/50">
          <div className="flex items-center gap-2">
            <p className="font-semibold text-gray-900">Notifications</p>
            {unreadCount > 0 && (
              <span className="bg-primary text-white text-sm font-medium rounded-full px-2 py-0.5">
                {unreadCount} unread
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sortedNotifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
              <Icon
                icon="hugeicons:notification-off"
                width="48"
                height="48"
                className="text-gray-300 mb-3"
              />
              <p className="font-medium text-gray-500 mb-1">No notifications</p>
              <p className="text-sm text-gray-400">We'll notify you when something arrives</p>
            </div>
          ) : (
            <div className="py-1">
              {/* Unread Notifications Section */}
              {unreadNotifications.length > 0 && (
                <>
                  {unreadNotifications.map((notification) => {
                    const userDisplayName = getUserDisplayName(notification);
                    const hasModelName = notification.model_name;
                    const hasUser = !!userDisplayName;

                    return (
                      <DropdownMenuItem
                        key={notification.id}
                        className="flex flex-col items-start gap-1.5 py-3 px-4 text-sm cursor-pointer transition-colors  border-l-primary bg-primary/5 hover:bg-primary/10"
                        onClick={() => handleNotificationClick(notification)}
                      >
                        <div className="flex items-start justify-between w-full">
                          <p className="text-gray-800 flex-1 pr-2 font-semibold">
                            {notification.message}
                          </p>
                          <div className="w-2 h-2 bg-primary rounded-full mt-1.5 flex-shrink-0" />
                        </div>

                        {/* Meta information row */}
                        <div className="flex items-center justify-between w-full">
                          <div className="flex items-center gap-2">
                            {hasUser && (
                              <span className=" text-gray-600">By {userDisplayName}</span>
                            )}
                            {hasUser && hasModelName && <span className=" text-gray-400">•</span>}
                            {hasModelName && (
                              <span className=" text-gray-600 px-1.5 py-0.5 rounded">
                                {notification.model_name}
                              </span>
                            )}
                          </div>
                          <span className=" text-gray-600">
                            {formatDistanceToNow(new Date(getNotificationTimestamp(notification)), {
                              addSuffix: true,
                            })}
                          </span>
                        </div>
                      </DropdownMenuItem>
                    );
                  })}
                  {readNotifications.length > 0 && (
                    <div className="px-4 py-2 bg-gray-50/50 border-y text-center">
                      <p className=" text-black font-medium">Earlier</p>
                    </div>
                  )}
                </>
              )}

              {/* Read Notifications Section */}
              {readNotifications.map((notification) => {
                const userDisplayName = getUserDisplayName(notification);
                const hasModelName = notification.model_name;
                const hasUser = !!userDisplayName;

                return (
                  <DropdownMenuItem
                    key={notification.id}
                    className="flex flex-col items-start gap-1.5 py-3 px-4 text-sm cursor-pointer transition-colors  border-l-transparent hover:bg-gray-50/80"
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className="flex items-start justify-between w-full">
                      <p className="text-gray-600 flex-1 pr-2">{notification.message}</p>
                    </div>

                    {/* Meta information row */}
                    <div className="flex items-center justify-between w-full">
                      <div className="flex items-center gap-2">
                        {hasUser && <span className=" text-gray-500">By {userDisplayName}</span>}
                        {hasUser && hasModelName && <span className=" text-gray-400">•</span>}
                        {hasModelName && (
                          <span className=" text-gray-500  px-1.5 py-0.5 rounded">
                            {notification.model_name}
                          </span>
                        )}
                      </div>
                      <span className=" text-gray-500">
                        {formatDistanceToNow(new Date(getNotificationTimestamp(notification)), {
                          addSuffix: true,
                        })}
                      </span>
                    </div>
                  </DropdownMenuItem>
                );
              })}
            </div>
          )}
        </div>

        {sortedNotifications.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <div className="px-4 py-2 bg-gray-50/50 border-t">
              <p className=" text-gray-500 text-center">
                {sortedNotifications.length} notification
                {sortedNotifications.length !== 1 ? "s" : ""} total
              </p>
            </div>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
