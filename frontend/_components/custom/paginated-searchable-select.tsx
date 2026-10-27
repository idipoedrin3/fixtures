"use client";

import * as React from "react";
import {Check, X, Loader2} from "lucide-react";
import {Icon} from "@iconify/react";
import {toast} from "sonner";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {formatCurrency} from "#/_lib/utils";
import {cn} from "@/lib/utils";
import {IPaginatedResponse} from "#/_types/api.types";
import {capitalizeEachWord} from "#/_api/helpers";

// Generic item type for the select
export type PaginatedSelectItem<T> = T;

// Fetchers for paginated data
export type FetchFirstPageFn<T> = (query: any) => Promise<IPaginatedResponse<T>>;
export type FetchFromUrlFn<T> = (args: {url: string}) => Promise<IPaginatedResponse<T>>;
export type FetchByIdFn<T> = (id: string) => Promise<T>;

export interface PaginatedSearchableSelectProps<T> {
  initialData?: T[];
  fetchFirstPage: FetchFirstPageFn<T>;
  fetchFromUrl: FetchFromUrlFn<T>;
  fetchById?: FetchByIdFn<T>;
  idKey: keyof T;
  valueKey: keyof T;
  labelKey?: keyof T;
  labelKeyFn?: (item: T) => string;
  renderLabel?: (item: T) => React.ReactNode;
  labelPrepend?: string;
  labelDescKey?: keyof T;
  labelDescKeyFn?: (item: T) => string;
  onValueChange: (value: string[]) => void;
  showSelectedItems?: boolean;
  multiple?: boolean;
  disabled?: boolean;
  className?: string;
  id?: string;
  popoverModal?: boolean;
  defaultLabel?: string;
  triggerClassName?: string;
  popoverClassName?: string;
  placeholder?: string;
  emptyMessage?: string;
  searchPlaceholder?: string;

  clearButton?: boolean;
  initialSelectedLabel?: string;
  description?: string;

  onItemsChange?: (data: T[]) => void;

  onItemSelected?: (item: T | null) => void;
  value?: string | number | null;
  capitalizeLabels?: boolean;
  query?: Record<string, string | number | boolean>;
  popoverSide?: "top" | "bottom" | "left" | "right";
  popoverAlign?: "start" | "center" | "end";

  excludeIds?: string[];
  popoverContainer?: HTMLElement | null;

  createAction?: {
    label: string;
    onClick: () => void;
  };
  refreshOnOpen?: boolean;
}

