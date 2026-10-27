"use client";

import {Icon} from "@iconify/react";
import Image from "next/image";
import {hasPermission} from "#/_api/helpers";
import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {cn} from "@/lib/utils";

export interface ResponsiveAction {
  key: string;
  label: string;
  icon: string;
  iconImageSrc?: string;
  onSelect: () => void | Promise<void>;
  prominent?: boolean;
  disabled?: boolean;
  destructive?: boolean;
  visible?: boolean;
  permissionCode?: string | string[];
}

interface ResponsiveActionsProps {
  actions: ResponsiveAction[];
  className?: string;
  portalContainer?: HTMLDivElement | null;
  iconOnly?: boolean;
}

function canViewAction(action: ResponsiveAction) {
  if (action.visible === false) return false;
  if (!action.permissionCode) return true;

  const permissionCodes = Array.isArray(action.permissionCode)
    ? action.permissionCode
    : [action.permissionCode];

  return permissionCodes.every((code) => hasPermission(code));
}

export function ResponsiveActions({
  actions,
  className,
  portalContainer,
  iconOnly = false,
}: ResponsiveActionsProps) {
  const visibleActions = actions.filter(canViewAction);
  const prominentActions = visibleActions.filter((action) => action.prominent);
  const hasProminentActions = prominentActions.length > 0;
  const hasOverflowActions = visibleActions.some((action) => !action.prominent);

  if (visibleActions.length === 0) return null;

  return (
    <div className={cn("flex shrink-0 items-center gap-2", className)}>
      {prominentActions.map((action) => (
        <Button
          key={action.key}
          variant={action.destructive ? "destructive" : "outline"}
          className={cn(
            "hidden h-8 gap-2 rounded-lg px-3 md:inline-flex",
            !action.destructive && "border-[#BEBECF]",
          )}
          onClick={() => void action.onSelect()}
          disabled={action.disabled}
        >
          {action.iconImageSrc ? (
            <Image
              src={action.iconImageSrc}
              alt=""
              aria-hidden
              width={18}
              height={18}
              className="size-[18px] object-contain"
            />
          ) : (
            <Icon icon={action.icon} className="size-4" />
          )}
          {action.label}
        </Button>
      ))}

      <DropdownMenu modal={portalContainer ? false : true}>
        <DropdownMenuTrigger asChild>
          <Button
            variant={iconOnly ? "ghost" : "outline"}
            aria-label={hasProminentActions ? "More Actions" : "Actions"}
            className={cn(
              iconOnly
                ? "h-8 w-8 rounded-full p-0"
                : "h-8 w-8 rounded-lg border-[#BEBECF] px-0 md:w-auto md:px-3",
              !hasOverflowActions && "md:hidden",
            )}
          >
            <Icon
              icon="hugeicons:more-vertical-circle-01"
              className={iconOnly ? "size-4" : "size-4 md:hidden"}
            />
            {!iconOnly && (
              <span className="hidden md:inline">
                {hasProminentActions ? "More Actions" : "Actions"}
              </span>
            )}
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          align="end"
          className={cn("w-56", !hasOverflowActions && "md:hidden")}
          container={portalContainer}
          onCloseAutoFocus={portalContainer ? (event) => event.preventDefault() : undefined}
        >
          {visibleActions.map((action) => (
            <DropdownMenuItem
              key={action.key}
              disabled={action.disabled}
              className={cn(
                action.prominent && "md:hidden",
                action.destructive && "text-destructive focus:text-destructive",
              )}
              onClick={() => void action.onSelect()}
            >
              {action.iconImageSrc ? (
                <Image
                  src={action.iconImageSrc}
                  alt=""
                  aria-hidden
                  width={18}
                  height={18}
                  className="mr-2 size-[18px] object-contain"
                />
              ) : (
                <Icon icon={action.icon} className="mr-2 size-4" />
              )}
              {action.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
