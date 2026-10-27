"use client";

import {useEffect, useRef} from "react";
import {Icon} from "@iconify/react";

interface SystemUnitSelectorProps {
  units: any[];
  selectedUnitNames: string[];
  onSelectionChange: (selected: string[]) => void;
  isLoading?: boolean;
  error?: string | null;
  hasMore: boolean;
  isLoadingMore: boolean;
  onLoadMore: () => void;
  itemKey?: string;
  descriptionKey?: string;
}

export default function SystemUnitSelector({
  units,
  selectedUnitNames,
  onSelectionChange,
  isLoading = false,
  error = null,
  hasMore,
  isLoadingMore,
  onLoadMore,
  itemKey = "unit_name",
  descriptionKey = "description",
}: SystemUnitSelectorProps) {
  const toggleUnit = (unitName: string) => {
    onSelectionChange(
      selectedUnitNames.includes(unitName)
        ? selectedUnitNames.filter((name) => name !== unitName)
        : [...selectedUnitNames, unitName],
    );
  };

  const loaderRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hasMore || isLoadingMore || !loaderRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => entries[0].isIntersecting && onLoadMore(),
      {threshold: 0.1},
    );
    observer.observe(loaderRef.current);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, onLoadMore]);

  if (isLoading) {
    return (
      <div className="py-10 flex flex-col items-center justify-center text-muted-foreground">
        <Icon icon="eos-icons:loading" className="h-6 w-6 animate-spin mb-2" />
        <p className="text-base">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-10 text-center text-base text-destructive">
        <Icon icon="solar:warning-triangle-bold" className="mx-auto mb-2 h-6 w-6" />
        {error}
      </div>
    );
  }

  if (units.length === 0) {
    return <div className="py-10 text-center text-base text-muted-foreground">No items found</div>;
  }

  return (
    <div className="max-h-[420px] overflow-y-auto space-y-1.5 pr-1 -mr-1 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
      {units.map((unit) => {
        const isSelected = selectedUnitNames.includes(unit[itemKey]);
        return (
          <label
            key={unit[itemKey]}
            className={`
              flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 transition-colors
              ${
                isSelected
                  ? "border-primary/30 bg-primary/5"
                  : "border-border hover:border-input hover:bg-muted/50"
              }
            `}
          >
            <div className="relative mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => toggleUnit(unit[itemKey])}
                className="absolute inset-0 opacity-0"
              />
              <div
                className={`
                  h-5 w-5 rounded border flex items-center justify-center transition-all
                  ${
                    isSelected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background group-hover:border-primary/60"
                  }
                `}
              >
                {isSelected && <Icon icon="lucide:check" className="h-4 w-4" />}
              </div>
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span
                  className={`text-base font-medium ${isSelected ? "text-primary" : "text-foreground"} truncate`}
                >
                  {unit[itemKey]}
                </span>
                {unit.unit_abbreviation && (
                  <span className="text-base text-muted-foreground font-mono">
                    {unit.unit_abbreviation}
                  </span>
                )}
              </div>
              {unit[descriptionKey] && (
                <p className="mt-1 text-base leading-relaxed text-muted-foreground line-clamp-2">
                  {unit[descriptionKey]}
                </p>
              )}
            </div>
          </label>
        );
      })}

      {hasMore && (
        <div ref={loaderRef} className="py-4 text-center text-base text-muted-foreground">
          {isLoadingMore ? (
            <div className="flex items-center justify-center gap-2">
              <Icon icon="eos-icons:loading" className="h-4 w-4 animate-spin" />
              Loading more...
            </div>
          ) : (
            "Scroll for more"
          )}
        </div>
      )}
    </div>
  );
}
