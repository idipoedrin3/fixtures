"use client";

import * as React from "react";
import {Check} from "lucide-react";
import {Icon} from "@iconify/react";

import {cn} from "@/lib/utils";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";

export type SearchableSelectItem = {
  id: number | string;
  label: string;
  value?: string;
};

type SearchableSelectProps = {
  items: SearchableSelectItem[];
  selectedItems?: (number | string)[];
  placeholder?: string;
  emptyMessage?: string;
  searchPlaceholder?: string;
  onSelect: (itemId: number | string) => void;
  onRemove?: (itemId: number | string) => void;
  renderSelectedItems?: (
    selectedIds: (number | string)[],
    items: SearchableSelectItem[],
  ) => React.ReactNode;
  multiple?: boolean;
  disabled?: boolean;
  className?: string;
  triggerClassName?: string;
  popoverClassName?: string;
};

export function SearchableSelect({
  items,
  selectedItems = [],
  placeholder = "Select an item",
  emptyMessage = "No items found.",
  searchPlaceholder = "Search items...",
  onSelect,
  // onRemove,
  renderSelectedItems,
  multiple = false,
  disabled = false,
  className,
  triggerClassName,
  popoverClassName,
}: SearchableSelectProps) {
  const [open, setOpen] = React.useState(false);

  // For single select, find the selected item to display in the trigger
  const selectedItem =
    !multiple && selectedItems.length > 0
      ? items.find((item) => item.id === selectedItems[0])
      : null;

  const handleSelect = (itemId: number | string) => {
    onSelect(itemId);
    if (!multiple) {
      setOpen(false);
    }
  };

  return (
    <div className={cn("relative", className)}>
      {multiple && renderSelectedItems && (
        <div className="mb-2">{renderSelectedItems(selectedItems, items)}</div>
      )}

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger disabled={disabled} className="w-full disabled:cursor-not-allowed">
          <div
            aria-expanded={open}
            className={cn(
              "inline-flex h-[44px] w-full items-center justify-center gap-2 rounded-lg border border-input bg-background px-4 py-2 text-sm font-medium ring-offset-background transition-colors hover:bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              disabled && "!bg-accent !text-accent-foreground opacity-50",
              triggerClassName,
            )}
            role="combobox"
          >
            <span className="flex-grow truncate text-left">
              {!multiple && selectedItem ? selectedItem.label : placeholder}
            </span>
            <Icon icon="hugeicons:arrow-down-01" className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </div>
        </PopoverTrigger>
        <PopoverContent
          className={cn("w-full p-0", popoverClassName)}
          style={{
            minWidth: "var(--radix-popper-anchor-width)",
            maxWidth: "var(--radix-popper-anchor-width)",
            zIndex: 99999,
          }}
        >
          <Command>
            <CommandInput placeholder={searchPlaceholder} className="!border-none" />
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            <CommandGroup>
              <CommandList>
                {items.map((item) => (
                  <CommandItem
                    key={item.id}
                    value={item.value || item.label}
                    onSelect={() => handleSelect(item.id)}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        selectedItems.includes(item.id) ? "opacity-100" : "opacity-0",
                      )}
                    />
                    {item.label}
                  </CommandItem>
                ))}
              </CommandList>
            </CommandGroup>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
