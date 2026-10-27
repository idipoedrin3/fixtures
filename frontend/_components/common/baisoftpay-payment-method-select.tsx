"use client";

import {useEffect, useState} from "react";
import {Check} from "lucide-react";
import {Icon} from "@iconify/react";
import {Button} from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {cn} from "@/lib/utils";
import type {IBeneficiaryPaymentMethod} from "#/_types/types.utils";

const METHOD_GROUPS: {
  type: IBeneficiaryPaymentMethod["method_type"];
  label: string;
}[] = [
  {type: "mobile_money", label: "Mobile Money"},
  {type: "bank", label: "Bank Accounts"},
  {type: "digital_wallet", label: "Digital Wallets"},
];

function getMethodLabel(method: IBeneficiaryPaymentMethod) {
  return (
    method.operator_name ||
    method.operator_code?.replaceAll("_", " ") ||
    METHOD_GROUPS.find((group) => group.type === method.method_type)?.label ||
    "Payment destination"
  );
}

function DestinationDetails({method}: {method: IBeneficiaryPaymentMethod}) {
  return (
    <span className="flex min-w-0 flex-1 flex-col text-left">
      <span className="truncate text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {getMethodLabel(method)}
      </span>
      <span className="truncate font-mono text-sm text-foreground">
        {method.identifier}
        {method.currency ? ` · ${method.currency.code}` : " · Currency not set"}
      </span>
    </span>
  );
}

export function BaisoftPayPaymentMethodSelect({
  methods,
  value,
  disabled,
  loading,
  onSearch,
  onChange,
}: {
  methods: IBeneficiaryPaymentMethod[];
  value: IBeneficiaryPaymentMethod | null;
  disabled?: boolean;
  loading?: boolean;
  onSearch?: (search: string) => Promise<IBeneficiaryPaymentMethod[]>;
  onChange: (method: IBeneficiaryPaymentMethod) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<IBeneficiaryPaymentMethod[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const displayedMethods = search.trim() && onSearch ? searchResults : methods;

  useEffect(() => {
    if (!open || !search.trim() || !onSearch) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    let cancelled = false;
    const timeout = window.setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await onSearch(search.trim());
        if (!cancelled) setSearchResults(results);
      } finally {
        if (!cancelled) setIsSearching(false);
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [onSearch, open, search]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="h-12 w-full justify-between px-3 font-normal"
        >
          {value ? (
            <DestinationDetails method={value} />
          ) : (
            <span className="text-muted-foreground">
              {loading ? "Loading destinations..." : "Select payment destination"}
            </span>
          )}
          <Icon icon="hugeicons:arrow-down-01" className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>

      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-0">
        <Command shouldFilter={!onSearch} className="[&_[cmdk-input-wrapper]]:border-0">
          <CommandInput
            value={search}
            onValueChange={setSearch}
            placeholder="Search account, number, bank, or provider..."
            className="!rounded-none !border-0 !shadow-none !ring-0 focus:!ring-0 focus-visible:!ring-0"
          />
          <CommandList
            className="max-h-72 overflow-y-auto overscroll-contain"
            onWheel={(event) => event.stopPropagation()}
          >
            <CommandEmpty>
              {isSearching ? "Searching..." : "No matching payment destination found."}
            </CommandEmpty>

            {METHOD_GROUPS.map((group) => {
              const groupedMethods = displayedMethods.filter(
                (method) => method.method_type === group.type,
              );

              if (!groupedMethods.length) return null;

              return (
                <CommandGroup key={group.type} heading={group.label}>
                  {groupedMethods.map((method) => (
                    <CommandItem
                      key={method.base_uuid}
                      value={[group.label, getMethodLabel(method), method.identifier].join(" ")}
                      onSelect={() => {
                        onChange(method);
                        setOpen(false);
                      }}
                      className="py-2"
                    >
                      <Check
                        className={cn(
                          "size-4 shrink-0",
                          value?.base_uuid === method.base_uuid ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <DestinationDetails method={method} />
                    </CommandItem>
                  ))}
                </CommandGroup>
              );
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