export function PaginatedSearchableSelect<T extends Record<string, any>>({
  initialData,
  fetchFirstPage,
  fetchFromUrl,
  fetchById,
  idKey,
  valueKey,
  labelKey,
  labelKeyFn,
  renderLabel,
  labelPrepend,
  labelDescKey,
  labelDescKeyFn,
  onValueChange,
  multiple = false,
  disabled = false,
  showSelectedItems = false,
  className,
  id,

  defaultLabel,
  triggerClassName,
  popoverClassName,
  popoverModal = false,
  placeholder = "Select an item",
  emptyMessage = "No items found.",
  searchPlaceholder = "Search items...",
  description,
  initialSelectedLabel,
  clearButton = true,
  capitalizeLabels = true,
  onItemsChange,
  onItemSelected,
  value,
  popoverAlign,
  popoverSide,
  query = {},
  excludeIds = [],
  popoverContainer,
  createAction,
  refreshOnOpen = false,
}: PaginatedSearchableSelectProps<T>) {
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [data, setData] = React.useState<IPaginatedResponse<PaginatedSelectItem<T>> | null>({
    next: "",
    previous: "",
    results: initialData ?? [],
    count: initialData?.length ?? 0,
  });
  const wasValueEverSetRef = React.useRef(false);
  const [search, setSearch] = React.useState("");
  const [hasMore, setHasMore] = React.useState(true);
  const listRef = React.useRef<HTMLDivElement>(null);
  const [sentinelNode, setSentinelNode] = React.useState<HTMLDivElement | null>(null);
  const [selectedItem, setSelectedItem] = React.useState<T | null>(
    !multiple && initialData?.length ? initialData[0] : null,
  );
  const sentinelRef = React.useCallback((node: HTMLDivElement | null) => {
    setSentinelNode(node);
  }, []);

  const [selectedItems, setSelectedItems] = React.useState<string[]>(
    initialData?.map((x) => String(x[idKey])) ?? [],
  );

  const [selectedItemsList, setSelectedItemsList] = React.useState<T[]>(
    initialData?.length && initialData.length > 0 ? initialData : ([] as any),
  );

  const isSyncingFromValueRef = React.useRef(false);
  const [isResolvingValue, setIsResolvingValue] = React.useState(false);
  const prevInitialDataIdsRef = React.useRef<string>("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  const loadMoreTimeoutRef = React.useRef<number | undefined>(undefined);
  const loadMoreObserverRef = React.useRef<IntersectionObserver | undefined>(undefined);

  // const isSyncingFromProp = React.useRef(false);

  React.useEffect(() => {
    const tid = setTimeout(() => {
      setDebouncedSearch(search);
    }, 400);
    return () => clearTimeout(tid);
  }, [search]);

  React.useEffect(() => {
    if (!initialData?.length) return;

    const newIds = initialData.map((d) => String(d[idKey])).join(",");
    if (prevInitialDataIdsRef.current === newIds) return;
    prevInitialDataIdsRef.current = newIds;

    setData((prev) => ({
      ...(prev ?? {next: "", previous: "", count: 0, results: []}),
      results: [
        ...initialData,
        ...(prev?.results?.filter(
          (r) => !initialData.some((d) => String(d[idKey]) === String(r[idKey])),
        ) ?? []),
      ],
    }));

    if (value !== undefined && value !== null && !multiple) {
      const match = initialData.find((d) => String(d[idKey]) === String(value));
      if (match) {
        isSyncingFromValueRef.current = true;
        setSelectedItem(match);
        setSelectedItems([String(match[idKey])]);
      }
    }
  }, [initialData]);

  // Fetch first page for paginated mode
  React.useEffect(() => {
    if (!fetchFirstPage || disabled || !open) return;
    if (!refreshOnOpen && data && data.next && !debouncedSearch) return;

    setLoading(true);
    fetchFirstPage({search: debouncedSearch, ...(query || {})})
      .then((res: IPaginatedResponse<T>) => {
        setData(res as IPaginatedResponse<PaginatedSelectItem<T>>);
        setHasMore(!!res.next);
      })
      .catch(() => toast.error("Failed to load items"))
      .finally(() => setLoading(false));
  }, [fetchFirstPage, debouncedSearch, disabled, open, refreshOnOpen]);

  React.useEffect(() => {
    if (multiple) return;

    if (value !== undefined && value !== null) {
      wasValueEverSetRef.current = true;
    }

    if (value === undefined || value === null) {
      if (!wasValueEverSetRef.current) {
        setIsResolvingValue(false);
        return;
      }
      if (selectedItems.length > 0 || selectedItem !== null) {
        isSyncingFromValueRef.current = true;
        setSelectedItems([]);
        setSelectedItem(null);
      }
      setIsResolvingValue(false);
      return;
    }

    const strValue = String(value);

    if (selectedItems.length === 1 && selectedItems[0] === strValue && selectedItem) {
      return;
    }

    const found = data?.results?.find((item) => String(item[idKey]) === strValue);

    isSyncingFromValueRef.current = true;

    if (selectedItems.length !== 1 || selectedItems[0] !== strValue) {
      setSelectedItems([strValue]);
    }

    if (found) {
      if (selectedItem !== found) setSelectedItem(found);
      setIsResolvingValue(false);
      return;
    }

    if (!fetchById) {
      setIsResolvingValue(false);
      return;
    }

    if (isResolvingValue) return;

    setIsResolvingValue(true);

    fetchById(strValue)
      .then((item) => {
        if (!item) return;
        setSelectedItem(item);
        setData((prev) => ({
          ...(prev ?? {results: [], count: 0, next: "", previous: ""}),
          results: [item, ...(prev?.results?.filter((x) => String(x[idKey]) !== strValue) ?? [])],
        }));
      })
      .finally(() => {
        setIsResolvingValue(false);
      });
  }, [value, multiple, idKey, data?.results, fetchById]);

  React.useEffect(() => {
    if (!data?.next || !fetchFromUrl || loading || !sentinelNode || disabled) return;

    if (debouncedSearch) {
      loadMoreObserverRef.current?.disconnect();
      if (loadMoreTimeoutRef.current) clearTimeout(loadMoreTimeoutRef.current);
      loadMoreTimeoutRef.current = undefined;
      setHasMore(false);
      return;
    }

    loadMoreObserverRef.current?.disconnect();

    if (loadMoreTimeoutRef.current) {
      clearTimeout(loadMoreTimeoutRef.current);
      loadMoreTimeoutRef.current = undefined;
      return;
    }

    loadMoreTimeoutRef.current = window.setTimeout(() => {
      loadMoreObserverRef.current = new IntersectionObserver(
        (entries) => {
          const entry = entries[0];

          if (!hasMore) return;
          if (entry.isIntersecting && !loading) {
            setLoading(true);
            fetchFromUrl({url: data.next!})
              .then((res: IPaginatedResponse<T> | null) => {
                if (res && (!data.next || data.next !== res.next)) {
                  setHasMore(!!res.next);
                  setData((prev) => ({
                    ...res,
                    results: [...(prev?.results || []), ...res.results],
                  }));
                }
              })
              .catch((error: any) => {
                toast.error("Failed to load more items");
              })
              .finally(() => setLoading(false));
          }
        },
        {
          root: listRef.current,
          rootMargin: "5px",
          threshold: 0.1,
        },
      );
      loadMoreObserverRef.current.observe(sentinelNode);
    }, 1500);

    return () => {
      loadMoreObserverRef.current?.disconnect();
      if (loadMoreTimeoutRef.current) clearTimeout(loadMoreTimeoutRef.current);
      loadMoreTimeoutRef.current = undefined;
    };
  }, [data?.next, fetchFromUrl, loading, sentinelNode, hasMore, disabled, debouncedSearch, query]);

  const handleSelect = (itemId: string | number) => {
    const item = (data?.results ?? []).find((item) => item[idKey] === itemId);

    if (!item) return;
    if (multiple && selectedItems.includes(itemId.toString()) && onRemove) {
      onRemove(itemId, item);
    } else {
      onSelect(itemId, item);
      if (!multiple) setOpen(false);
    }
  };

  const onSelect = (itemId: string | number, item: PaginatedSelectItem<T>) => {
    isSyncingFromValueRef.current = false;
    if (!selectedItems.includes(itemId.toString())) {
      let newItems: string[];

      if (multiple) {
        newItems = [itemId.toString(), ...selectedItems];
        setSelectedItem(null);
      } else {
        newItems = [itemId.toString()];
        setSelectedItem(item);
      }
      setSelectedItems(newItems);
      setSelectedItemsList((prev) => [item, ...prev]);
    }
  };

  const onRemove = (itemId: string | number, _item: PaginatedSelectItem<T>) => {
    isSyncingFromValueRef.current = false;
    const newItems = selectedItems.filter((id) => String(id) !== String(itemId));

    setSelectedItems(newItems);
    setSelectedItemsList((prev) => {
      const nxt = [...prev].filter((x) => x[idKey] !== itemId);
      return nxt;
    });
  };

  const onClear = () => {
    isSyncingFromValueRef.current = false;
    setSelectedItem(null);
    setSelectedItems([]);
    setSelectedItemsList([]);
  };

  const getLabel = (item: T) => {
    return labelKeyFn ? labelKeyFn(item) : item[labelKey || valueKey];
  };

  const getRenderedLabel = (item: T) => {
    return renderLabel ? renderLabel(item) : getLabel(item);
  };

  const displayedSelectedItem =
    !multiple && value !== undefined && value !== null
      ? ([selectedItem, ...(initialData ?? []), ...(data?.results ?? [])].find(
          (item): item is T => item != null && String(item[idKey]) === String(value),
        ) ?? null)
      : selectedItem;

  const getLabelDesc = (item: T) => {
    return labelDescKeyFn
      ? labelDescKeyFn(item)
      : labelDescKey
        ? typeof item[labelDescKey] === "number" || !isNaN(Number(item[labelDescKey]))
          ? formatCurrency(Number(item[labelDescKey]))
          : String(item[labelDescKey])
        : "";
  };

  React.useEffect(() => {
    onItemSelected?.call(undefined, selectedItem);
  }, [selectedItem]);

  React.useEffect(() => {
    if (isSyncingFromValueRef.current) {
      isSyncingFromValueRef.current = false;
      return;
    }
    // if (isSyncingFromProp.current) {
    //   isSyncingFromProp.current = false;
    //   return;
    // }
    onValueChange?.call(undefined, selectedItems);
  }, [selectedItems]);

  React.useEffect(() => {
    onItemsChange?.call(undefined, selectedItemsList);
  }, [selectedItemsList]);

  React.useEffect(() => {
    if (!open) setSearch("");
  }, [open]);

  return (
    <div className={cn("relative", className)}>
      {multiple && showSelectedItems && (
        <div className="py-1">
          <div className="flex items-center justify-start gap-2 flex-wrap">
            {!defaultLabel ? (
              <>
                {(data?.results ?? [])
                  .filter((resItem) => !excludeIds.includes(String(resItem[idKey])))
                  .filter((resItem) =>
                    selectedItems.find((item: any) => String(item) === String(resItem[idKey])),
                  )
                  .map((itemData, idx) => {
                    return (
                      <span
                        key={idx}
                        className="pl-2.5 rounded-full text-sm inline-flex bg-background border text-foreground py-0.5 w-fit items-center gap-1"
                      >
                        <span className="flex-grow line-clamp-1">
                          {capitalizeLabels
                            ? capitalizeEachWord(getLabel(itemData))
                            : getLabel(itemData)}
                        </span>

                        {!disabled ? (
                          <button
                            className="rounded-full mx-1 !px-1 bg-red-500/10 hover:bg-red-500/20 cursor-pointer aspect-square !text-xs"
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onRemove(itemData[idKey], itemData);
                            }}
                          >
                            <X className="!h-3 !w-3 text-red-500" />
                          </button>
                        ) : (
                          <span />
                        )}
                      </span>
                    );
                  })}
              </>
            ) : (
              <span className="px-2 rounded-full text-sm inline-flex bg-primary/20 text-primary py-1 w-fit items-center gap-1 max-w-xs">
                {defaultLabel}
              </span>
            )}
          </div>
        </div>
      )}
      <Popover open={open} onOpenChange={setOpen} modal={popoverModal}>
        <PopoverTrigger disabled={disabled} className="w-full disabled:cursor-not-allowed">
          <div className="w-full min-w-full">
            <div
              aria-expanded={open}
              className={cn(
                "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
                "border border-input bg-background",
                "h-10 px-4 py-2",
                "w-full flex h-[44px] rounded-lg border-input hover:bg-transparent",
                triggerClassName,
                disabled ? "!bg-accent !text-accent-foreground" : "",
              )}
              role="combobox"
            >
              <span className="truncate flex-grow text-left flex items-center gap-2">
                {!multiple && isResolvingValue ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin opacity-60" />
                    <span className="opacity-60">Loading selection…</span>
                  </>
                ) : multiple ? (
                  selectedItems.length > 0 ? (
                    `${selectedItems.length} ${
                      selectedItems.length === 1 ? "item" : "items"
                    } selected`
                  ) : (
                    capitalizeEachWord(placeholder)
                  )
                ) : displayedSelectedItem ? (
                  getRenderedLabel(displayedSelectedItem)
                ) : initialSelectedLabel && value ? (
                  initialSelectedLabel
                ) : (
                  capitalizeEachWord(placeholder)
                )}
              </span>

              {!multiple &&
                !disabled &&
                (displayedSelectedItem || (initialSelectedLabel && value)) &&
                !isResolvingValue &&
                clearButton && (
                  <span
                    title="Clear"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onClear();
                    }}
                    className="bg-accent px-1 py-1 rounded-full"
                  >
                    <Icon icon="hugeicons:cancel-01" className="size-2.5 opacity-60" />
                  </span>
                )}

              <Icon icon="hugeicons:arrow-down-01" className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </div>
            {description ? (
              <p className="!text-left text-xs md:text-sm opacity-50">{description}</p>
            ) : null}
          </div>
        </PopoverTrigger>
        <PopoverContent
          onWheel={(event) => event.stopPropagation()}
          {...(popoverContainer ? {container: popoverContainer} : {})}
          id={id || ""}
          className={cn("w-full p-0", popoverClassName)}
          style={{
            minWidth: "var(--radix-popper-anchor-width)",
            maxWidth: "var(--radix-popper-anchor-width)",
            zIndex: 99999,
          }}
          side={popoverSide}
          align={popoverAlign}
          //avoidCollisions={false}
        >
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={capitalizeEachWord(searchPlaceholder)}
              value={search}
              onValueChange={setSearch}
              className="!border-none"
            />
            {multiple && selectedItems.length > 0 && (
              <div className="flex items-center justify-between border-y px-3 py-2">
                <span className="text-xs font-medium text-muted-foreground">
                  {selectedItems.length}{" "}
                  {selectedItems.length === 1 ? "item selected" : "items selected"}
                </span>
                {!disabled && (
                  <button
                    type="button"
                    className="text-xs font-medium text-primary hover:underline"
                    onMouseDown={(event) => {
                      event.preventDefault();
                      onClear();
                    }}
                  >
                    Clear all
                  </button>
                )}
              </div>
            )}
            <CommandEmpty>
              {loading || hasMore ? (
                <div className="flex items-center justify-center gap-4 py-2 text-xs text-gray-500">
                  <Loader2 className="size-4 animate-spin" />
                  <span>Loading more...</span>
                </div>
              ) : (
                capitalizeEachWord(emptyMessage)
              )}
            </CommandEmpty>
            <CommandGroup>
              <CommandList
                ref={listRef}
                className="overscroll-contain"
                style={{maxHeight: 300, overflowY: "auto"}}
              >
                {(data?.results ?? [])
                  .filter((resItem) => !excludeIds.includes(String(resItem[idKey])))
                  .map((item, i) => {
                    const isSelected = selectedItems.includes(`${item[idKey]}`);

                    return (
                      <CommandItem
                        key={i}
                        value={item[valueKey]}
                        onSelect={() => handleSelect(item[idKey])}
                      >
                        <Check
                          className={cn("mr-2 h-4 w-4", isSelected ? "opacity-100" : "opacity-0")}
                        />
                        <div className="text-left">
                          <p className={cn("font-medium", capitalizeLabels && "capitalize")}>
                            {labelPrepend ? labelPrepend : ""}
                            {getRenderedLabel(item)}
                          </p>
                          <p
                            className={cn(
                              "text-xs opacity-75 break-words whitespace-normal",
                              capitalizeLabels && "capitalize",
                            )}
                          >
                            {getLabelDesc(item)}
                          </p>
                        </div>
                        {multiple && isSelected && (
                          <button
                            type="button"
                            className="rounded-full ml-auto !px-1 bg-red-500/20 cursor-pointer aspect-square !text-xs"
                            onClick={(e) => {
                              e.stopPropagation();
                              onRemove(item[idKey], item);
                            }}
                          >
                            <X className="!h-3 !w-3 text-red-500" />
                          </button>
                        )}
                      </CommandItem>
                    );
                  })}
                {hasMore && <div ref={sentinelRef} className="h-3" />}
              </CommandList>
              {createAction && (
                <>
                  <div className="mx-2 h-px bg-border" />
                  <div className="px-1 pt-1 pb-1">
                    <button
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        createAction.onClick();
                      }}
                      className="flex items-center gap-2 w-full px-2.5 py-2 text-xs font-medium text-primary hover:bg-primary/10 rounded-md transition-colors"
                    >
                      <span className="flex items-center justify-center rounded-full bg-primary/15 h-4 w-4 shrink-0">
                        <Icon icon="hugeicons:plus-sign" className="size-2.5" />
                      </span>
                      {createAction.label}
                    </button>
                  </div>
                </>
              )}
            </CommandGroup>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

export default PaginatedSearchableSelect;
