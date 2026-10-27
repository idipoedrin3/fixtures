"use client";

import {BRANCH_INVENTORY_API, INVENTORY_ITEMS_API} from "#/_api/api.helpers";
import {IBranchInventoryItem, IInventoryItem} from "#/_types/api.types";
import {truncateText} from "#/_lib/utils";
import PaginatedSearchableSelect from "./paginated-searchable-select";

export type InventoryItemSelectLevel = "branch" | "institution";

export type InventorySelectableItem = IBranchInventoryItem | IInventoryItem;

type Props = {
  level?: InventoryItemSelectLevel;
  branchBaseUuid?: string;
  canBeSold?: boolean;
  canBePurchased?: boolean;
  itemType?: "GOODS" | "SERVICES";
  value?: string | number | null;
  initialData?: InventorySelectableItem[];
  disabled?: boolean;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  onValueChange?: (value: string[]) => void;
  onItemSelected?: (item: InventorySelectableItem | null) => void;
};

function isBranchInventoryItem(item: InventorySelectableItem): item is IBranchInventoryItem {
  return "inventory_item" in item;
}

export function getItemName(item: InventorySelectableItem) {
  return isBranchInventoryItem(item) ? item.inventory_item?.item_name : item.item_name;
}

function getItemCode(item: InventorySelectableItem) {
  return isBranchInventoryItem(item) ? item.inventory_item?.reference_code : item.reference_code;
}

function isServiceItem(item: InventorySelectableItem) {
  return isBranchInventoryItem(item)
    ? item.inventory_item?.item_type === "SERVICES" ||
        item.branch_inventory_item?.item_type === "SERVICES"
    : item.item_type === "SERVICES";
}

function getItemDescription(item: InventorySelectableItem) {
  if (isServiceItem(item)) {
    return getItemCode(item) ?? "-";
  }

  if (isBranchInventoryItem(item)) {
    const branchName = item.branch?.branch_name
      ? ` at ${truncateText(item.branch.branch_name, 10)}`
      : "";

    return `${getItemCode(item) ?? "-"} - ${item.quantity ?? 0} in stock${branchName}`;
  }

  return `${getItemCode(item) ?? "-"} - ${item.quantity_on_hand ?? 0} in stock`;
}

export default function InventoryItemSelect({
  level = "branch",
  branchBaseUuid,
  canBeSold,
  canBePurchased,
  itemType,
  value,
  initialData,
  disabled,
  placeholder = "Select item",
  searchPlaceholder = "Search items...",
  emptyMessage = "No items found",
  onValueChange,
  onItemSelected,
}: Props) {
  const query = {
    ...(branchBaseUuid ? {branch_uuids: branchBaseUuid} : {}),
    ...(canBeSold !== undefined ? {can_be_sold: canBeSold} : {}),
    ...(canBePurchased !== undefined ? {can_be_purchased: canBePurchased} : {}),
    ...(itemType ? {item_type: itemType} : {}),
  };

  const fetchFirstPage =
    level === "branch"
      ? BRANCH_INVENTORY_API.fetchBranchInventory
      : INVENTORY_ITEMS_API.fetchInventoryItems;

  const fetchFromUrl =
    level === "branch"
      ? BRANCH_INVENTORY_API.fetchBranchInventoryFromUrl
      : INVENTORY_ITEMS_API.fetchInventoryItemsFromUrl;

  return (
    <PaginatedSearchableSelect<InventorySelectableItem>
      fetchFirstPage={(params) => fetchFirstPage(params) as any}
      fetchFromUrl={(params) => fetchFromUrl(params) as any}
      placeholder={placeholder}
      searchPlaceholder={searchPlaceholder}
      emptyMessage={emptyMessage}
      idKey="base_uuid"
      valueKey="base_uuid"
      labelKeyFn={(item) => getItemName(item) ?? "-"}
      labelDescKeyFn={getItemDescription}
      value={value}
      initialData={initialData}
      query={query}
      onValueChange={onValueChange ?? (() => {})}
      onItemSelected={onItemSelected}
      disabled={disabled}
    />
  );
}
