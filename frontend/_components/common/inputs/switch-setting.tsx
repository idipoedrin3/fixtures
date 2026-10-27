"use client";

import type {ReactNode} from "react";
import {Label} from "@/components/ui/label";
import {Switch} from "@/components/ui/switch";
import {cn} from "@/lib/utils";
import {capitalizeEachWord} from "#/_api/helpers";
import InfoPopover from "../info-popover";

interface SwitchSettingProps {
  id: string;
  label: ReactNode;
  description?: ReactNode;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  labelClassName?: string;
  infoMarkdown?: string;
  infoPopoverSide?: "top" | "right" | "bottom" | "left";
  infoPopoverWidth?: "sm" | "md" | "lg";
}

export default function SwitchSetting({
  id,
  label,
  description,
  checked,
  onCheckedChange,
  disabled = false,
  className,
  labelClassName,
  infoMarkdown,
  infoPopoverSide = "top",
  infoPopoverWidth = "sm",
}: SwitchSettingProps) {
  const descriptionId = description ? `${id}-description` : undefined;

  return (
    <div className={cn("space-y-0.5", className)}>
      <div className="flex items-center gap-3">
        <Switch
          id={id}
          checked={checked}
          onCheckedChange={onCheckedChange}
          disabled={disabled}
          aria-describedby={descriptionId}
        />
        <div className="flex items-center gap-1">
          <Label
            htmlFor={id}
            className={cn(
              "cursor-pointer font-medium text-gray-700",
              disabled && "cursor-not-allowed opacity-70",
              labelClassName,
            )}
          >
            {typeof label === "string" ? capitalizeEachWord(label) : label}
          </Label>
          {infoMarkdown ? (
            <InfoPopover markdown={infoMarkdown} side={infoPopoverSide} width={infoPopoverWidth} />
          ) : null}
        </div>
      </div>

      {description ? (
        <p id={descriptionId} className="text-sm text-gray-500">
          {description}
        </p>
      ) : null}
    </div>
  );
}
