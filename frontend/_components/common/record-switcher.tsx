"use client";

import {useEffect, useRef, useState, useCallback} from "react";
import {Icon} from "@iconify/react";
import {PopoverAnchor} from "@radix-ui/react-popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {IPaginatedResponse} from "#/_types/api.types";
import {cn} from "@/lib/utils";
import {TruncatedText} from "./truncated-text";

export interface RecordSwitcherProps<T extends Record<string, any>> {
  currentId: string;
  currentLabel?: string;
  hideCurrentLabel?: boolean;
  truncateLabelAt?: number;
  labelClassName?: string;
  currentDescription?: string;
  fetchFirstPage: (query?: Record<string, any>) => Promise<IPaginatedResponse<T>>;
  fetchFromUrl: (args: {url: string}) => Promise<IPaginatedResponse<T>>;
  idKey?: keyof T;
  labelKey?: keyof T;
  labelKeyFn?: (item: T) => string;
  descriptionKey?: keyof T;
  descriptionKeyFn?: (item: T) => string;
  statusKeyFn?: (item: T) => string;
  basePath: string;
  label?: string;
  className?: string;
  query?: Record<string, any>;
  navigateSuffix?: string;
  getRecordPath?: (item: T) => string;
  portalContainer?: HTMLElement | null;
  onSelect?: (item: T) => void;
}

interface ListItem<T> {
  id: string;
  label: string;
  description?: string;
  status?: string;
  path?: string;
  record: T;
}

