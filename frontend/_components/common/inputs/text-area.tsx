"use client";

import * as React from "react";
import {Icon} from "@iconify/react";
import {cn} from "@/lib/utils";

type TextareaProps = React.ComponentProps<"textarea"> & {
  description?: string;
  label?: string;
  error?: string;
  maxLength?: number;
  showCount?: boolean;
  countPosition?: "top" | "bottom";
  variant?: "default" | "ghost" | "filled" | "line";
  resize?: "none" | "vertical" | "horizontal" | "both";
  autoResize?: boolean;
  minRows?: number;
  maxRows?: number;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  loading?: boolean;
  showOptional?: boolean;
  labelClassName?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
};

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      className,
      description,
      label,
      error,
      maxLength,
      showCount = false,
      countPosition = "bottom",
      variant = "default",
      resize = "vertical",
      autoResize = false,
      minRows = 3,
      maxRows,
      startIcon,
      endIcon,
      loading = false,
      showOptional = false,
      value,
      defaultValue,
      onChange,
      id,
      disabled,
      required,
      labelClassName,
      collapsible = false,
      defaultExpanded = true,
      ...props
    },
    ref,
  ) => {
    const internalRef = React.useRef<HTMLTextAreaElement>(null);
    const resolvedRef = (ref as React.RefObject<HTMLTextAreaElement>) ?? internalRef;
    const generatedId = React.useId();
    const textareaId = id ?? generatedId;

    const [internalValue, setInternalValue] = React.useState(defaultValue?.toString() ?? "");
    const isControlled = value !== undefined;
    const currentValue = isControlled ? (value?.toString() ?? "") : internalValue;
    const isLine = variant === "line";
    const canCollapse = collapsible && !required && Boolean(label);
    const [expanded, setExpanded] = React.useState(defaultExpanded || Boolean(currentValue));
    const isExpanded = expanded || Boolean(error);

    React.useEffect(() => {
      if (currentValue) setExpanded(true);
    }, [currentValue]);

    const resizeTextarea = React.useCallback(() => {
      const el = resolvedRef.current;
      if (!el) return;
      if (isLine) {
        el.style.height = "0px";
        el.style.height = `${el.scrollHeight}px`;
        el.style.overflowY = "hidden";
      } else if (autoResize) {
        el.style.height = "auto";
        const lineHeight = parseInt(getComputedStyle(el).lineHeight) || 20;
        const paddingY =
          parseInt(getComputedStyle(el).paddingTop) + parseInt(getComputedStyle(el).paddingBottom);
        const minH = minRows * lineHeight + paddingY;
        const maxH = maxRows ? maxRows * lineHeight + paddingY : Infinity;
        el.style.height = `${Math.min(Math.max(el.scrollHeight, minH), maxH)}px`;
        el.style.overflowY = maxRows && el.scrollHeight > maxH ? "auto" : "hidden";
      }
    }, [isLine, autoResize, minRows, maxRows, resolvedRef]);

    React.useEffect(() => {
      resizeTextarea();
    }, [currentValue, resizeTextarea, isExpanded]);
    React.useEffect(() => {
      resizeTextarea();
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (!isControlled) setInternalValue(e.target.value);
      onChange?.(e);
    };

    const count = currentValue.length;
    const percentage = maxLength ? count / maxLength : 0;
    const isAtLimit = percentage >= 1;
    const hasError = Boolean(error);

    const getCountColor = () => {
      if (!maxLength) return "text-muted-foreground";
      if (percentage >= 1) return "text-destructive";
      if (percentage >= 0.9) return "text-red-500";
      if (percentage >= 0.75) return "text-yellow-500";
      return "text-muted-foreground";
    };

    const variantClasses = {
      default:
        "border border-input bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background",
      ghost:
        "border border-transparent bg-transparent hover:bg-muted/40 focus-visible:bg-background focus-visible:border-input focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background",
      filled:
        "border border-transparent bg-muted focus-visible:bg-background focus-visible:border-input focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background",
      line: "!border-0 !border-b !border-t-0 !border-x-0 border-input bg-transparent !rounded-none !shadow-none !ring-0 !ring-offset-0 focus-visible:outline-none focus-visible:!border-b-2 focus-visible:!border-primary transition-[border-color,border-width]",
    };

    const resizeClasses = {
      none: "resize-none",
      vertical: "resize-y",
      horizontal: "resize-x",
      both: "resize",
    };

    const lineErrorClasses = isLine
      ? (isAtLimit || hasError) && "!border-b-destructive focus-visible:!border-b-destructive"
      : (isAtLimit || hasError) && "border-destructive focus-visible:ring-destructive";

    const counter = showCount ? (
      <div className="text-xs md:text-sm flex justify-between items-center gap-2">
        <span className="text-muted-foreground">{description}</span>
        <span className={cn("tabular-nums shrink-0", getCountColor())}>
          {maxLength ? `${count}/${maxLength}` : `${count} characters`}
        </span>
      </div>
    ) : description ? (
      <p className="text-xs md:text-sm text-muted-foreground">{description}</p>
    ) : null;

    const textareaEl = (
      <textarea
        id={textareaId}
        ref={resolvedRef}
        value={currentValue}
        maxLength={maxLength}
        onChange={handleChange}
        disabled={disabled || loading}
        rows={isLine ? 1 : props.rows}
        required={required}
        aria-invalid={hasError || undefined}
        aria-describedby={
          [
            description || showCount ? `${textareaId}-description` : null,
            hasError ? `${textareaId}-error` : null,
          ]
            .filter(Boolean)
            .join(" ") || undefined
        }
        style={
          isLine
            ? {overflowY: "hidden"}
            : autoResize
              ? {minHeight: `${minRows * 20 + 16}px`, overflowY: "hidden"}
              : undefined
        }
        className={cn(
          "flex w-full text-base placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-base transition-colors",
          isLine ? "py-0 px-0 rounded-none leading-normal resize-none" : "rounded-md px-3 py-2",
          !autoResize && !isLine && "min-h-[80px]",
          variantClasses[variant],
          !isLine && resizeClasses[autoResize ? "none" : resize],
          lineErrorClasses,
          startIcon && (isLine ? "pl-6" : "pl-9"),
          endIcon && (isLine ? "pr-6" : "pr-9"),
          loading && "animate-pulse",
          className,
        )}
        {...props}
      />
    );

    const labelEl = (
      <label
        htmlFor={textareaId}
        className={cn(
          "text-lg font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 flex items-center gap-1.5",
          isLine && "shrink-0 whitespace-nowrap",
          labelClassName,
          canCollapse && "sr-only",
        )}
      >
        {label}
        {required && (
          <span className="text-destructive" aria-hidden="true">
            *
          </span>
        )}
        {showOptional && !required && (
          <span className="text-xs font-normal text-muted-foreground">(optional)</span>
        )}
      </label>
    );

    const iconsAndLoading = (
      <>
        {startIcon && (
          <div
            className={cn(
              "absolute top-0 text-muted-foreground pointer-events-none",
              isLine ? "left-0" : "left-3 top-2.5",
            )}
          >
            {startIcon}
          </div>
        )}
        {endIcon && (
          <div
            className={cn(
              "absolute text-muted-foreground pointer-events-none",
              isLine ? "right-0 top-0" : "right-3 top-2.5",
            )}
          >
            {endIcon}
          </div>
        )}
        {loading && (
          <div className={cn("absolute", isLine ? "right-0 top-0" : "right-3 top-2.5")}>
            <svg
              className="animate-spin h-4 w-4 text-muted-foreground"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          </div>
        )}
      </>
    );

    const content = (
      <div className="w-full grid gap-1.5">
        {isLine ? (
          <div className="flex items-baseline gap-3 w-full">
            {label && labelEl}
            <div className="relative flex-1 min-w-0">
              {iconsAndLoading}
              {textareaEl}
            </div>
          </div>
        ) : (
          <>
            {label && labelEl}
            {countPosition === "top" && counter}
            <div className="relative">
              {iconsAndLoading}
              {textareaEl}
            </div>
          </>
        )}

        {countPosition === "bottom" && (
          <div id={`${textareaId}-description`} className="grid gap-1">
            {counter}
          </div>
        )}

        {hasError && (
          <p
            id={`${textareaId}-error`}
            className="text-xs md:text-sm text-destructive flex items-center gap-1"
            role="alert"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-3.5 w-3.5 shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            {error}
          </p>
        )}
      </div>
    );
    if (!canCollapse) return content;

    return (
      <div className="w-full space-y-1">
        <button
          type="button"
          aria-expanded={isExpanded}
          aria-controls={`${textareaId}-panel`}
          disabled={disabled || loading}
          onClick={() => setExpanded((visible) => !visible)}
          className={cn(
            "flex items-center gap-2 rounded text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
            labelClassName,
          )}
        >
          <Icon
            icon="hugeicons:arrow-right-01"
            aria-hidden="true"
            className={cn(
              "size-5 shrink-0 -translate-x-1.5 transition-transform duration-300 ease-in-out motion-reduce:transition-none",
              isExpanded && "rotate-90",
            )}
          />
          {label}
          {showOptional && <span className="font-normal text-muted-foreground">(optional)</span>}
        </button>
        <div
          id={`${textareaId}-panel`}
          inert={!isExpanded}
          aria-hidden={!isExpanded}
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-in-out motion-reduce:transition-none",
            isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="min-h-0 overflow-hidden">{content}</div>
        </div>
      </div>
    );
  },
);

Textarea.displayName = "Textarea";

export {Textarea};
export type {TextareaProps};
