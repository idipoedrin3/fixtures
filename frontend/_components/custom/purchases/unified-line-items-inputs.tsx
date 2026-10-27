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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {Switch} from "@/components/ui/switch";
import {formatCurrency} from "#/_lib/utils";
import {Currency, IAccount, IAssetCategory, IInventoryItem} from "#/_types/api.types";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {
  ACCOUNTS_API,
  ASSET_CATEGORIES_API,
  INVENTORY_ITEMS_API,
  INVOICES_API,
  TAXES_API,
} from "#/_api/api.helpers";
import React from "react";
import {InventoryItemCreatePanel} from "#/(dashboard)/inventory-items/_components/inventory-item-create-panel";
import {
  CURRENCY_CONVERSION_API,
  IExchangeRateInput,
} from "#/_api/services/system.service";

export type UnifiedLineItemType = "inventory" | "service" | "other" | "fixed_asset" | "other_expense";

type UnifiedInventoryItem = {
  id?: number;
  base_uuid?: string;
  item_name: string;
  item_category?: IInventoryItem["item_category"];
  buying_price?: IInventoryItem["buying_price"];
  inventory_item_units_of_measure?: Array<{
    id?: number;
    base_uuid: string;
    is_base_unit_of_measure?: boolean;
    selling_price?: number | string | null;
    unit_of_measure: {
      id?: number;
      base_uuid?: string;
      unit_name: string;
      unit_abbreviation?: string;
    };
  }>;
};

export type UnifiedLineItem = {
  type: UnifiedLineItemType;
  purchase_order_line_item_uuid?: string;
  item?: UnifiedInventoryItem;
  line_item: number | string;
  item_name: string;
  item_category?: string;
  quantity: number;
  unit_price: string;
  net_unit_price?: string;
  tax_unit_price?: string;
  display_unit_price?: string;
  line_total: string;
  selected_uom_uuid?: string;
  selected_uom_abbreviation?: string;
  unit_of_measure?: string | number | null;
  asset_category?: string;
  tax_base_uuid?: string;
  tax_type?: string;
  applicable_taxes?: {tax: string | number; is_inclusive: boolean}[];
  expense_name?: string;
  account_to_record_expense?: string;
};

interface UnifiedLineItemData extends UnifiedLineItem {
  categoryData?: IAssetCategory;
}

type Props = {
  initialItems?: UnifiedLineItemData[];
  onItemsChange?: (items: UnifiedLineItem[]) => void;
  currency?: Currency | null;
  previewCurrency?: Currency | null;
  exchangeRate?: IExchangeRateInput | null;
  hideCurrency?: boolean;
  readonly?: boolean;
  canAdd?: boolean;
  canDelete?: boolean;
  allowUnitPriceOverride?: boolean;
  calculateTaxOnUnitPrice?: boolean;
  withTaxes?: boolean;
  taxEnabledTypes?: UnifiedLineItemType[];
  taxLayout?: "rows" | "inline";
  showPricingPreview?: boolean;
  object_uuid?: string;
  model_name?: string;
  allowedTypes?: UnifiedLineItemType[];
  lineItemErrors?: Record<string, string>;
};

