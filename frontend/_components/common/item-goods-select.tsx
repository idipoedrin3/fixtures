"use client";

import {useMemo} from "react";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {INVENTORY_ITEMS_API} from "#/_api/api.helpers";
import {IInventoryItem} from "#/_types/api.types";

interface InventoryGoodsSelectProps {
  value?: string | null;
  onValueChange?: (id: string) => void;
  onItemSelected?: (item: IInventoryItem | null) => void;
  error?: string;
  disabled?: boolean;
  description?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  clearButton?: boolean;
  excludeIds?: string[];
  className?: string;
  initialData?: IInventoryItem[];
  createAction?: {label: string; onClick: () => void};
  fetchById?: (id: string) => Promise<IInventoryItem>;
}

export function InventoryGoodsSelect({
  value,
  onValueChange,
  onItemSelected,
  error,
  disabled,
  description,
  placeholder = "Select inventory item",
  searchPlaceholder = "Search items...",
  emptyMessage = "No items found",
  clearButton = true,
  excludeIds,
  className,
  initialData,
  createAction,
  fetchById,
}: InventoryGoodsSelectProps) {
  const fetchItems = useMemo(
    () => (args: Record<string, any>) =>
      INVENTORY_ITEMS_API.fetchInventoryItems({...args, item_type: "GOODS"}),
    [],
  );

  const fetchItemsFromUrl = useMemo(
    () =>
      ({url}: {url: string}) =>
        INVENTORY_ITEMS_API.fetchInventoryItemsFromUrl({url}),
    [],
  );

  const defaultFetchById = useMemo(
    () => async (id: string) => {
      if (!id) return Promise.resolve(null as any);
      return INVENTORY_ITEMS_API.fetchInventoryItemById({itemUuid: id});
    },
    [],
  );

  return (
    <div className="space-y-1">
      <PaginatedSearchableSelect<IInventoryItem>
        fetchFirstPage={fetchItems}
        fetchFromUrl={fetchItemsFromUrl}
        fetchById={fetchById ?? defaultFetchById}
        initialData={initialData}
        idKey="base_uuid"
        valueKey="base_uuid"
        labelKey="item_name"
        labelDescKey="reference_code"
        value={value}
        onValueChange={(ids) => onValueChange?.(ids[0] ?? "")}
        onItemSelected={onItemSelected}
        placeholder={placeholder}
        searchPlaceholder={searchPlaceholder}
        emptyMessage={emptyMessage}
        description={description}
        disabled={disabled}
        clearButton={clearButton}
        excludeIds={excludeIds}
        className={className}
        createAction={createAction}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
