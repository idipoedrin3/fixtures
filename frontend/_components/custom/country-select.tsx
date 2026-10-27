"use client";

import type React from "react";

import {useEffect, useRef, useState} from "react";
import {Icon} from "@iconify/react";

import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {ICountry} from "#/_types/types.utils";

export default function CountrySelect({
  countries,
  selectedCountry,
  onCountryChange,
  onSearchChange,
  onLoadMore,
  hasMore = false,
  isLoading = false,
  disabled = false,
  compact = false,
  compactValue = "phone_code",
}: {
  countries: ICountry[];
  selectedCountry: ICountry | null;
  onCountryChange: (country: ICountry | null) => void;
  onSearchChange: (search: string) => void;
  onLoadMore: () => void;
  hasMore?: boolean;
  isLoading?: boolean;
  disabled?: boolean;
  compact?: boolean;
  compactValue?: "phone_code" | "iso2";
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, []);

  const handleSearchChange = (value: string) => {
    setSearchTerm(value);

    if (searchTimer.current) clearTimeout(searchTimer.current);

    searchTimer.current = setTimeout(() => {
      onSearchChange(value.trim());
    }, 300);
  };

  const handleScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const element = event.currentTarget;
    const nearBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 40;

    if (nearBottom && hasMore && !isLoading) onLoadMore();
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          disabled={disabled}
          type="button"
          variant="outline"
          className={`flex min-w-0 items-center justify-between rounded-[14px] border ${
            compact ? "w-auto px-2" : "w-full"
          }`}
        >
          <span className="flex items-center gap-2 truncate">
            {selectedCountry ? (
              <>
                <span className="text-lg">{selectedCountry.flag}</span>
                {compact ? selectedCountry[compactValue] : selectedCountry.name}
              </>
            ) : compact ? (
              <span className="text-gray-400">{compactValue === "iso2" ? "Country" : "+Code"}</span>
            ) : (
              "Select Country"
            )}
          </span>
          <span className="ml-auto">
            <Icon icon="hugeicons:arrow-down-01" className="size-5" />
          </span>
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        className={`max-h-80 overflow-hidden p-0 ${
          compact ? "w-32" : "w-[var(--radix-popover-trigger-width)]"
        }`}
      >
        <div className="p-2 border-b border-gray-100">
          <Input
            placeholder="Search Countries..."
            disabled={disabled}
            value={searchTerm}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="text-sm border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>
        <div className="max-h-60 overflow-y-auto" onScroll={handleScroll}>
          {countries.length > 0 ? (
            countries.map((country) => (
              <button
                key={country.iso2}
                type="button"
                onClick={() => {
                  onCountryChange(country);
                  setIsOpen(false);
                  setSearchTerm("");
                }}
                className={`w-full px-3 py-2 text-left hover:bg-gray-50 flex items-center gap-2 ${
                  selectedCountry?.iso2 === country.iso2 ? "bg-blue-50 text-blue-600" : ""
                }`}
              >
                <span className="text-lg">{country.flag}</span>
                {!compact ? <span className="font-medium text-sm">{country.name}</span> : <></>}

                <span className="ml-auto text-xs text-gray-400">{country.iso2}</span>
              </button>
            ))
          ) : !isLoading ? (
            <div className="px-3 py-4 text-center text-sm text-gray-500">
              No countries found matching "{searchTerm}"
            </div>
          ) : null}
          {isLoading && (
            <div className="px-3 py-2 text-center text-xs text-gray-500">Loading countries...</div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
