"use client";

import {Icon} from "@iconify/react";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {Button} from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {ASSET_CATEGORIES_API, INVENTORY_ITEMS_API, INVOICES_API} from "#/_api/api.helpers";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {Input} from "@/components/ui/input";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import {formatCurrency} from "#/_lib/utils";
import {ICurrencyConversion} from "#/_api/services/system.service";
import {Currency, IAssetCategory, IInventoryItem} from "#/_types/api.types";
import {Switch} from "@/components/ui/switch";
import {TAXES_API} from "#/_api/api.helpers";
import React from "react";
import SearchableComboboxInput, {ComboboxOption} from "../common/searchable-combobox-input";

export type VendorLineItemType = "inventory" | "other" | "fixed_asset";

export type VendorLineItem = {
  type: VendorLineItemType;
  line_item: number | string;
  item_name: string;
  item_category?: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  selected_uom_uuid?: string;
  selected_uom_abbreviation?: string;
  unit_of_measure?: string | number | null;
  applicable_taxes?: {tax: number; is_inclusive: boolean}[];
  display_unit_price?: string;
  tax_base_uuid?: string;
  tax_type?: string;
  asset_category?: string;
  asset_category_name?: string;
};
interface VendorLineItemData extends VendorLineItem {
  item?: IInventoryItem;
}

type Props = {
  allowUnitPriceOverride?: boolean;
  canAdd?: boolean;
  canDelete?: boolean;
  onItemsChange?: (items: VendorLineItem[]) => void;
  onValidationChange?: (isValid: boolean) => void;
  initialItems?: VendorLineItemData[];
  model_name?: ICurrencyConversion["model_name"];
  object_uuid?: ICurrencyConversion["object_uuid"];
  currency?: Currency | null;
  hideCurrency?: boolean;
  readonly?: boolean;
  uomValueType?: "uuid" | "id";
  isInventoryBased?: boolean;
  withTaxes?: boolean;
  title?: string;
  description?: string;
  calculateTaxOnUnitPrice?: boolean;
  itemText?: boolean;
  lineItemValueType?: "id" | "base_uuid";
  itemOptionsLoader?: () => Promise<ComboboxOption[]>;
  itemSearchFn?: (search: string) => Promise<ComboboxOption[]>;
};

