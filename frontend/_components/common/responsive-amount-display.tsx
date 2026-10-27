"use client";

import {useEffect, useRef, useState} from "react";
import {formatCurrency} from "#/_lib/utils";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {cn} from "@/lib/utils";

type ResponsiveAmountDisplayProps = {
  value: number | string;
  currency?: string;
  className?: string;
};

export function ResponsiveAmountDisplay({
  value,
  currency,
  className,
}: ResponsiveAmountDisplayProps) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const fullValueRef = useRef<HTMLSpanElement>(null);
  const [showFull, setShowFull] = useState(false);
  const amount = Number(value);
  const validAmount = Number.isFinite(amount) ? amount : 0;
  const fullAmount = formatCurrency(validAmount);
  const compactAmount = new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(validAmount);

  const fullDisplay = [currency, fullAmount].filter(Boolean).join(" ");
  const compactDisplay = [currency, compactAmount].filter(Boolean).join(" ");

  useEffect(() => {
    const container = containerRef.current;
    const fullValue = fullValueRef.current;
    const availableSpace = container?.parentElement;

    if (!container || !fullValue || !availableSpace) return;

    const updateDisplay = () => {
      setShowFull(fullValue.scrollWidth <= availableSpace.clientWidth);
    };

    updateDisplay();

    const observer = new ResizeObserver(updateDisplay);
    observer.observe(availableSpace);

    return () => observer.disconnect();
  }, [fullDisplay]);

  return (
    <span
      ref={containerRef}
      className={cn("relative inline-flex max-w-full tabular-nums", className)}
    >
      <span
        ref={fullValueRef}
        aria-hidden
        className="pointer-events-none invisible absolute whitespace-nowrap"
      >
        {fullDisplay}
      </span>

      {showFull ? (
        <span className="whitespace-nowrap">{fullDisplay}</span>
      ) : (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="cursor-pointer whitespace-nowrap"
              aria-label={`Show full amount: ${fullDisplay}`}
            >
              {compactDisplay}
            </button>
          </PopoverTrigger>

          <PopoverContent
            align="end"
            side="top"
            className="w-auto max-w-[calc(100vw-2rem)] whitespace-nowrap px-3 py-2 font-medium tabular-nums"
          >
            {fullDisplay}
          </PopoverContent>
        </Popover>
      )}
    </span>
  );
}
