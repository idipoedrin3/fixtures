"use client";

import {useState, useEffect, useRef, useCallback} from "react";
import {Loader2, Check} from "lucide-react";
import {Icon} from "@iconify/react";

import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {ScrollArea} from "@/components/ui/scroll-area";
import {cn} from "@/lib/utils";

interface InfiniteScrollSelectProps<T> {
  items: T[];
  loading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
  onSearch: (query: string) => void;
  onSelect: (item: T) => void;
  selectedItem: T | null;
  getItemId: (item: T) => string | number;
  getItemLabel: (item: T) => string;
  getItemDescription?: (item: T) => string;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  className?: string;
}

export function InfiniteScrollSelect<T>({
  items,
  loading,
  hasMore,
  onLoadMore,
  onSearch,
  onSelect,
  selectedItem,
  getItemId,
  getItemLabel,
  getItemDescription,
  placeholder = "Select an item...",
  searchPlaceholder = "Search...",
  emptyMessage = "No items found",
  className,
}: InfiniteScrollSelectProps<T>) {
  const [searchQuery, setSearchQuery] = useState("");
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const [edit, setEdit] = useState(true);

  const handleSearch = useCallback(
    (query: string) => {
      setSearchQuery(query);
      onSearch(query);
    },
    [onSearch],
  );

  // Set up intersection observer for infinite scroll
  useEffect(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    observerRef.current = new IntersectionObserver(
      (entries) => {
        const target = entries[0];

        if (target.isIntersecting && hasMore && !loading) {
          onLoadMore();
        }
      },
      {
        threshold: 0.1,
      },
    );

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [hasMore, loading, onLoadMore]);

  return (
    <div className={cn("w-full", className)}>
      {/* Search Input */}
      {edit && (
        <div className="relative mb-4">
          <Icon
            icon="hugeicons:search-01"
            className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4"
          />
          <Input
            placeholder={searchPlaceholder}
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-10 rounded-xl"
          />
        </div>
      )}

      {/* Selected Item Display */}
      {!edit && selectedItem && (
        <div
          onClick={() => setEdit(true)}
          className="mb-4 p-3 bg-primary/10 border border-primary/20 rounded-lg cursor-pointer"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-primary capitalize">{getItemLabel(selectedItem)}</p>
              {getItemDescription && (
                <p className="text-sm text-gray-600 capitalize">
                  {getItemDescription(selectedItem)}
                </p>
              )}
            </div>
            <Check className="h-5 w-5 text-primary" />
          </div>
        </div>
      )}

      {/* Items List */}
      {edit && (
        <ScrollArea className="h-48 border rounded-xl" ref={scrollAreaRef}>
          <div className="p-2">
            {items?.length === 0 && !loading ? (
              <div key="empty-state" className="text-center py-8 text-gray-500">
                <p>{emptyMessage}</p>
              </div>
            ) : (
              <>
                {items?.map((item, index) => {
                  const isSelected = selectedItem && getItemId(selectedItem) === getItemId(item);
                  const itemKey = getItemId(item) || `item-${index}`;

                  return (
                    <Button
                      key={itemKey}
                      type="button"
                      variant="ghost"
                      className={cn(
                        "w-full justify-start p-3 h-auto mb-1",
                        isSelected && "bg-primary/10 border border-primary/20",
                      )}
                      onClick={() => {
                        onSelect(item);
                        setEdit(false);
                      }}
                    >
                      <div className="flex items-center justify-between w-full">
                        <div className="text-left">
                          <p className="font-medium capitalize">{getItemLabel(item)}</p>
                          {getItemDescription && (
                            <p className="text-sm text-gray-600 capitalize">
                              {getItemDescription(item)}
                            </p>
                          )}
                        </div>
                        {isSelected && <Check className="h-4 w-4 text-primary" />}
                      </div>
                    </Button>
                  );
                })}

                {/* Load More Trigger */}
                {hasMore && (
                  <div
                    key="load-more-trigger"
                    ref={loadMoreRef}
                    className="flex justify-center py-4"
                  >
                    {loading && <Loader2 className="h-6 w-6 animate-spin text-gray-400" />}
                  </div>
                )}

                {/* Loading State */}
                {loading && items?.length === 0 && (
                  <div key="loading-state" className="flex justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                  </div>
                )}
              </>
            )}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
