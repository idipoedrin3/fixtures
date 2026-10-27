"use client";

import {useId, useState} from "react";
import {Icon} from "@iconify/react";
import {cn} from "@/lib/utils";

type Props = {
  title: string;
  description: string;
  collapsedDescription?: string;
  headerLeading?: React.ReactNode;
  headerAction?: React.ReactNode;
  className?: string;
  children?: string | React.ReactNode;
  gridClassName?: string;
  hideHeader?: boolean;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
};

export default function FormSection({
  title,
  description,
  collapsedDescription,
  headerLeading,
  headerAction,
  className,
  children,
  gridClassName,
  hideHeader = false,
  collapsible = false,
  defaultCollapsed = true,
}: Props) {
  const contentId = useId();
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const canCollapse = collapsible && !hideHeader;
  const isCollapsed = canCollapse && collapsed;

  return (
    <section
      className={cn(
        "transition-[padding] duration-300 ease-in-out motion-reduce:transition-none",
        children ? "pb-6" : "",
        isCollapsed && "py-2",
        className,
      )}
    >
      {!hideHeader && (
        <>
          <div className="flex items-start justify-between gap-4 pt-2">
            <div className="flex items-center gap-3">
              {headerLeading ? <div className="shrink-0">{headerLeading}</div> : null}
              <h2 className="font-semibold text-xl">
                {canCollapse ? (
                  <button
                    type="button"
                    aria-expanded={!isCollapsed}
                    aria-controls={contentId}
                    onClick={() => setCollapsed((value) => !value)}
                    className="flex items-center gap-2 rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Icon
                      icon="hugeicons:arrow-right-01"
                      aria-hidden="true"
                      className={cn(
                        "h-5 w-5 shrink-0 -translate-x-1.5 transition-transform duration-300 ease-in-out motion-reduce:transition-none",
                        !isCollapsed && "rotate-90",
                      )}
                    />
                    {title}
                  </button>
                ) : (
                  title
                )}
              </h2>
            </div>
            {headerAction ? <div className="shrink-0 pt-1">{headerAction}</div> : null}
          </div>
          <div className="mt-1 text-sm md:text-base opacity-60">
            {isCollapsed ? (collapsedDescription ?? description) : description}
          </div>
        </>
      )}
      {children ? (
        <div
          id={contentId}
          inert={isCollapsed}
          aria-hidden={isCollapsed}
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-in-out motion-reduce:transition-none",
            isCollapsed
              ? "grid-rows-[0fr] opacity-0"
              : "grid-rows-[1fr] opacity-100",
          )}
        >
          <div className="min-h-0 overflow-hidden">
            <div
              className={cn(
                "pt-3 grid gap-x-4 gap-y-4 lg:grid-cols-2 [&>div]:space-y-2",
                gridClassName,
              )}
            >
              {children}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
