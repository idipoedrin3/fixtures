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
import {Input} from "@/components/ui/input";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import {formatCurrency} from "#/_lib/utils";
import {Currency, IAssetCategory} from "#/_types/api.types";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {ASSET_CATEGORIES_API} from "#/_api/api.helpers";
import {TAXES_API} from "#/_api/api.helpers";
import {Switch} from "@/components/ui/switch";
import React from "react";

export type FixedAssetLineItem = {
  line_item: string;
  asset_category?: number | string;
  unit_of_measure?: string;
  quantity: number;
  unit_price: string;
  line_total?: string;
  applicable_taxes?: {tax: number; is_inclusive: boolean}[];
};

interface FixedAssetLineItemData extends FixedAssetLineItem {
  categoryData?: IAssetCategory;
  category_name?: string;
}

type Props = {
  onItemsChange?: (items: FixedAssetLineItem[]) => void;
  onValidationChange?: (isValid: boolean) => void;
  initialItems?: FixedAssetLineItemData[];
  currency?: Currency | null;
  hideCurrency?: boolean;
  readonly?: boolean;
  canAdd?: boolean;
  canDelete?: boolean;
  showUnitOfMeasure?: boolean;
  withTaxes?: boolean;
};

export default function FixedAssetLineItemsInput({
  onItemsChange,
  onValidationChange,
  initialItems = [],
  currency,
  hideCurrency = false,
  readonly = false,
  canAdd = true,
  canDelete = true,
  showUnitOfMeasure = false,
  withTaxes = false,
}: Props) {
  const [items, setItems] = useState<FixedAssetLineItemData[]>(initialItems);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const prevItems = useRef(items);

  useEffect(() => {
    if (prevItems.current === items) return;
    prevItems.current = items;
    if (onItemsChange) {
      const cleaned = items.map(({categoryData, category_name, ...rest}) => rest);
      onItemsChange(cleaned);
    }
  }, [items]);

  const calculateLineTotal = useCallback((quantity: number, unitPrice: string): string => {
    const qty = Number(quantity) || 0;
    const price = parseFloat(unitPrice.replace(/,/g, "")) || 0;
    return (qty * price).toFixed(2);
  }, []);

  const updateItem = useCallback(
    (index: number, updatedFields: Partial<FixedAssetLineItemData>) => {
      setItems((prev) => {
        const newItems = [...prev];
        const updatedItem = {...newItems[index], ...updatedFields};

        if (updatedFields.quantity !== undefined || updatedFields.unit_price !== undefined) {
          updatedItem.line_total = calculateLineTotal(updatedItem.quantity, updatedItem.unit_price);
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
      newErrors.line_items = "At least one fixed asset line item is required";
    }

    items.forEach((item, index) => {
      if (!item.line_item || !item.line_item.trim()) {
        newErrors[`line_item_${index}`] = "Asset name is required";
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
  }, [items, onValidationChange]);

  useEffect(() => {
    validateItems();
  }, [items]);

  const addItem = useCallback(() => {
    setItems((prev) => [...prev, {line_item: "", quantity: 1, unit_price: "0", line_total: "0"}]);
  }, []);

  const removeItem = useCallback((index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
    setErrors((prev) => {
      const next = {...prev};
      delete next[`line_item_${index}`];
      delete next[`quantity_${index}`];
      delete next[`unit_price_${index}`];
      return next;
    });
  }, []);

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
    return items
      .reduce((sum, item) => {
        const price = parseFloat((item.unit_price ?? "0").toString().replace(/,/g, "")) || 0;
        const qty = Number(item.quantity) || 0;
        return sum + qty * price;
      }, 0)
      .toFixed(2);
  }, [items]);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h4 className="text-lg font-semibold text-gray-900">Fixed Asset Line Items</h4>
        <p className="text-sm text-gray-600 leading-relaxed">
          Add fixed assets being purchased, including asset categories, quantities and prices.
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow className="text-base text-slate-800 hover:bg-background">
              <TableHead className="w-12">#</TableHead>
              <TableHead className="min-w-[250px]">Asset Name *</TableHead>
              <TableHead className="min-w-[200px]">Asset Category</TableHead>
              {showUnitOfMeasure && <TableHead className="w-36">Unit of Measure</TableHead>}
              <TableHead className="w-32">Qty *</TableHead>
              <TableHead className="w-36 text-right">
                Unit Price *
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
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No fixed assets added. Click &quot;Add Row&quot; to get started.
                </TableCell>
              </TableRow>
            ) : (
              items.map((entry, index) => (
                <React.Fragment key={index}>
                  <TableRow className="hover:bg-muted/50">
                    <TableCell className="font-medium text-muted-foreground">{index + 1}</TableCell>

                    {/* Asset Description */}
                    <TableCell>
                      <div className="space-y-1">
                        <Input
                          placeholder="Enter asset name"
                          value={entry.line_item}
                          onChange={(e) => updateItem(index, {line_item: e.target.value})}
                          disabled={readonly}
                          className={errors[`line_item_${index}`] ? "border-red-500" : ""}
                        />
                        {errors[`line_item_${index}`] && (
                          <p className="text-xs text-red-600">{errors[`line_item_${index}`]}</p>
                        )}
                      </div>
                    </TableCell>

                    {/* Asset Category */}
                    <TableCell>
                      <PaginatedSearchableSelect
                        fetchFirstPage={ASSET_CATEGORIES_API.fetchAssetCategories}
                        fetchFromUrl={ASSET_CATEGORIES_API.fetchAssetCategoriesFromUrl}
                        idKey="base_uuid"
                        valueKey="base_uuid"
                        labelKey="reference_code"
                        labelDescKey="category_description"
                        placeholder="Select category (optional)"
                        searchPlaceholder="Search categories..."
                        emptyMessage="No categories found"
                        value={entry.asset_category}
                        initialData={entry.categoryData ? [entry.categoryData] : []}
                        onValueChange={() => {}}
                        onItemSelected={(category) => {
                          if (category) {
                            updateItem(index, {
                              asset_category: category.base_uuid,
                              category_name: category.category_name,
                              categoryData: category,
                            });
                          } else {
                            updateItem(index, {
                              asset_category: undefined,
                              category_name: undefined,
                              categoryData: undefined,
                            });
                          }
                        }}
                        disabled={readonly}
                      />
                    </TableCell>

                    {showUnitOfMeasure && (
                      <TableCell>
                        <Input
                          placeholder="e.g. pcs, kg"
                          value={entry.unit_of_measure || ""}
                          onChange={(e) => updateItem(index, {unit_of_measure: e.target.value})}
                          disabled={readonly}
                        />
                      </TableCell>
                    )}

                    {/* Quantity */}
                    <TableCell>
                      <div className="space-y-1">
                        <Input
                          type="number"
                          min="1"
                          step="1"
                          placeholder="0"
                          className="text-right"
                          value={entry.quantity}
                          onChange={(e) =>
                            updateItem(index, {quantity: parseInt(e.target.value) || 0})
                          }
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
                          value={entry.unit_price}
                          onValueChange={(value) =>
                            updateItem(index, {
                              unit_price: value.toString().replace(/,/g, "") || "0",
                            })
                          }
                          disabled={readonly}
                          className="text-right"
                        />
                        {errors[`unit_price_${index}`] && (
                          <p className="text-xs text-red-600">{errors[`unit_price_${index}`]}</p>
                        )}
                      </div>
                    </TableCell>

                    {/* Line Total */}
                    <TableCell className="text-right font-medium">
                      {formatCurrency(
                        (
                          Number(entry.quantity) *
                          parseFloat((entry.unit_price ?? "0").toString().replace(/,/g, ""))
                        ).toFixed(2),
                      )}
                    </TableCell>

                    {/* Tax + Delete */}
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
                          >
                            <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>

                  {/* Tax sub-rows */}
                  {withTaxes &&
                    (entry.applicable_taxes ?? []).map((tax, taxIndex) => (
                      <TableRow key={`tax-${index}-${taxIndex}`} className="hover:bg-transparent">
                        <TableCell />
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
                                labelKey="tax_name"
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
                        <TableCell />
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
              <TableCell colSpan={2} className="text-right text-base font-semibold">
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
