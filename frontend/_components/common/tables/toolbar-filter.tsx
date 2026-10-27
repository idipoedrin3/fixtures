"use client";

import {Icon} from "@iconify/react";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export interface ToolbarFilterOption {
  label: string;
  value: string;
  description?: string;
}

interface ToolbarFilterProps {
  label: string;
  options: ToolbarFilterOption[];
  value: string[];
  onChange: (value: string[]) => void;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  loading?: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void;
  emptyMessage?: string;
  onOpen?: () => void;
}

export function ToolbarFilter({
  label,
  options,
  value,
  onChange,
  searchValue = "",
  onSearchChange,
  searchPlaceholder = "Search...",
  loading = false,
  hasMore = false,
  onLoadMore,
  emptyMessage = "No options found",
  onOpen,
}: ToolbarFilterProps) {
  const selectedOption =
    value.length === 1 ? options.find((option) => option.value === value[0]) : undefined;

  const triggerLabel =
    value.length === 0
      ? label
      : value.length === 1
        ? `${label}: ${selectedOption?.label ?? "1 selected"}`
        : `${label}: ${value.length} selected`;

  const toggleOption = (optionValue: string) => {
    onChange(
      value.includes(optionValue)
        ? value.filter((selectedValue) => selectedValue !== optionValue)
        : [...value, optionValue],
    );
  };

  return (
    <DropdownMenu
      onOpenChange={(open) => {
        if (open) onOpen?.();
      }}
    >
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="h-10 max-w-56 shrink-0 gap-2 rounded-xl">
          <span className="truncate">{triggerLabel}</span>
          {value.length > 0 && <span className="size-2 shrink-0 rounded-full bg-primary" />}
          <Icon icon="hugeicons:arrow-down-01" className="size-4 shrink-0 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-72 overflow-hidden p-0">
        {onSearchChange && (
          <div
            className="border-b px-1.5 py-2"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <div className="relative">
              <Icon
                icon="hugeicons:search-01"
                className="absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                value={searchValue}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder={searchPlaceholder}
                className="h-8 rounded-none !border-0 bg-transparent pl-7 shadow-none focus-visible:!border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              />
            </div>
          </div>
        )}

        <div
          className="max-h-72 overflow-y-auto p-1.5"
          onScroll={(event) => {
            const element = event.currentTarget;
            const nearBottom =
              element.scrollHeight - element.scrollTop - element.clientHeight <= 24;

            if (nearBottom && hasMore && !loading) {
              onLoadMore?.();
            }
          }}
        >
          {value.length > 0 && (
            <DropdownMenuItem onSelect={() => onChange([])}>
              <Icon icon="hugeicons:undo" />
              Reset {label}
            </DropdownMenuItem>
          )}

          {options.map((option) => (
            <DropdownMenuCheckboxItem
              key={option.value}
              checked={value.includes(option.value)}
              onCheckedChange={() => toggleOption(option.value)}
              onSelect={(event) => event.preventDefault()}
              className="gap-3 rounded-lg px-2 py-2 [&>span:first-child]:hidden"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{option.label}</span>
                {option.description && (
                  <span className="block truncate text-xs text-muted-foreground">
                    {option.description}
                  </span>
                )}
              </span>

              {value.includes(option.value) && (
                <Icon icon="hugeicons:tick-02" className="size-4 shrink-0 text-primary" />
              )}
            </DropdownMenuCheckboxItem>
          ))}

          {loading && (
            <div className="flex items-center justify-center gap-2 px-3 py-6 text-sm text-muted-foreground">
              <Icon icon="hugeicons:loading-03" className="size-4 animate-spin" />
              Loading...
            </div>
          )}

          {!loading && options.length === 0 && (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </div>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