export default function LineItemsInput({
  allowUnitPriceOverride = true,
  canAdd = true,
  canDelete = true,
  onItemsChange,
  onValidationChange,
  initialItems = [],
  hideCurrency = false,
  currency: selectedCurrency,
  readonly = false,
  uomValueType = "uuid",
  isInventoryBased = true,
  withTaxes = true,
  title,
  description,
  calculateTaxOnUnitPrice = false,
  itemText = false,
  lineItemValueType = "base_uuid",
  itemOptionsLoader,
  itemSearchFn,
}: Props) {
  const [items, setItems] = useState<VendorLineItemData[]>(initialItems);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currency, setCurrency] = useState<Currency | null>(selectedCurrency ?? null);
  const isFirstRender = useRef(true);
  const prevIsInventoryBased = useRef(isInventoryBased);
  const [loadedOptions, setLoadedOptions] = useState<ComboboxOption[]>([]);

  useEffect(() => {
    if (selectedCurrency) setCurrency(selectedCurrency);
  }, [selectedCurrency]);

  useEffect(() => {
    if (itemOptionsLoader) {
      itemOptionsLoader()
        .then(setLoadedOptions)
        .catch(() => setLoadedOptions([]));
    }
  }, []);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (onItemsChange) {
      const cleaned = items.map(({item, ...rest}) => {
        if (isInventoryBased) {
          const {selected_uom_uuid, selected_uom_abbreviation, ...cleanedRest} = rest;
          return cleanedRest;
        }
        const {selected_uom_uuid, ...manualRest} = rest;
        return manualRest;
      });
      onItemsChange(cleaned);
    }
  }, [items, isInventoryBased]);

  useEffect(() => {
    if (prevIsInventoryBased.current === isInventoryBased) return;
    prevIsInventoryBased.current = isInventoryBased;
    setItems([]);
    setErrors({});
  }, [isInventoryBased]);

  const getDefaultUOM = useCallback((item: IInventoryItem) => {
    if (!item.inventory_item_units_of_measure?.length) return null;
    const baseUnit = item.inventory_item_units_of_measure.find(
      (uom) => uom.is_base_unit_of_measure,
    );
    return baseUnit ?? item.inventory_item_units_of_measure[0];
  }, []);

  const getBuyingPriceFromUOM = useCallback(
    (item: IInventoryItem, uomUuid?: string) => {
      if (!item.inventory_item_units_of_measure?.length) {
        return item.buying_price?.toString() ?? "0";
      }
      if (uomUuid) {
        const selectedUOM = item.inventory_item_units_of_measure.find(
          (uom) => uom.base_uuid === uomUuid,
        );
        if (selectedUOM) return selectedUOM.selling_price?.toString() ?? "0";
      }
      const defaultUOM = getDefaultUOM(item);
      return defaultUOM?.selling_price?.toString() ?? item.buying_price?.toString() ?? "0";
    },
    [getDefaultUOM],
  );

  const calculateLineTotal = useCallback((quantity: number, unitPrice: string): string => {
    const qty = Number(quantity) || 0;
    const price = parseFloat(unitPrice) || 0;
    return (qty * price).toFixed(2);
  }, []);

  const calculateUnitPriceWithTax = useCallback(
    async (
      originalPrice: string,
      base_uuid?: string,
    ): Promise<{amount: string; base_uuid: string; type: string}> => {
      if (!calculateTaxOnUnitPrice) {
        return {amount: originalPrice, base_uuid: "", type: ""};
      }
      try {
        const response = await INVOICES_API.previewTaxCalculation({
          amount: originalPrice,
          base_uuid,
          type: "purchase",
        });
        return {
          amount: response.gross_amount.toString(),
          base_uuid: base_uuid ?? "",
          type: "purchase",
        };
      } catch {
        return {amount: originalPrice, base_uuid: "", type: ""};
      }
    },
    [calculateTaxOnUnitPrice],
  );

  const updateItem = useCallback(
    (index: number, updatedFields: Partial<VendorLineItemData>) => {
      setItems((prev) => {
        const newItems = [...prev];
        const updatedItem = {...newItems[index], ...updatedFields};

        if (updatedFields.quantity !== undefined || updatedFields.unit_price !== undefined) {
          const priceForTotal = updatedItem.display_unit_price ?? updatedItem.unit_price;
          updatedItem.line_total = calculateLineTotal(updatedItem.quantity, priceForTotal);
        }

        newItems[index] = updatedItem;
        return newItems;
      });
    },
    [calculateLineTotal],
  );

  const validateItems = useCallback(() => {
    const newErrors: Record<string, string> = {};

    if (items.length === 0) {
      newErrors.line_items = "At least one line item is required";
    }

    items.forEach((item, index) => {
      if (isInventoryBased) {
        if (!item.line_item && !item.item_name) {
          newErrors[`line_item_${index}`] = "Item is required";
        }
      } else {
        if (!item.item_name || !item.item_name.trim()) {
          newErrors[`line_item_${index}`] = "Item description is required";
        }
        if (!item.selected_uom_abbreviation || !item.selected_uom_abbreviation.trim()) {
          newErrors[`uom_${index}`] = "Unit of measure is required";
        }
      }

      if (!item.quantity || item.quantity <= 0) {
        newErrors[`quantity_${index}`] = "Quantity must be greater than 0";
      }
      if (item.unit_price === undefined || parseFloat(item.unit_price) < 0) {
        newErrors[`unit_price_${index}`] = "Unit price must be 0 or greater";
      }
    });

    setErrors(newErrors);
    const isValid = Object.keys(newErrors).length === 0;
    onValidationChange?.(isValid);
    return isValid;
  }, [items, onValidationChange, isInventoryBased]);

  useEffect(() => {
    validateItems();
  }, [items, validateItems]);

  const handleUOMChange = useCallback(
    async (index: number, uomUuid: string) => {
      const item = items[index];
      if (!item.item) return;

      const selectedUOM = item.item.inventory_item_units_of_measure?.find(
        (uom) => uom.base_uuid === uomUuid,
      );

      if (selectedUOM) {
        const newPrice = selectedUOM.selling_price?.toString() ?? "0";
        const taxResponse = await calculateUnitPriceWithTax(newPrice, item.tax_base_uuid);

        updateItem(index, {
          selected_uom_uuid: uomUuid,
          unit_of_measure:
            uomValueType === "id" ? (selectedUOM.unit_of_measure?.id ?? null) : uomUuid,
          selected_uom_abbreviation:
            selectedUOM.unit_of_measure.unit_abbreviation || selectedUOM.unit_of_measure.unit_name,
          unit_price: newPrice,
          display_unit_price: taxResponse.amount,
          line_total: calculateLineTotal(items[index]?.quantity || 1, taxResponse.amount),
        });
      }
    },
    [items, updateItem, uomValueType, calculateUnitPriceWithTax],
  );

  const handleItemSelected = useCallback(
    async (index: number, item: IInventoryItem | null) => {
      if (!item) return;

      const defaultUOM = getDefaultUOM(item);
      const buyingPrice = getBuyingPriceFromUOM(item);

      const taxResponse = await calculateUnitPriceWithTax(buyingPrice, item.base_uuid);

      updateItem(index, {
        item,
        item_name: item.item_name,
        item_category: item.item_category?.id?.toString() ?? undefined,
        line_item:
          lineItemValueType === "id" ? (item.id ?? index + 1) : (item.base_uuid ?? index + 1),
        selected_uom_uuid: defaultUOM?.base_uuid,
        unit_of_measure:
          uomValueType === "id" ? (defaultUOM?.unit_of_measure?.id ?? null) : defaultUOM?.base_uuid,
        selected_uom_abbreviation:
          defaultUOM?.unit_of_measure.unit_abbreviation || defaultUOM?.unit_of_measure.unit_name,
        unit_price: buyingPrice,
        display_unit_price: taxResponse.amount,
        tax_base_uuid: taxResponse.base_uuid,
        tax_type: taxResponse.type,
        quantity: items[index]?.quantity || 1,
        line_total: calculateLineTotal(items[index]?.quantity || 1, taxResponse.amount),
      });
    },
    [
      getDefaultUOM,
      getBuyingPriceFromUOM,
      updateItem,
      calculateLineTotal,
      items,
      uomValueType,
      calculateUnitPriceWithTax,
    ],
  );
  const addItem = useCallback(() => {
    setItems((prev) => [
      ...prev,
      {
        type: "inventory",
        line_item: prev.length + 1,
        item_name: "",
        quantity: 1,
        unit_price: "0",
        line_total: "0",
      },
    ]);
  }, []);

  const removeItem = useCallback(
    (index: number) => {
      if (items.length === 1) return;
      setItems((prev) => prev.filter((_, i) => i !== index));
      setErrors((prev) => {
        const next = {...prev};
        delete next[`line_item_${index}`];
        delete next[`quantity_${index}`];
        delete next[`unit_price_${index}`];
        return next;
      });
    },
    [items.length],
  );

  const addTax = useCallback((index: number) => {
    setItems((prev) =>
      prev.map((item, i) =>
        i !== index
          ? item
          : {
              ...item,
              applicable_taxes: [...(item.applicable_taxes ?? []), {tax: 0, is_inclusive: false}],
            },
      ),
    );
  }, []);

  const removeTax = useCallback((itemIndex: number, taxIndex: number) => {
    setItems((prev) =>
      prev.map((item, i) =>
        i !== itemIndex
          ? item
          : {
              ...item,
              applicable_taxes: (item.applicable_taxes ?? []).filter((_, ti) => ti !== taxIndex),
            },
      ),
    );
  }, []);

  const updateTax = useCallback((itemIndex: number, taxIndex: number, field: string, val: any) => {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== itemIndex) return item;
        const taxes = (item.applicable_taxes ?? []).map((tax, ti) =>
          ti !== taxIndex ? tax : {...tax, [field]: val},
        );
        return {...item, applicable_taxes: taxes};
      }),
    );
  }, []);

  const grandTotal = useMemo(() => {
    return items.reduce((sum, item) => sum + (parseFloat(item.line_total) || 0), 0).toFixed(2);
  }, [items]);

  const validateQuantity = useCallback((index: number, value: number) => {
    if (value <= 0) {
      setErrors((prev) => ({...prev, [`quantity_${index}`]: "Quantity must be greater than 0"}));
      return false;
    }
    setErrors((prev) => {
      const n = {...prev};
      delete n[`quantity_${index}`];
      return n;
    });
    return true;
  }, []);

  const validateUnitPrice = useCallback((index: number, value: string) => {
    const price = parseFloat(value);
    if (isNaN(price) || price < 0) {
      setErrors((prev) => ({...prev, [`unit_price_${index}`]: "Unit price must be 0 or greater"}));
      return false;
    }
    setErrors((prev) => {
      const n = {...prev};
      delete n[`unit_price_${index}`];
      return n;
    });
    return true;
  }, []);

  return (
    <div className="space-y-4 mt-8">
      <div className="space-y-2">
        <h4 className="text-lg font-semibold text-gray-900">{title ?? "Line Items"}</h4>
        <p className="text-sm text-gray-600 leading-relaxed">
          {description ??
            "Add the products or services being ordered, including quantities and unit prices."}
        </p>
      </div>

      <div className="rounded-md border overflow-visible">
        <Table className="overflow-visible">
          <TableHeader>
            <TableRow className="text-base text-slate-800 hover:bg-background">
              <TableHead className="w-12">#</TableHead>
              {!itemText && <TableHead className="w-36">Type</TableHead>}
              <TableHead className="min-w-[250px]">Item Description</TableHead>
              <TableHead className="w-40">Unit of Measure</TableHead>
              <TableHead className="w-32">Qty</TableHead>
              <TableHead className="w-36 text-right">
                Unit Price
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">({currency.code})</span>
                )}
              </TableHead>
              <TableHead className="w-36 text-right">
                Total Amount
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">({currency.code})</span>
                )}
              </TableHead>
              {canDelete && !readonly && <TableHead className={withTaxes ? "w-24" : "w-12"} />}
            </TableRow>
          </TableHeader>

          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={isInventoryBased ? (canDelete ? 7 : 6) : canDelete ? 6 : 5}
                  className="text-center text-muted-foreground py-8"
                >
                  No items added. Click &quot;Add Row&quot; to get started.
                </TableCell>
              </TableRow>
            ) : (
              items.map((entry, index) => (
                <React.Fragment key={index}>
                  <TableRow key={index} className="hover:bg-muted/50">
                    <TableCell className="font-medium text-muted-foreground">{index + 1}</TableCell>
                    {/* Type selector */}
                    {!itemText && (
                      <TableCell>
                        <Select
                          value={entry.type}
                          onValueChange={(value) =>
                            updateItem(index, {
                              type: value as VendorLineItemType,
                              line_item: index + 1,
                              item_name: "",
                              unit_price: "0",
                              line_total: "0",
                              selected_uom_uuid: undefined,
                              selected_uom_abbreviation: undefined,
                              asset_category: undefined,
                              item: undefined,
                            })
                          }
                          disabled={readonly}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="inventory">Inventory</SelectItem>
                            <SelectItem value="other">Other</SelectItem>
                            <SelectItem value="fixed_asset">Fixed Asset</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                    )}

                    {/* Item selector */}
                    <TableCell className="overflow-visible">
                      <div className="space-y-1">
                        {itemText ? (
                          <SearchableComboboxInput
                            value={entry.item_name}
                            onChange={(value) =>
                              updateItem(index, {item_name: value, line_item: index + 1})
                            }
                            disabled={readonly}
                            placeholder="Search or enter item description"
                            onSearch={itemSearchFn ?? (() => Promise.resolve([]))}
                          />
                        ) : entry.type === "inventory" ? (
                          <PaginatedSearchableSelect<IInventoryItem>
                            fetchFirstPage={INVENTORY_ITEMS_API.fetchInventoryItems}
                            fetchFromUrl={INVENTORY_ITEMS_API.fetchInventoryItemsFromUrl}
                            placeholder="Select item"
                            searchPlaceholder="Search items..."
                            emptyMessage="No items found"
                            idKey="id"
                            valueKey="id"
                            labelKeyFn={(item) => item.item_name}
                            labelDescKeyFn={(item) =>
                              `${item.item_code} · ${item.quantity_on_hand} on hand`
                            }
                            value={entry.item?.id || undefined}
                            initialData={entry.item ? [entry.item] : []}
                            onValueChange={() => {}}
                            onItemSelected={(item) => handleItemSelected(index, item)}
                            disabled={readonly}
                          />
                        ) : entry.type === "fixed_asset" ? (
                          <div className="flex items-center gap-2">
                            <Input
                              placeholder="Asset name"
                              value={entry.item_name}
                              onChange={(e) =>
                                updateItem(index, {
                                  item_name: e.target.value,
                                  line_item: e.target.value,
                                })
                              }
                              disabled={readonly}
                              className="flex-1"
                            />
                            <div className="flex-1">
                              <PaginatedSearchableSelect<IAssetCategory>
                                fetchFirstPage={ASSET_CATEGORIES_API.fetchAssetCategories}
                                fetchFromUrl={ASSET_CATEGORIES_API.fetchAssetCategoriesFromUrl}
                                idKey="base_uuid"
                                valueKey="base_uuid"
                                labelKey="category_name"
                                labelDescKey="category_description"
                                placeholder="Select category"
                                searchPlaceholder="Search categories..."
                                emptyMessage="No categories found"
                                value={entry.asset_category}
                                initialData={
                                  entry.asset_category
                                    ? [
                                        {
                                          base_uuid: entry.asset_category,
                                          category_name: entry.asset_category_name ?? "",
                                        } as any,
                                      ]
                                    : []
                                }
                                onValueChange={() => {}}
                                onItemSelected={(cat) =>
                                  updateItem(index, {
                                    asset_category: cat?.base_uuid,
                                    asset_category_name: cat?.category_name,
                                  })
                                }
                                disabled={readonly}
                              />
                            </div>
                          </div>
                        ) : (
                          <Input
                            placeholder="Enter item description"
                            value={entry.item_name}
                            onChange={(e) =>
                              updateItem(index, {item_name: e.target.value, line_item: index + 1})
                            }
                            disabled={readonly}
                          />
                        )}
                        {errors[`line_item_${index}`] && (
                          <p className="text-xs text-red-600">{errors[`line_item_${index}`]}</p>
                        )}
                      </div>
                    </TableCell>

                    {/* UOM selector */}
                    <TableCell>
                      <div className="space-y-1">
                        {itemText ? (
                          <Input
                            placeholder="e.g., pcs, kg"
                            value={entry.selected_uom_abbreviation || ""}
                            onChange={(e) =>
                              updateItem(index, {selected_uom_abbreviation: e.target.value})
                            }
                            disabled={readonly}
                          />
                        ) : isInventoryBased && entry.type === "inventory" ? (
                          entry.item?.inventory_item_units_of_measure?.length ? (
                            <Select
                              value={
                                entry.selected_uom_uuid || getDefaultUOM(entry.item)?.base_uuid
                              }
                              onValueChange={(value) => handleUOMChange(index, value)}
                              disabled={readonly}
                            >
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select UOM" />
                              </SelectTrigger>
                              <SelectContent>
                                {entry.item.inventory_item_units_of_measure.map((uom) => (
                                  <SelectItem key={uom.base_uuid} value={uom.base_uuid}>
                                    {uom.unit_of_measure.unit_abbreviation ||
                                      uom.unit_of_measure.unit_name}
                                    {uom.is_base_unit_of_measure && " (Base)"}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : entry.item ? (
                            <span className="text-sm text-muted-foreground">No UOM</span>
                          ) : (
                            <span className="text-sm text-muted-foreground">-</span>
                          )
                        ) : (
                          <>
                            <Input
                              placeholder="e.g., pcs, kg"
                              value={entry.selected_uom_abbreviation || ""}
                              onChange={(e) =>
                                updateItem(index, {selected_uom_abbreviation: e.target.value})
                              }
                              disabled={readonly}
                              className={errors[`uom_${index}`] ? "border-red-500" : ""}
                            />
                            {errors[`uom_${index}`] && (
                              <p className="text-xs text-red-600">{errors[`uom_${index}`]}</p>
                            )}
                          </>
                        )}
                      </div>
                    </TableCell>
                    {/* Quantity */}
                    <TableCell>
                      <div className="space-y-1">
                        <Input
                          required
                          type="number"
                          min="1"
                          step="1"
                          placeholder="0"
                          className="text-right"
                          value={entry.quantity}
                          onChange={(e) => {
                            const value = parseInt(e.target.value) || 0;
                            validateQuantity(index, value);
                            updateItem(index, {quantity: value});
                          }}
                          disabled={readonly}
                        />
                        {errors[`quantity_${index}`] && (
                          <p className="text-xs text-red-600">{errors[`quantity_${index}`]}</p>
                        )}
                      </div>
                    </TableCell>

                    {/* Unit Price */}
                    <TableCell>
                      <div className="space-y-1">
                        <FormattedNumberInput
                          value={entry.display_unit_price ?? entry.unit_price}
                          onValueChange={(value) => {
                            const stringValue = value?.toString() ?? "";
                            validateUnitPrice(index, stringValue);
                            updateItem(index, {unit_price: stringValue || "0"});
                          }}
                          disabled={readonly || (!allowUnitPriceOverride && !!entry.item)}
                          className="text-right"
                        />
                        {errors[`unit_price_${index}`] && (
                          <p className="text-xs text-red-600">{errors[`unit_price_${index}`]}</p>
                        )}
                      </div>
                    </TableCell>

                    {/* Line Total */}
                    <TableCell className="text-right font-medium">
                      {formatCurrency(entry.line_total)}
                    </TableCell>

                    {/* Remove */}
                    {canDelete && !readonly && (
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {withTaxes && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => addTax(index)}
                              className="h-8 px-2 text-xs text-muted-foreground hover:text-primary hover:bg-muted gap-1"
                            >
                              <Icon icon="hugeicons:plus-sign" className="w-3 h-3" />
                              Tax
                            </Button>
                          )}
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeItem(index)}
                            className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                            disabled={items.length === 1}
                          >
                            <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>

                  {/* Tax rows - only when withTaxes */}
                  {withTaxes &&
                    (entry.applicable_taxes ?? []).map((tax, taxIndex) => (
                      <TableRow key={`tax-${index}-${taxIndex}`} className="hover:bg-transparent">
                        <TableCell />
                        {/* spans: */}
                        <TableCell colSpan={4} className="py-1">
                          <div className="ml-6 flex items-center gap-3 bg-muted/40 rounded-lg px-3 py-2 border-l-2 border-primary/30">
                            <div className="flex-1">
                              <PaginatedSearchableSelect
                                placeholder="Select tax"
                                searchPlaceholder="Search taxes..."
                                emptyMessage="No taxes found"
                                fetchFirstPage={TAXES_API.fetchTaxes}
                                fetchFromUrl={TAXES_API.fetchTaxesFromUrl}
                                idKey="base_uuid"
                                valueKey="base_uuid"
                                onValueChange={(list) =>
                                  updateTax(index, taxIndex, "tax", list[0] || 0)
                                }
                              />
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <span className="text-xs text-muted-foreground whitespace-nowrap">
                                Inclusive
                              </span>
                              <Switch
                                checked={tax.is_inclusive}
                                onCheckedChange={(checked) =>
                                  updateTax(index, taxIndex, "is_inclusive", checked)
                                }
                              />
                            </div>
                          </div>
                        </TableCell>
                        {/* Total col - empty */}
                        <TableCell />
                        {/* Actions col */}
                        <TableCell className="py-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeTax(index, taxIndex)}
                            className="h-8 w-8 text-red-500 hover:text-red-500 hover:bg-red-50"
                          >
                            <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                </React.Fragment>
              ))
            )}
          </TableBody>

          <TableFooter>
            <TableRow>
              <TableCell colSpan={3}>
                {canAdd && !readonly && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addItem}
                    className="flex items-center gap-2"
                  >
                    <Icon icon="hugeicons:plus-sign" className="h-4 w-4" />
                    Add Row
                  </Button>
                )}
              </TableCell>
              <TableCell colSpan={3} className="text-right text-base font-semibold">
                Grand Total
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">({currency.code})</span>
                )}
              </TableCell>
              <TableCell className="text-right text-base font-bold">
                {formatCurrency(grandTotal)}
              </TableCell>
              {canDelete && !readonly && <TableCell />}
            </TableRow>
          </TableFooter>
        </Table>
      </div>
    </div>
  );
}
