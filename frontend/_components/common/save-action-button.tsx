"use client";

import {Icon} from "@iconify/react";
import {useEffect, useState} from "react";

import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {cn} from "@/lib/utils";

export type SaveAction = "save-and-new" | "save-and-close" | "save-and-view";

type SaveActionButtonProps = {
  primaryLabel?: string;
  pendingLabel?: string;
  isPending?: boolean;
  disabled?: boolean;
  className?: string;
  onAction: (action: SaveAction) => void;
  onSaveDraft?: () => void;
  isSavingDraft?: boolean;
};

const actions: Array<{
  value: SaveAction;
  label: string;
  icon: string;
  shortcut: {
    key: string;
    shift?: boolean;
  };
}> = [
  {
    value: "save-and-new",
    label: "Save And New",
    icon: "hugeicons:add-01",
    shortcut: {key: "S", shift: true},
  },
  {
    value: "save-and-close",
    label: "Save And Close",
    icon: "hugeicons:cancel-01",
    shortcut: {key: "X", shift: true},
  },
  {
    value: "save-and-view",
    label: "Save And View Details",
    icon: "hugeicons:view",
    shortcut: {key: "S"},
  },
];

export function SaveActionButton({
  primaryLabel = "Save",
  pendingLabel = "Saving...",
  isPending = false,
  disabled = false,
  className,
  onAction,
  onSaveDraft,
  isSavingDraft = false,
}: SaveActionButtonProps) {
  const isDisabled = disabled || isPending;
  const [modifierLabel, setModifierLabel] = useState("Ctrl");

  useEffect(() => {
    if (/Mac|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
      setModifierLabel("⌘");
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isDisabled || (!event.ctrlKey && !event.metaKey) || event.altKey) {
        return;
      }

      const key = event.key.toLowerCase();
      let action: SaveAction | null = null;

      if (!event.shiftKey && key === "d" && onSaveDraft && !isSavingDraft) {
        event.preventDefault();
        onSaveDraft();
        return;
      } else if (event.shiftKey && key === "s") {
        action = "save-and-new";
      } else if (event.shiftKey && key === "x") {
        action = "save-and-close";
      } else if (!event.shiftKey && key === "s") {
        action = "save-and-view";
      }

      if (action) {
        event.preventDefault();
        onAction(action);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDisabled, isSavingDraft, onAction, onSaveDraft]);

  return (
    <div className={cn("inline-flex", className)}>
      <Button
        type="submit"
        disabled={isDisabled}
        className="h-12 flex-1 rounded-l-full rounded-r-none px-6"
      >
        {isPending ? pendingLabel : primaryLabel}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            disabled={isDisabled}
            className="h-12 rounded-l-none rounded-r-full border-l border-primary-foreground/30 px-3"
            aria-label={`${primaryLabel} options`}
          >
            <Icon icon="hugeicons:arrow-down-01" className="size-4" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="min-w-56">
          {onSaveDraft && (
            <>
              <DropdownMenuItem
                className="group cursor-pointer gap-3 px-3 py-2.5 text-sm"
                disabled={isSavingDraft}
                onSelect={onSaveDraft}
              >
                <Icon icon="hugeicons:file-add" className="size-4" />
                {isSavingDraft ? "Saving Draft..." : "Save Draft"}
                <DropdownMenuShortcut className="opacity-0 transition-opacity group-hover:opacity-60">
                  {modifierLabel}+D
                </DropdownMenuShortcut>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}

          {actions.map((action) => {
            return (
              <DropdownMenuItem
                key={action.value}
                className="group cursor-pointer gap-3 px-3 py-2.5 text-sm"
                onSelect={() => onAction(action.value)}
              >
                <Icon icon={action.icon} className="size-4" />
                {action.label}
                <DropdownMenuShortcut className="opacity-0 transition-opacity group-hover:opacity-60">
                  {modifierLabel}+{action.shortcut.shift ? "Shift+" : ""}
                  {action.shortcut.key}
                </DropdownMenuShortcut>
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