export function RecordSwitcher<T extends Record<string, any>>({
  currentId,
  currentLabel,
  hideCurrentLabel = false,
  truncateLabelAt,
  currentDescription,
  fetchFirstPage,
  fetchFromUrl,
  idKey = "base_uuid" as keyof T,
  labelKey,
  labelKeyFn,
  descriptionKey,
  descriptionKeyFn,
  statusKeyFn,
  labelClassName,
  basePath,
  label,
  className,
  query = {},
  navigateSuffix = "",
  getRecordPath,
  portalContainer,
  onSelect,
}: RecordSwitcherProps<T>) {
  const router = useRouter();

  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [items, setItems] = useState<ListItem<T>[]>([]);
  const [nextPageUrl, setNextPageUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const listRef = useRef<HTMLDivElement>(null);
  const nameTriggerRef = useRef<HTMLButtonElement>(null);
  const [sentinelNode, setSentinelNode] = useState<HTMLDivElement | null>(null);

  const fetchFirstPageRef = useRef(fetchFirstPage);
  const fetchFromUrlRef = useRef(fetchFromUrl);
  const requestVersionRef = useRef(0);

  fetchFirstPageRef.current = fetchFirstPage;
  fetchFromUrlRef.current = fetchFromUrl;

  // ── Debounce search ─────────────────────────────────────────────
  useEffect(() => {
    const tid = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(tid);
  }, [search]);

  // ── Reset on close or record change ──────────────────────────────
  useEffect(() => {
    if (!open) {
      setSearch("");
      setItems([]);
      setNextPageUrl(null);
    }
  }, [open]);

  useEffect(() => {
    setOpen(false);
    setSearch("");
    setItems([]);
    setNextPageUrl(null);
    setIsLoading(false);
    setIsLoadingMore(false);
  }, [currentId]);

  // ── Fetch first page ─────────────────────────────────────────────
  useEffect(() => {
    const version = ++requestVersionRef.current;
    const isCurrent = () => requestVersionRef.current === version;

    setItems([]);
    setNextPageUrl(null);
    setIsLoadingMore(false);
    setIsLoading(open);

    const invalidate = () => {
      requestVersionRef.current += 1;
    };

    if (!open || search !== debouncedSearch) return invalidate;

    fetchFirstPageRef
      .current({search: debouncedSearch, ...query})
      .then((res) => {
        if (!isCurrent()) return;
        setItems(mapItems(res.results));
        setNextPageUrl(res.next ?? null);
      })
      .finally(() => {
        if (isCurrent()) setIsLoading(false);
      });

    return invalidate;
  }, [open, search, debouncedSearch, currentId]);

  // ── Infinite scroll ──────────────────────────────────────────────
  const sentinelRef = useCallback((node: HTMLDivElement | null) => {
    setSentinelNode(node);
  }, []);

  useEffect(() => {
    if (
      !open ||
      search !== debouncedSearch ||
      isLoading ||
      !nextPageUrl ||
      !sentinelNode ||
      isLoadingMore
    )
      return;

    const version = requestVersionRef.current;
    const isCurrent = () => requestVersionRef.current === version;
    let started = false;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting || started || !isCurrent()) return;
        started = true;

        setIsLoadingMore(true);

        fetchFromUrlRef
          .current({url: nextPageUrl})
          .then((res) => {
            if (!isCurrent()) return;
            setItems((prev) => {
              const incoming = mapItems(res.results);
              const deduped = incoming.filter((n) => !prev.some((e) => e.id === n.id));
              return [...prev, ...deduped];
            });

            setNextPageUrl(res.next ?? null);
          })
          .finally(() => {
            if (isCurrent()) setIsLoadingMore(false);
          });
      },
      {root: listRef.current, rootMargin: "10px", threshold: 0.1},
    );

    observer.observe(sentinelNode);
    return () => observer.disconnect();
  }, [
    open,
    search,
    debouncedSearch,
    currentId,
    isLoading,
    nextPageUrl,
    sentinelNode,
    isLoadingMore,
  ]);

  // ── Helpers ──────────────────────────────────────────────────────
  const mapItems = (results: T[]): ListItem<T>[] =>
    results.map((item) => ({
      id: String(item[idKey]),
      label: labelKeyFn
        ? labelKeyFn(item)
        : labelKey
          ? String(item[labelKey])
          : String(item[idKey]),
      description: descriptionKeyFn
        ? descriptionKeyFn(item)
        : descriptionKey
          ? String(item[descriptionKey])
          : undefined,
      status: statusKeyFn?.(item),
      path: getRecordPath?.(item),
      record: item,
    }));

  const handleSelect = (id: string) => {
    setOpen(false);
    if (id === currentId) return;

    const selected = items.find((item) => item.id === id);

    if (selected && onSelect) {
      onSelect(selected.record);
      return;
    }

    router.push(selected?.path ?? `${basePath}/${id}${navigateSuffix}`);
  };

  const safeLabel = currentLabel?.trim() || "Untitled record";
  const singularLabel = label?.replace(/s$/i, "") || "record";
  const useTruncatedLabel = truncateLabelAt !== undefined && !hideCurrentLabel;

  const chevronIcon = (
    <Icon
      icon="hugeicons:arrow-down-01"
      className={cn(
        "shrink-0 w-4 h-4 text-muted-foreground/60 transition-transform",
        open && "rotate-180",
      )}
    />
  );

  return (
    <Popover key={currentId} open={open} onOpenChange={setOpen}>
      {useTruncatedLabel && (
        <PopoverAnchor className={cn("min-w-0 max-w-full", className)}>
          <div className="flex min-w-0 items-center gap-1.5">
            <TruncatedText
              text={safeLabel}
              maxLength={truncateLabelAt}
              singleLine
              textClassName={cn(
                "text-xl sm:text-2xl font-semibold font-mono tracking-tight text-foreground leading-tight",
                labelClassName,
              )}
              renderText={(text) => (
                <PopoverTrigger asChild>
                  <button
                    ref={nameTriggerRef}
                    type="button"
                    aria-label={`Switch ${singularLabel.toLowerCase()}: ${safeLabel}`}
                    className="min-w-0 overflow-hidden whitespace-nowrap rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {text}
                  </button>
                </PopoverTrigger>
              )}
            />
            <PopoverTrigger asChild>
              <button
                type="button"
                aria-label={label ? `Switch ${label}` : "Switch record"}
                className="shrink-0 rounded-sm p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {chevronIcon}
              </button>
            </PopoverTrigger>
          </div>
          {currentDescription && (
            <p className="mt-0.5 truncate text-base font-normal text-muted-foreground">
              {currentDescription}
            </p>
          )}
        </PopoverAnchor>
      )}
      {!useTruncatedLabel && (
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={hideCurrentLabel ? (label ? `Switch ${label}` : "Switch record") : undefined}
          className={cn(
            "group inline-flex w-fit items-center gap-1.5 text-left bg-transparent p-0 m-0",
            "focus:outline-none",
            className,
          )}
        >
          {!hideCurrentLabel && (
            <span className="flex flex-col min-w-0 max-w-[70vw] sm:max-w-none">
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "text-xl sm:text-2xl font-semibold font-mono tracking-tight text-foreground leading-tight truncate",
                    labelClassName,
                  )}
                >
                  {safeLabel}
                </span>

                {chevronIcon}
              </span>

              {currentDescription && (
                <span className="text-base font-normal text-muted-foreground truncate mt-0.5">
                  {currentDescription}
                </span>
              )}
            </span>
          )}

          {hideCurrentLabel && chevronIcon}
        </button>
      </PopoverTrigger>
      )}

      {/* ── MOBILE-FIRST POPOVER ───────────────────────────────────── */}
      <PopoverContent
        container={portalContainer}
        className={cn(
          "p-0 shadow-xl border border-border",
          "w-[calc(100vw-2rem)] sm:w-80",
          "max-h-[85vh] overflow-hidden",
          "rounded-xl sm:rounded-lg",
        )}
        align="start"
        side="bottom"
        sideOffset={8}
        collisionPadding={16}
        style={{zIndex: 99999}}
        onInteractOutside={(event) => {
          const target = event.detail.originalEvent.target;
          if (target instanceof Node && nameTriggerRef.current?.contains(target)) {
            event.preventDefault();
          }
        }}
      >
        {/* Header */}
        <div className="px-3 pt-3 pb-2.5 border-b border-border/60">
          <p className="text-base font-semibold">{label ? `Switch ${label}` : "Switch record"}</p>
          <p className="text-[15px] text-muted-foreground mt-0.5">
            Search and select a {singularLabel.toLowerCase()}
          </p>
        </div>

        <Command shouldFilter={false}>
          <CommandInput
            placeholder={`Search ${label?.toLowerCase() ?? "records"}…`}
            value={search}
            onValueChange={setSearch}
            className="!border-none text-base"
          />

          <CommandEmpty>
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 py-4 text-base">
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-t-transparent" />
                Loading…
              </div>
            ) : (
              <span className="text-base text-muted-foreground">No results found.</span>
            )}
          </CommandEmpty>

          <CommandGroup>
            <CommandList ref={listRef} className="max-h-[65vh] sm:max-h-[280px] overflow-y-auto">
              {/* Loading skeleton */}
              {isLoading && items.length === 0
                ? Array.from({length: 5}).map((_, i) => (
                    <div key={i} className="flex items-center gap-3 px-3 py-3 mx-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-muted" />
                      <div className="flex-1 space-y-1.5">
                        <div
                          className="h-2.5 bg-muted animate-pulse rounded"
                          style={{width: `${55 + i * 8}%`}}
                        />
                        <div className="h-2 bg-muted/60 animate-pulse rounded w-2/5" />
                      </div>
                    </div>
                  ))
                : items.map((item) => {
                    const isCurrent = item.id === currentId;

                    return (
                      <CommandItem
                        key={item.id}
                        value={item.id}
                        onSelect={() => handleSelect(item.id)}
                        className={cn(
                          "flex items-start gap-2.5 px-3 py-3 sm:py-2.5",
                          "cursor-pointer rounded-lg mx-1 my-0.5",
                          isCurrent && "bg-primary/10 border border-primary/20",
                        )}
                      >
                        <div className="flex-1 min-w-0">
                          <div>
                            <p
                              className={cn(
                                "min-w-0 truncate text-base font-medium",
                                isCurrent ? "text-primary" : "text-foreground",
                              )}
                            >
                              {item.label}
                            </p>

                            {item.status && (
                              <span
                                className={cn(
                                  "mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                                  item.status === "approved" && "bg-green-100 text-green-700",
                                  item.status === "pending" && "bg-amber-100 text-amber-700",
                                  item.status === "rejected" && "bg-red-100 text-red-700",
                                )}
                              >
                                {item.status}
                              </span>
                            )}
                          </div>
                          {item.description && (
                            <p className="text-xs text-muted-foreground truncate mt-0.5">
                              {item.description}
                            </p>
                          )}
                        </div>

                        {isCurrent && (
                          <span className="text-[14px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                            current
                          </span>
                        )}
                      </CommandItem>
                    );
                  })}

              {/* Infinite scroll sentinel */}
              {nextPageUrl && (
                <div ref={sentinelRef} className="h-6 flex items-center justify-center">
                  {isLoadingMore && (
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" />
                  )}
                </div>
              )}
            </CommandList>
          </CommandGroup>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