export default function UnifiedLineItemsInput({
  initialItems = [],
  onItemsChange,
  currency,
  previewCurrency,
  exchangeRate,
  hideCurrency = false,
  readonly = false,
  canAdd = true,
  canDelete = true,
  allowUnitPriceOverride = true,
  calculateTaxOnUnitPrice = false,
  withTaxes = false,
  taxEnabledTypes = ["inventory", "other", "fixed_asset", "other_expense"],
  taxLayout = "rows",
  showPricingPreview = false,
  allowedTypes = ["inventory", "other", "fixed_asset", "other_expense"],
  lineItemErrors = {},
}: Props) {
  const [items, setItems] = useState<UnifiedLineItemData[]>(initialItems);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [inventoryItemCreationIndex, setInventoryItemCreationIndex] = useState<number | null>(null);
  const taxCache = useRef<Map<string, {netAmount: string; taxAmount: string; grossAmount: string}>>(
    new Map(),
  );
  const isFirstRender = useRef(true);
  const pricingRequestVersion = useRef<Record<number, number>>({});
  const [previewMultiplier, setPreviewMultiplier] = useState(1);
  const [previewError, setPreviewError] = useState<string>();

  const showCurrencyPreview =
    !!currency && !!previewCurrency && currency.code !== previewCurrency.code;

  const tableColumnCount =
    7 +
    (canDelete && !readonly ? 1 : 0) +
    (showPricingPreview ? 2 : 0) +
    (showCurrencyPreview ? 1 : 0) +
    (withTaxes && taxLayout === "inline" ? 1 : 0);

  const previewFractionDigits = Math.min(
    Math.max(Number(previewCurrency?.decimal_places ?? previewCurrency?.decimail_places ?? 2), 0),
    20,
  );

  useEffect(() => {
    if (!showCurrencyPreview || !previewCurrency) {
      setPreviewMultiplier(1);
      setPreviewError(undefined);
      return;
    }

    let cancelled = false;

    const fetchPreviewMultiplier = async () => {
      try {
        const result = await CURRENCY_CONVERSION_API.post({
          amount: "1",
          currency: currency!.id.toString(),
          target_currency: previewCurrency.id.toString(),
          ...(exchangeRate ? {exchange_rate: exchangeRate} : {}),
        });

        if (!cancelled) {
          setPreviewMultiplier(Number(result.converted_amount));
          setPreviewError(undefined);
        }
      } catch {
        if (!cancelled) {
          setPreviewMultiplier(0);
          setPreviewError(`A valid ${previewCurrency.code} exchange rate is required.`);
        }
      }
    };

    void fetchPreviewMultiplier();

    return () => {
      cancelled = true;
    };
  }, [exchangeRate, previewCurrency, showCurrencyPreview]);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (onItemsChange) {
      const cleaned = items.map(({item, categoryData, ...rest}) => rest);
      onItemsChange(cleaned);
    }
  }, [items]);

  const calculateLineTotal = useCallback((quantity: number, unitPrice: string): string => {
    const qty = Number(quantity) || 0;
    const price = parseFloat(unitPrice) || 0;
    return (qty * price).toFixed(2);
  }, []);

  const convertBasePriceToDocumentPrice = useCallback(
    (basePrice: string) => {
      if (!showCurrencyPreview) return basePrice;
      if (previewMultiplier <= 0) return "0";

      return (Number(basePrice) / previewMultiplier).toString();
    },
    [previewMultiplier, showCurrencyPreview],
  );

  const calculateUnitPriceWithTax = useCallback(
    async (
      originalPrice: string,
      base_uuid?: string,
      applicableTaxes: UnifiedLineItem["applicable_taxes"] = [],
    ) => {
      const selectedTaxes = applicableTaxes.filter((tax) => !!tax.tax);

      if (!calculateTaxOnUnitPrice && selectedTaxes.length === 0) {
        return {
          netAmount: originalPrice,
          taxAmount: "0",
          grossAmount: originalPrice,
          base_uuid: "",
          type: "",
        };
      }

      const cleanAmount = parseFloat(originalPrice).toFixed(2);
      const taxKey = selectedTaxes
        .map((tax) => `${tax.tax}:${tax.is_inclusive}`)
        .sort()
        .join(",");
      const cacheKey = `${base_uuid ?? "manual"}::${cleanAmount}::${taxKey}`;

      if (taxCache.current.has(cacheKey)) {
        const cached = taxCache.current.get(cacheKey)!;
        return {
          ...cached,
          base_uuid: base_uuid ?? "",
          type: base_uuid ? "purchase" : "",
        };
      }

      try {
        const response = await INVOICES_API.previewTaxCalculation({
          amount: cleanAmount,
          ...(selectedTaxes.length > 0
            ? {applicable_taxes: selectedTaxes}
            : base_uuid
              ? {base_uuid, type: "purchase"}
              : {applicable_taxes: []}),
        });
        const preview = {
          netAmount: response.net_amount.toString(),
          taxAmount: response.tax_amount.toString(),
          grossAmount: response.gross_amount.toString(),
        };
        taxCache.current.set(cacheKey, preview);
        return {
          ...preview,
          base_uuid: base_uuid ?? "",
          type: base_uuid ? "purchase" : "",
        };
      } catch {
        return {
          netAmount: originalPrice,
          taxAmount: "0",
          grossAmount: originalPrice,
          base_uuid: "",
          type: "",
        };
      }
    },
    [calculateTaxOnUnitPrice],
  );

  const updateItem = useCallback(
    (index: number, updatedFields: Partial<UnifiedLineItemData>) => {
      setItems((prev) => {
        const newItems = [...prev];
        const updatedItem = {...newItems[index], ...updatedFields};

        if (
          updatedFields.quantity !== undefined ||
          updatedFields.unit_price !== undefined ||
          updatedFields.display_unit_price !== undefined ||
          updatedFields.net_unit_price !== undefined ||
          updatedFields.tax_unit_price !== undefined
        ) {
          updatedItem.line_total = calculateLineTotal(
            updatedItem.quantity,
            updatedItem.display_unit_price ?? updatedItem.unit_price,
          );
        }

        newItems[index] = updatedItem;
        return newItems;
      });
    },
    [calculateLineTotal],
  );

  const getDefaultUOM = useCallback((item: UnifiedInventoryItem) => {
    if (!item.inventory_item_units_of_measure?.length) return null;
    return (
      item.inventory_item_units_of_measure.find((u) => u.is_base_unit_of_measure) ??
      item.inventory_item_units_of_measure[0]
    );
  }, []);

  const handleItemSelected = useCallback(
    async (index: number, item: IInventoryItem | null) => {
      if (!item) return;
      const defaultUOM = getDefaultUOM(item);
      const baseBuyingPrice =
        defaultUOM?.selling_price?.toString() ?? item.buying_price?.toString() ?? "0";
      const buyingPrice = convertBasePriceToDocumentPrice(baseBuyingPrice);

      const taxResponse = await calculateUnitPriceWithTax(buyingPrice, item.base_uuid);

      updateItem(index, {
        item,
        item_name: item.item_name,
        item_category: item.item_category?.id?.toString() ?? undefined,
        line_item: item.base_uuid ?? index + 1,
        selected_uom_uuid: defaultUOM?.base_uuid,
        unit_of_measure: defaultUOM?.base_uuid,
        selected_uom_abbreviation:
          defaultUOM?.unit_of_measure.unit_abbreviation || defaultUOM?.unit_of_measure.unit_name,
        unit_price: buyingPrice,
        net_unit_price: taxResponse.netAmount,
        tax_unit_price: taxResponse.taxAmount,
        display_unit_price: taxResponse.grossAmount,
        tax_base_uuid: taxResponse.base_uuid || undefined,
        tax_type: taxResponse.type || undefined,
        quantity: items[index]?.quantity || 1,
        line_total: calculateLineTotal(items[index]?.quantity || 1, taxResponse.grossAmount),
      });
    },
    [
      getDefaultUOM,
      calculateUnitPriceWithTax,
      convertBasePriceToDocumentPrice,
      updateItem,
      calculateLineTotal,
      items,
    ],
  );

  const handleUOMChange = useCallback(
    async (index: number, uomUuid: string) => {
      const item = items[index];
      if (!item.item) return;
      const selectedUOM = item.item.inventory_item_units_of_measure?.find(
        (u) => u.base_uuid === uomUuid,
      );
      if (!selectedUOM) return;

      const basePrice = selectedUOM.selling_price?.toString() ?? "0";
      const newPrice = convertBasePriceToDocumentPrice(basePrice);
      const taxResponse = await calculateUnitPriceWithTax(newPrice, item.tax_base_uuid);

      updateItem(index, {
        selected_uom_uuid: uomUuid,
        unit_of_measure: uomUuid,
        selected_uom_abbreviation:
          selectedUOM.unit_of_measure.unit_abbreviation || selectedUOM.unit_of_measure.unit_name,
        unit_price: newPrice,
        net_unit_price: taxResponse.netAmount,
        tax_unit_price: taxResponse.taxAmount,
        display_unit_price: taxResponse.grossAmount,
        line_total: calculateLineTotal(item.quantity, taxResponse.grossAmount),
      });
    },
    [
      items,
      calculateUnitPriceWithTax,
      convertBasePriceToDocumentPrice,
      updateItem,
      calculateLineTotal,
    ],
  );

  const handleTypeChange = useCallback((index: number, type: UnifiedLineItemType) => {
    setItems((prev) => {
      const newItems = [...prev];
      newItems[index] = {
        type,
        line_item: index + 1,
        item_name: "",
        quantity: 1,
        unit_price: "0",
        net_unit_price: "0",
        tax_unit_price: "0",
        display_unit_price: "0",
        line_total: "0",
        applicable_taxes: [],
        expense_name: undefined,
        account_to_record_expense: undefined,
      };
      return newItems;
    });
  }, []);

  const addItem = useCallback(() => {
    setItems((prev) => [
      ...prev,
      {
        type: "inventory",
        line_item: prev.length + 1,
        item_name: "",
        quantity: 1,
        unit_price: "0",
        net_unit_price: "0",
        tax_unit_price: "0",
        display_unit_price: "0",
        line_total: "0",
        applicable_taxes: [],
      },
    ]);
  }, []);

  const removeItem = useCallback(
    (index: number) => {
      if (items.length === 1) return;
      setItems((prev) => prev.filter((_, i) => i !== index));
    },
    [items.length],
  );

  // Tax handlers
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

  const applyPricingPreview = useCallback(
    async (
      index: number,
      unitPrice: string,
      applicableTaxes: UnifiedLineItem["applicable_taxes"] = [],
    ) => {
      const entry = items[index];
      if (!entry) return;

      const requestVersion = (pricingRequestVersion.current[index] ?? 0) + 1;
      pricingRequestVersion.current[index] = requestVersion;

      const preview = await calculateUnitPriceWithTax(
        unitPrice,
        entry.type === "inventory" || entry.type === "service"
          ? entry.tax_base_uuid || entry.item?.base_uuid
          : undefined,
        entry.type === "inventory" || entry.type === "service" ? [] : applicableTaxes,
      );

      if (pricingRequestVersion.current[index] !== requestVersion) return;

      updateItem(index, {
        net_unit_price: preview.netAmount,
        tax_unit_price: preview.taxAmount,
        display_unit_price: preview.grossAmount,
        tax_base_uuid: preview.base_uuid || entry.tax_base_uuid,
        tax_type: preview.type || entry.tax_type,
      });
    },
    [calculateUnitPriceWithTax, items, updateItem],
  );

  const handleUnitPriceChange = useCallback(
    (index: number, value: number | null) => {
      const unitPrice = (value ?? 0).toString();

      updateItem(index, {
        unit_price: unitPrice,
        net_unit_price: unitPrice,
        tax_unit_price: "0",
        display_unit_price: unitPrice,
      });

      void applyPricingPreview(index, unitPrice, items[index]?.applicable_taxes ?? []);
    },
    [applyPricingPreview, items, updateItem],
  );

  const handleBaseUnitPriceChange = useCallback(
    (index: number, value: number | null) => {
      if (previewMultiplier <= 0) return;

      const documentPrice = (value ?? 0) / previewMultiplier;
      handleUnitPriceChange(index, documentPrice);
    },
    [handleUnitPriceChange, previewMultiplier],
  );

  const removeTax = useCallback(
    (itemIndex: number, taxIndex: number) => {
      const entry = items[itemIndex];
      if (!entry) return;

      const applicableTaxes = (entry.applicable_taxes ?? []).filter(
        (_, index) => index !== taxIndex,
      );

      updateItem(itemIndex, {applicable_taxes: applicableTaxes});
      void applyPricingPreview(itemIndex, entry.unit_price, applicableTaxes);
    },
    [applyPricingPreview, items, updateItem],
  );

  const updateTax = useCallback(
    (itemIndex: number, taxIndex: number, field: string, val: any) => {
      const entry = items[itemIndex];
      if (!entry) return;

      const applicableTaxes = (entry.applicable_taxes ?? []).map((tax, index) =>
        index === taxIndex ? {...tax, [field]: val} : tax,
      );

      updateItem(itemIndex, {applicable_taxes: applicableTaxes});
      void applyPricingPreview(itemIndex, entry.unit_price, applicableTaxes);
    },
    [applyPricingPreview, items, updateItem],
  );

  const pricingTotals = useMemo(() => {
    return items.reduce(
      (totals, item) => {
        const quantity = Number(item.quantity) || 0;

        totals.net += quantity * (parseFloat(item.net_unit_price ?? item.unit_price) || 0);
        totals.tax += quantity * (parseFloat(item.tax_unit_price ?? "0") || 0);
        totals.gross += quantity * (parseFloat(item.display_unit_price ?? item.unit_price) || 0);

        return totals;
      },
      {net: 0, tax: 0, gross: 0},
    );
  }, [items]);

  const grandTotal = pricingTotals.gross.toFixed(2);

  const canApplyTaxes = useCallback(
    (type: UnifiedLineItemType) => withTaxes && taxEnabledTypes.includes(type),
    [taxEnabledTypes, withTaxes],
  );

  const hasAnyTaxes = useMemo(
    () => items.some((item) => (item.applicable_taxes ?? []).length > 0),
    [items],
  );

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h4 className="text-lg font-semibold text-gray-900">Line Items</h4>
        <p className="text-sm text-gray-600">
          Add items being ordered. Select the type for each row.
        </p>
        <p className="text-xs text-muted-foreground lg:hidden">
          Scroll horizontally to view all pricing and tax details.
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border bg-background">
        <Table
          className={
            showPricingPreview && withTaxes && taxLayout === "inline"
              ? hasAnyTaxes
                ? "min-w-[1800px]"
                : "min-w-[1600px]"
              : showPricingPreview
                ? "min-w-[1380px]"
                : showCurrencyPreview
                  ? "min-w-[1140px]"
                  : "min-w-[980px]"
          }
        >
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="w-14 min-w-14">#</TableHead>
              <TableHead className="w-40 min-w-40">Type</TableHead>
              <TableHead className="w-[320px] min-w-[320px]">Item</TableHead>
              <TableHead className="w-40 min-w-40">UOM</TableHead>
              <TableHead className="w-28 min-w-28">Qty</TableHead>
              <TableHead className="w-40 min-w-40 text-right">
                Unit Price
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">({currency.code})</span>
                )}
              </TableHead>
              {showCurrencyPreview && (
                <TableHead className="w-40 min-w-40 text-right">
                  Unit Price ({previewCurrency?.code})
                </TableHead>
              )}
              <TableHead className="w-40 min-w-40 text-right">
                {showPricingPreview ? "Net Amount" : "Total"}
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({currency.code})
                  </span>
                )}
              </TableHead>
              {showPricingPreview && (
                <>
                  <TableHead className="w-40 min-w-40 text-right">
                    Tax Amount
                    {currency && !hideCurrency && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({currency.code})
                      </span>
                    )}
                  </TableHead>
                  <TableHead className="w-40 min-w-40 text-right">
                    Gross Amount
                    {currency && !hideCurrency && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({currency.code})
                      </span>
                    )}
                  </TableHead>
                </>
              )}
              {withTaxes && taxLayout === "inline" && (
                <TableHead
                  className={hasAnyTaxes ? "w-[380px] min-w-[380px]" : "w-[180px] min-w-[180px]"}
                >
                  Taxes
                </TableHead>
              )}
              {canDelete && !readonly && (
                <TableHead className="w-14 min-w-14 text-center" />
              )}
            </TableRow>
          </TableHeader>

          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={tableColumnCount}
                  className="text-center text-muted-foreground py-8"
                >
                  No items added. Click &quot;Add Row&quot; to get started.
                </TableCell>
              </TableRow>
            ) : (
              items.map((entry, index) => (
                <React.Fragment key={index}>
                  <TableRow className="group hover:bg-muted/50 align-top">
                    <TableCell className="font-medium text-muted-foreground pt-3">
                      {index + 1}
                    </TableCell>

                    {/* Type selector */}
                    <TableCell>
                      <Select
                        value={entry.type}
                        onValueChange={(v) => handleTypeChange(index, v as UnifiedLineItemType)}
                        disabled={readonly}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {allowedTypes.includes("inventory") && (
                            <SelectItem value="inventory">Inventory</SelectItem>
                          )}
                          {allowedTypes.includes("service") && (
                            <SelectItem value="service">Service</SelectItem>
                          )}
                          {allowedTypes.includes("other") && (
                            <SelectItem value="other">Other</SelectItem>
                          )}
                          {allowedTypes.includes("fixed_asset") && (
                            <SelectItem value="fixed_asset">Fixed Asset</SelectItem>
                          )}
                          {allowedTypes.includes("other_expense") && (
                            <SelectItem value="other_expense">Other Expense</SelectItem>
                          )}
                        </SelectContent>
                      </Select>
                    </TableCell>

                    {/* Item input - varies by type */}
                    <TableCell className="w-[320px] min-w-[320px]">
                      <div className="flex items-start gap-2">
                        <div className="min-w-0 flex-1 space-y-1">
                          {entry.type === "inventory" || entry.type === "service" ? (
                            <PaginatedSearchableSelect<IInventoryItem>
                              key={entry.type}
                              fetchFirstPage={(params) =>
                                INVENTORY_ITEMS_API.fetchInventoryItems({
                                  ...params,
                                  item_type: entry.type === "service" ? "SERVICES" : "GOODS",
                                })
                              }
                              fetchFromUrl={INVENTORY_ITEMS_API.fetchInventoryItemsFromUrl}
                              placeholder={entry.type === "service" ? "Select service" : "Select item"}
                              searchPlaceholder={entry.type === "service" ? "Search services..." : "Search items..."}
                              emptyMessage={entry.type === "service" ? "No services found" : "No items found"}
                              idKey="id"
                              valueKey="id"
                              labelKeyFn={(item) => item.item_name}
                              labelDescKeyFn={(item) =>
                                entry.type === "service"
                                  ? item.item_code
                                  : `${item.item_code} · ${item.quantity_on_hand} on hand`
                              }
                              value={entry.item?.id || undefined}
                              initialData={entry.item ? [entry.item as IInventoryItem] : []}
                              onValueChange={() => {}}
                              onItemSelected={(item) => handleItemSelected(index, item)}
                              disabled={readonly}
                              createAction={
                                !readonly
                                  ? {
                                      label: entry.type === "service" ? "Create new service" : "Create new item",
                                      onClick: () => setInventoryItemCreationIndex(index),
                                    }
                                  : undefined
                              }
                            />
                          ) : entry.type === "fixed_asset" ? (
                            <div className="grid w-full grid-cols-2 gap-2">
                              <Input
                                placeholder="Asset name (optional)"
                                value={entry.item_name}
                                onChange={(e) =>
                                  updateItem(index, {
                                    item_name: e.target.value,
                                    line_item: e.target.value,
                                  })
                                }
                                disabled={readonly}
                                className="min-w-0 w-full"
                              />
                              <div className="min-w-0">
                                <PaginatedSearchableSelect<IAssetCategory>
                                  fetchFirstPage={ASSET_CATEGORIES_API.fetchAssetCategories}
                                  fetchFromUrl={ASSET_CATEGORIES_API.fetchAssetCategoriesFromUrl}
                                  idKey="base_uuid"
                                  valueKey="base_uuid"
                                  labelKey="category_name"
                                  labelDescKey="reference_code"
                                  popoverClassName="!w-[320px] !min-w-[320px] !max-w-[320px]"
                                  popoverAlign="start"
                                  placeholder="Category (required)"
                                  searchPlaceholder="Search categories..."
                                  emptyMessage="No categories found"
                                  value={entry.asset_category}
                                  initialData={entry.categoryData ? [entry.categoryData] : []}
                                  onValueChange={() => {}}
                                  onItemSelected={(cat) =>
                                    updateItem(index, {
                                      asset_category: cat?.base_uuid,
                                      categoryData: cat ?? undefined,
                                    })
                                  }
                                  disabled={readonly}
                                />
                                {(errors[`line_item_${index}`] ||
                                  lineItemErrors?.[`line_item_${index}`]) && (
                                  <p className="text-xs text-red-600">
                                    {errors[`line_item_${index}`] ||
                                      lineItemErrors?.[`line_item_${index}`]}
                                  </p>
                                )}
                              </div>
                            </div>
                          ) : entry.type === "other_expense" ? (
                            <div className="flex gap-2">
                              <Input
                                placeholder="Expense name e.g. Shipping"
                                value={entry.expense_name || ""}
                                onChange={(e) =>
                                  updateItem(index, {
                                    expense_name: e.target.value,
                                    item_name: e.target.value,
                                    line_item: index + 1,
                                  })
                                }
                                disabled={readonly}
                                className="flex-1"
                              />
                              <div className="flex-1">
                                <PaginatedSearchableSelect<IAccount>
                                  fetchFirstPage={ACCOUNTS_API.fetchAccounts}
                                  fetchFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
                                  idKey="base_uuid"
                                  valueKey="base_uuid"
                                  labelKey="account_name"
                                  placeholder="Select account"
                                  searchPlaceholder="Search accounts..."
                                  emptyMessage="No accounts found"
                                  onValueChange={() => {}}
                                  onItemSelected={(acc) =>
                                    updateItem(index, {account_to_record_expense: acc?.base_uuid})
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

                        {!readonly && (
                          <div className="flex shrink-0 items-center gap-1">
                            {taxLayout === "rows" && canApplyTaxes(entry.type) && (
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => addTax(index)}
                                className="h-10 px-2 text-xs text-muted-foreground hover:text-primary"
                              >
                                <Icon icon="hugeicons:plus-sign" className="mr-1 size-3" />
                                Tax
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    {/* UOM */}
                    <TableCell>
                      {entry.type === "inventory" || entry.type === "service" ? (
                        <div>
                          {entry.item?.inventory_item_units_of_measure?.length ? (
                            <Select
                              value={entry.selected_uom_uuid || getDefaultUOM(entry.item)?.base_uuid}
                              onValueChange={(v) => handleUOMChange(index, v)}
                              disabled={readonly}
                            >
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder="UOM" />
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
                          ) : (
                            <span className="text-sm text-muted-foreground">-</span>
                          )}
                          {lineItemErrors[`unit_of_measure_${index}`] && (
                            <p className="mt-1 text-xs text-red-600">
                              {lineItemErrors[`unit_of_measure_${index}`]}
                            </p>
                          )}
                        </div>
                      ) : entry.type === "other" ? (
                        <Input
                          placeholder="e.g. pcs, kg"
                          value={entry.selected_uom_abbreviation || ""}
                          onChange={(e) =>
                            updateItem(index, {selected_uom_abbreviation: e.target.value})
                          }
                          disabled={readonly}
                        />
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>

                    {/* Quantity */}
                    <TableCell>
                      <Input
                        type="number"
                        min="1"
                        step="1"
                        placeholder="0"
                        className="text-right"
                        onFocus={(e) => e.target.select()}
                        value={entry.quantity}
                        onChange={(e) => {
                          const value = parseInt(e.target.value) || 0;
                          updateItem(index, {quantity: value});
                        }}
                        disabled={readonly}
                      />
                      {errors[`quantity_${index}`] && (
                        <p className="text-xs text-red-600">{errors[`quantity_${index}`]}</p>
                      )}
                    </TableCell>

                    {/* Unit Price */}
                    <TableCell>
                      <FormattedNumberInput
                        value={entry.unit_price}
                        onValueChange={(value) => handleUnitPriceChange(index, value)}
                        disabled={readonly || (!allowUnitPriceOverride && !!entry.item)}
                        className="text-right"
                      />
                    </TableCell>

                    {showCurrencyPreview && (
                      <TableCell className="align-top">
                        <FormattedNumberInput
                          value={(Number(entry.unit_price) || 0) * previewMultiplier}
                          onValueChange={(value) => handleBaseUnitPriceChange(index, value)}
                          disabled={readonly || (!allowUnitPriceOverride && !!entry.item)}
                          className="text-right"
                        />
                      </TableCell>
                    )}

                    {/* Line Total */}
                    <TableCell className="text-right font-medium pt-3">
                      {formatCurrency(
                        showPricingPreview
                          ? (Number(entry.quantity) || 0) *
                              (parseFloat(entry.net_unit_price ?? entry.unit_price) || 0)
                          : entry.line_total,
                      )}
                    </TableCell>
                    {showPricingPreview && (
                      <>
                        <TableCell className="text-right font-medium pt-3">
                          {formatCurrency(
                            (Number(entry.quantity) || 0) *
                              (parseFloat(entry.tax_unit_price ?? "0") || 0),
                          )}
                        </TableCell>
                        <TableCell className="text-right font-medium pt-3">
                          {formatCurrency(
                            (Number(entry.quantity) || 0) *
                              (parseFloat(entry.display_unit_price ?? entry.unit_price) || 0),
                          )}
                        </TableCell>
                      </>
                    )}

                    {withTaxes && taxLayout === "inline" && (
                      <TableCell
                        className={
                          hasAnyTaxes ? "w-[380px] min-w-[380px]" : "w-[180px] min-w-[180px]"
                        }
                      >
                        {canApplyTaxes(entry.type) ? (
                          <div className="flex items-start gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size={(entry.applicable_taxes ?? []).length > 0 ? "icon" : "sm"}
                              className={`h-10 shrink-0 rounded-xl ${
                                (entry.applicable_taxes ?? []).length > 0 ? "w-10" : ""
                              }`}
                              onClick={() => addTax(index)}
                              title="Add tax"
                            >
                              <Icon
                                icon="hugeicons:plus-sign"
                                className={`size-4 ${
                                  (entry.applicable_taxes ?? []).length > 0 ? "" : "mr-1"
                                }`}
                              />
                              {(entry.applicable_taxes ?? []).length === 0 ? "Add tax" : null}
                            </Button>

                            {(entry.applicable_taxes ?? []).length > 0 && (
                              <div className="min-w-0 flex-1 space-y-2">
                                {(entry.applicable_taxes ?? []).map((tax, taxIndex) => (
                                  <div
                                    key={`${index}-${taxIndex}`}
                                    className="grid grid-cols-[auto_minmax(190px,1fr)_auto] items-start gap-2"
                                  >
                                    <Button
                                      type="button"
                                      size="icon"
                                      variant="ghost"
                                      className="h-10 w-10 text-muted-foreground hover:text-destructive"
                                      onClick={() => removeTax(index, taxIndex)}
                                      title="Remove tax"
                                    >
                                      <Icon icon="hugeicons:cancel-01" className="size-4" />
                                    </Button>

                                    <PaginatedSearchableSelect
                                      placeholder="Select tax"
                                      searchPlaceholder="Search taxes..."
                                      emptyMessage="No taxes found"
                                      fetchFirstPage={TAXES_API.fetchTaxes}
                                      fetchFromUrl={TAXES_API.fetchTaxesFromUrl}
                                      idKey="base_uuid"
                                      valueKey="base_uuid"
                                      labelKey="tax_name"
                                      labelDescKey="reference_code"
                                      value={tax.tax ? String(tax.tax) : undefined}
                                      initialData={
                                        (tax as any)._taxObject ? [(tax as any)._taxObject] : []
                                      }
                                      onValueChange={(list) =>
                                        updateTax(index, taxIndex, "tax", list[0] || 0)
                                      }
                                    />

                                    <div className="flex h-10 items-center gap-2 whitespace-nowrap text-xs text-muted-foreground">
                                      Inclusive
                                      <Switch
                                        checked={tax.is_inclusive}
                                        onCheckedChange={(checked) =>
                                          updateTax(index, taxIndex, "is_inclusive", checked)
                                        }
                                      />
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    )}

                    {canDelete && !readonly && (
                      <TableCell className="w-14 min-w-14 px-2 text-center">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeItem(index)}
                          className="h-9 w-9 text-destructive hover:bg-destructive/10 hover:text-destructive"
                          disabled={items.length === 1}
                          title="Remove line item"
                        >
                          <Icon icon="mdi:delete-outline" className="size-4" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>

                  {/* Tax sub-rows */}
                  {taxLayout === "rows" &&
                    canApplyTaxes(entry.type) &&
                    (entry.applicable_taxes ?? []).map((tax, taxIndex) => (
                      <TableRow key={`tax-${index}-${taxIndex}`} className="hover:bg-transparent">
                        <TableCell />
                        <TableCell colSpan={tableColumnCount - 1} className="py-1">
                          <div className="ml-4 flex w-fit max-w-full items-center gap-3 rounded-lg bg-muted/40 px-3 py-2">
                            <div className="w-[360px] max-w-[50vw]">
                              <PaginatedSearchableSelect
                                placeholder="Select tax"
                                searchPlaceholder="Search taxes..."
                                emptyMessage="No taxes found"
                                fetchFirstPage={TAXES_API.fetchTaxes}
                                fetchFromUrl={TAXES_API.fetchTaxesFromUrl}
                                idKey="base_uuid"
                                valueKey="base_uuid"
                                labelKey="tax_name"
                                labelDescKey="reference_code"
                                triggerClassName="w-full"
                                popoverClassName="w-[360px]"
                                value={tax.tax ? String(tax.tax) : undefined}
                                initialData={
                                  (tax as any)._taxObject ? [(tax as any)._taxObject] : []
                                }
                                onValueChange={(list) =>
                                  updateTax(index, taxIndex, "tax", list[0] || 0)
                                }
                              />
                            </div>
                            <div className="flex shrink-0 items-center gap-2">
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
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => removeTax(index, taxIndex)}
                              className="h-8 w-8 shrink-0 text-red-500 hover:bg-red-50 hover:text-red-500"
                              title="Remove tax"
                            >
                              <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                </React.Fragment>
              ))
            )}
          </TableBody>

          <TableFooter>
            <TableRow>
              <TableCell
                colSpan={tableColumnCount}
              >
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
            </TableRow>
          </TableFooter>
        </Table>
      </div>
      {previewError && <p className="mt-2 text-sm text-destructive">{previewError}</p>}
      {showPricingPreview && (
        <div className="ml-auto w-full max-w-sm rounded-md border bg-muted/20 p-4">
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="font-medium">
                {currency && `${currency.code} `}
                {formatCurrency(pricingTotals.net)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Tax Amount</span>
              <span className="font-medium">
                {currency && `${currency.code} `}
                {formatCurrency(pricingTotals.tax)}
              </span>
            </div>
            <div className="flex justify-between border-t pt-3">
              <span className="font-semibold">Gross Total</span>
              <span className="font-bold">
                {currency && `${currency.code} `}
                {formatCurrency(pricingTotals.gross)}
              </span>
            </div>
          </div>
        </div>
      )}

      <InventoryItemCreatePanel
        open={inventoryItemCreationIndex !== null}
        onClose={() => setInventoryItemCreationIndex(null)}
        onSuccess={(newItem) => {
          if (inventoryItemCreationIndex !== null) {
            handleItemSelected(inventoryItemCreationIndex, newItem);
          }
          setInventoryItemCreationIndex(null);
        }}
        defaultType={
          inventoryItemCreationIndex !== null &&
          items[inventoryItemCreationIndex]?.type === "service"
            ? "SERVICES"
            : "GOODS"
        }
      />
    </div>
  );
}
