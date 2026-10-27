"use client";

import {ReactNode, useEffect, useRef, useState} from "react";

import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {cn} from "@/lib/utils";

type TruncatedTextProps = {
  text?: string | number | null;
  maxLength?: number;
  emptyFallback?: ReactNode;
  popoverAlign?: "start" | "center" | "end";
  className?: string;
  textClassName?: string;
  dotsClassName?: string;
  contentClassName?: string;
  singleLine?: boolean;
  renderText?: (text: string) => ReactNode;
};

export function TruncatedText({
  text,
  maxLength = 60,
  emptyFallback = "-",
  popoverAlign = "start",
  className,
  textClassName,
  dotsClassName,
  contentClassName,
  singleLine = false,
  renderText,
}: TruncatedTextProps) {
  const value = text === null || text === undefined ? "" : String(text);
  const containerRef = useRef<HTMLSpanElement>(null);
  const measurementRef = useRef<HTMLSpanElement>(null);
  const [overflows, setOverflows] = useState(false);

  useEffect(() => {
    if (!singleLine || !value) return;
    const container = containerRef.current;
    const measurement = measurementRef.current;
    if (!container || !measurement) return;

    const measure = () => {
      setOverflows(measurement.scrollWidth > container.clientWidth);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    observer.observe(measurement);
    measure();
    return () => observer.disconnect();
  }, [singleLine, value]);

  if (!value) {
    return <>{emptyFallback}</>;
  }

  const shouldTruncate = value.length > maxLength || (singleLine && overflows);
  const visibleText = shouldTruncate ? value.slice(0, maxLength).trimEnd() : value;

  if (!shouldTruncate && !singleLine) {
    return (
      <span className={cn("break-words", textClassName)}>
        {renderText ? renderText(value) : value}
      </span>
    );
  }

  return (
    <span
      ref={containerRef}
      className={cn(
        "break-words",
        className,
        textClassName,
        singleLine && "relative inline-flex min-w-0 max-w-full items-baseline",
      )}
    >
      {singleLine && (
        <span
          ref={measurementRef}
          aria-hidden="true"
          className="pointer-events-none invisible absolute w-max whitespace-nowrap"
        >
          {value}
        </span>
      )}
      {renderText ? (
        renderText(visibleText)
      ) : singleLine ? (
        <span className="min-w-0 overflow-hidden whitespace-nowrap">{visibleText}</span>
      ) : (
        visibleText
      )}
      {shouldTruncate && (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className={cn(
                "ml-0.5 inline cursor-pointer rounded-sm px-0.5 font-medium text-foreground underline-offset-4 transition-colors hover:text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                dotsClassName,
                singleLine && "shrink-0",
              )}
              aria-label="Show full text"
            >
              ...
            </button>
          </PopoverTrigger>
          <PopoverContent
            align={popoverAlign}
            side="top"
            className={cn(
              "max-h-72 w-max min-w-48 max-w-[calc(100vw-2rem)] overflow-auto whitespace-pre-wrap break-words text-sm leading-relaxed sm:max-w-80",
              contentClassName,
            )}
          >
            {value}
          </PopoverContent>
        </Popover>
      )}
    </span>
  );
}

export default TruncatedText;
