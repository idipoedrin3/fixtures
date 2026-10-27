"use client";

import {Icon} from "@iconify/react";
import {Fragment, useCallback, useEffect, useMemo, useRef, useState} from "react";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {Label} from "@/components/ui/label";
import {Switch} from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {INVOICES_API} from "#/_api/api.helpers";
import {Input} from "@/components/ui/input";
import {Textarea} from "#/_components/common/inputs/text-area";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {FormattedNumberInput} from "../../common/inputs/formatted-number-input";
import {formatCurrency} from "#/_lib/utils";
import {
  CURRENCY_CONVERSION_API,
  ICurrencyConversion,
  IExchangeRateInput,
} from "#/_api/services/system.service";
import {Currency} from "#/_types/api.types";
import InventoryItemSelect, {
  getItemName,
  InventoryItemSelectLevel,
  InventorySelectableItem,
} from "../inventory-item-select";
import PaginatedSearchableSelect from "../paginated-searchable-select";
import {BILL_OF_MATERIAL_API} from "#/_api/notifications.utils";
import type {ISalesLineDiscountFormData} from "#/_types/api.types";
import type {IBillOfMaterial} from "#/_types/types.utils";
import {
  calculateSalesLineDiscounts,
  sortSalesLineDiscounts,
  validateSalesLineDiscounts,
} from "./sales-line-discount.utils";
import {DiscountItemSummary, DiscountValueInput} from "./sales-line-discount-input";

type BomOption = IBillOfMaterial & {display_name: string};

export type LineItemDiscount = ISalesLineDiscountFormData & {
  id?: number;
  base_uuid?: string;
  discount_amount?: string;
};

export type LineItem = {
  sales_order_line_item_uuid?: string;
  quotation_line_item_uuid?: string;
  invoice_line_item_uuid?: string;
  line_item: string | number;
  item_name?: string;
  quantity: number;
  quantity_issued?: number;
  unit_price: string;
  net_unit_price?: string;
  tax_unit_price?: string;
  display_unit_price?: string;
  line_total: string;
  display_line_total?: string;
  selected_uom_uuid?: string;
  selected_uom_abbreviation?: string;
  unit_of_measure?: string | number | null;
  tax_base_uuid?: string;
  tax_type?: string;
  should_auto_create_manufacturing_order?: boolean;
  bill_of_material_to_be_used?: string;
  qty_to_be_manufactured?: number;
  manufacturing_order_description?: string;
  discounts?: LineItemDiscount[];
};

export interface LineItemData extends LineItem {
  item?: InventorySelectableItem;
  display_line_total?: string;
}

type Props = {
  showUOMSelector?: boolean;
  allowUnitPriceOverride?: boolean;
  canAdd?: boolean;
  canDelete?: boolean;
  onItemsChange?: (items: LineItem[]) => void;
  onValidationChange?: (isValid: boolean) => void;
  initialItems?: LineItemData[];
  model_name?: ICurrencyConversion["model_name"];
  object_uuid?: ICurrencyConversion["object_uuid"];
  currency?: Currency | string | null;
  previewCurrency?: Currency | null;
  exchangeRate?: IExchangeRateInput | null;
  convertCataloguePricesTo?: Currency | null;
  hideCurrency?: boolean;
  readonly?: boolean;
  uomValueType?: "uuid" | "id";
  showQtyIssued?: boolean;
  spreadColumns?: boolean;
  calculateTaxOnUnitPrice?: boolean;
  showTaxPricingDetails?: boolean;
  inventoryLevel?: InventoryItemSelectLevel;
  showManufacturingOptions?: boolean;
  enableDiscounts?: boolean;
};

export default function LineItemsInput({
  showUOMSelector = false,
  allowUnitPriceOverride = false,
  canAdd = true,
  canDelete = true,
  onItemsChange,
  onValidationChange,
  initialItems = [],
  model_name,
  object_uuid,
  hideCurrency = false,
  currency: selectedCurrency,
  previewCurrency,
  exchangeRate,
  convertCataloguePricesTo,
  showQtyIssued = false,
  readonly = false,
  spreadColumns = false,
  uomValueType = "uuid",
  calculateTaxOnUnitPrice,
  showTaxPricingDetails = false,
  inventoryLevel = "branch",
  showManufacturingOptions = false,
  enableDiscounts = true,
}: Props) {
  const [items, setItems] = useState<LineItemData[]>(initialItems);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [rate, setRate] = useState<string>("1");
  const [currency, setCurrency] = useState<Currency | string | null>(selectedCurrency ?? null);
  const [previewMultiplier, setPreviewMultiplier] = useState(1);
  const [previewError, setPreviewError] = useState<string>();
  const [discountModalIndex, setDiscountModalIndex] = useState<number | null>(null);
  const [expandedDiscount, setExpandedDiscount] = useState("0");
  const isFirstRender = useRef(true);
  const pricingRequestVersion = useRef<Record<number, number>>({});

  const calculateUnitPriceWithTax = useCallback(
    async (
      originalPrice: string,
      base_uuid?: string,
      type?: string,
    ): Promise<{
      amount: string;
      netAmount: string;
      taxAmount: string;
      base_uuid: string;
      type: string;
    }> => {
      if (!calculateTaxOnUnitPrice) {
        return {
          amount: originalPrice,
          netAmount: originalPrice,
          taxAmount: "0",
          base_uuid: "",
          type: "",
        };
      }
      try {
        const response = await INVOICES_API.previewTaxCalculation({
          amount: originalPrice,
          base_uuid,
          type,
        });
        return {
          amount: response.gross_amount.toString(),
          netAmount: response.net_amount.toString(),
          taxAmount: response.tax_amount.toString(),
          base_uuid: base_uuid ?? "",
          type: type ?? "",
        };
      } catch {
        return {
          amount: originalPrice,
          netAmount: originalPrice,
          taxAmount: "0",
          base_uuid: "",
          type: "",
        };
      }
    },
    [calculateTaxOnUnitPrice],
  );

  const convertCataloguePrice = useCallback(
    async (basePrice: string) => {
      if (!convertCataloguePricesTo) {
        return basePrice;
      }

      const result = await CURRENCY_CONVERSION_API.post({
        amount: basePrice,
        currency: convertCataloguePricesTo.id.toString(),
        ...(exchangeRate ? {exchange_rate: exchangeRate} : {}),
      });

      return result.converted_amount.toString();
    },
    [convertCataloguePricesTo, exchangeRate],
  );

  const canOverride = useMemo(() => {
    return !hideCurrency && (!object_uuid || !model_name);
  }, [hideCurrency, object_uuid, model_name]);

  useEffect(() => {
    if (selectedCurrency) {
      setCurrency(selectedCurrency);
    }
  }, [selectedCurrency]);

  const showCurrencyPreview = useMemo(() => {
    if (!previewCurrency || !currency) return false;

    const baseCode = typeof currency === "string" ? currency : currency.code;
    return previewCurrency.code !== baseCode;
  }, [currency, previewCurrency]);

  const totalsCurrencyCode = showCurrencyPreview
    ? previewCurrency?.code
    : typeof currency === "string"
      ? currency
      : currency?.code;

  const previewFractionDigits = useMemo(() => {
    if (!previewCurrency) return 2;

    const configuredDigits = Number(
      previewCurrency.decimal_places ?? previewCurrency.decimail_places ?? 2,
    );

    if (!Number.isFinite(configuredDigits)) return 2;

    return Math.min(Math.max(configuredDigits, 0), 20);
  }, [previewCurrency]);

  const formatPreviewAmount = useCallback(
    (amount: string | number | undefined) => {
      const numericAmount = Number(amount ?? 0);

      return (Number.isFinite(numericAmount) ? numericAmount : 0).toLocaleString("en-US", {
        minimumFractionDigits: previewFractionDigits,
        maximumFractionDigits: previewFractionDigits,
      });
    },
    [previewFractionDigits],
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
          currency: previewCurrency.id.toString(),
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

  const convertPreviewAmount = useCallback(
    (amount: string | number | undefined) => {
      return (Number(amount ?? 0) || 0) * previewMultiplier;
    },
    [previewMultiplier],
  );

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (onItemsChange) {
      const cleaned = items.map(({item, display_unit_price, ...rest}) => rest);
      onItemsChange(cleaned);
    }
  }, [items]);

  const getItemUOMs = useCallback((item: InventorySelectableItem) => {
    return "inventory_item" in item
      ? (item.branch_inventory_item_units_of_measure ?? [])
      : (item.inventory_item_units_of_measure ?? []);
  }, []);

  const getDefaultUOM = useCallback(
    (item: InventorySelectableItem) => {
      const units = getItemUOMs(item);

      if (!units.length) {
        return null;
      }

      const baseUnit = units.find((uom) => uom.is_base_unit_of_measure);

      return baseUnit ?? units[0];
    },
    [getItemUOMs],
  );

  const getSellingPriceFromUOM = useCallback(
    (item: InventorySelectableItem, uomUuid?: string) => {
      const units = getItemUOMs(item);

      if (!units.length) {
        return item.selling_price?.toString() ?? "0";
      }

      if (uomUuid) {
        const selectedUOM = units.find((uom) => uom.base_uuid === uomUuid);
        if (selectedUOM) {
          return selectedUOM.selling_price?.toString() ?? "0";
        }
      }

      const defaultUOM = getDefaultUOM(item);
      return defaultUOM?.selling_price?.toString() ?? "0";
    },
    [getDefaultUOM, getItemUOMs],
  );

  const calculateLineTotal = useCallback(
    (quantity: number, unitPrice: string): string => {
      const qty = Number(quantity) || 0;
      const price = parseFloat(unitPrice) || 0;
      const conversionRate = parseFloat(rate) || 1;
      return (qty * price * conversionRate).toFixed(2);
    },
    [rate],
  );

  const addDiscount = useCallback((lineIndex: number) => {
    setItems((prev) => {
      const newItems = [...prev];
      const lineItem = newItems[lineIndex];
      const discounts = lineItem.discounts || [];

      newItems[lineIndex] = {
        ...lineItem,
        discounts: [
          ...discounts,
          {
            discount_type: "percentage",
            discount_value: "",
            position: discounts.length,
            description: "",
          },
        ],
      };

      return newItems;
    });
  }, []);

  const removeDiscount = useCallback((lineIndex: number, discountIndex: number) => {
    setItems((prev) => {
      const newItems = [...prev];
      const lineItem = newItems[lineIndex];
      if (!lineItem.discounts) return prev;

      const newDiscounts = lineItem.discounts
        .filter((_, index) => index !== discountIndex)
        .map((discount, index) => ({...discount, position: index}));

      newItems[lineIndex] = {...lineItem, discounts: newDiscounts};

      return newItems;
    });
  }, []);

  const updateDiscount = useCallback(
    (lineIndex: number, discountIndex: number, fields: Partial<LineItemDiscount>) => {
      setItems((prev) => {
        const newItems = [...prev];
        const lineItem = newItems[lineIndex];
        if (!lineItem.discounts) return prev;

        const newDiscounts = lineItem.discounts.map((discount, index) =>
          index === discountIndex ? {...discount, ...fields} : discount,
        );

        newItems[lineIndex] = {...lineItem, discounts: newDiscounts};

        return newItems;
      });
    },
    [],
  );

  const moveDiscount = useCallback((lineIndex: number, fromIndex: number, toIndex: number) => {
    setItems((prev) => {
      const newItems = [...prev];
      const lineItem = newItems[lineIndex];
      const discounts = lineItem.discounts || [];

      if (
        fromIndex < 0 ||
        fromIndex >= discounts.length ||
        toIndex < 0 ||
        toIndex >= discounts.length
      ) {
        return prev;
      }

      const newDiscounts = [...discounts];
      const [moved] = newDiscounts.splice(fromIndex, 1);
      newDiscounts.splice(toIndex, 0, moved);

      newItems[lineIndex] = {
        ...lineItem,
        discounts: newDiscounts.map((discount, index) => ({
          ...discount,
          position: index,
        })),
      };

      return newItems;
    });
  }, []);

  const updateItem = useCallback(
    (index: number, updatedFields: Partial<LineItemData>) => {
      setItems((prev) => {
        const newItems = [...prev];
        const currentItem = newItems[index];

        const updatedItem = {
          ...currentItem,
          ...updatedFields,
        };

        if (
          updatedFields.quantity !== undefined ||
          updatedFields.unit_price !== undefined ||
          updatedFields.display_unit_price !== undefined ||
          updatedFields.net_unit_price !== undefined ||
          updatedFields.tax_unit_price !== undefined
        ) {
          updatedItem.line_total = calculateLineTotal(updatedItem.quantity, updatedItem.unit_price);
          if (updatedItem.display_unit_price) {
            updatedItem.display_line_total = calculateLineTotal(
              updatedItem.quantity,
              updatedItem.display_unit_price,
            );
          } else {
            updatedItem.display_line_total = undefined;
          }
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
      if (!item.line_item && !item.item_name) {
        newErrors[`line_item_${index}`] = "Item is required";
      }

      if (!item.quantity || item.quantity <= 0) {
        newErrors[`quantity_${index}`] = "Quantity must be greater than 0";
      }
      if (showUOMSelector && item.item && !item.unit_of_measure) {
        newErrors[`unit_of_measure_${index}`] = "Unit of measure is required";
      }
      if (
        item.unit_price === undefined ||
        item.unit_price === null ||
        parseFloat(item.unit_price) < 0
      ) {
        newErrors[`unit_price_${index}`] = "Unit price must be 0 or greater";
      }

      if (showManufacturingOptions && item.should_auto_create_manufacturing_order) {
        if (!item.qty_to_be_manufactured || item.qty_to_be_manufactured < 1) {
          newErrors[`qty_to_be_manufactured_${index}`] =
            "Quantity to be manufactured must be 1 or greater";
        }
      }

      if (item.discounts && item.discounts.length > 0) {
        const lineAmount = Number(item.line_total) || 0;
        const discountErrors = validateSalesLineDiscounts(item.discounts, lineAmount);

        sortSalesLineDiscounts(item.discounts).forEach((discount, discountIndex) => {
          const message = discountErrors[discountIndex];
          if (message) {
            newErrors[`discount_${index}_${discountIndex}`] = message;
          }
        });
      }
    });

    setErrors(newErrors);

    const isValid = Object.keys(newErrors).length === 0;
    if (onValidationChange) {
      onValidationChange(isValid);
    }

    return isValid;
  }, [items, onValidationChange, showManufacturingOptions, showUOMSelector]);

  useEffect(() => {
    validateItems();
  }, [items, validateItems]);

  const handleUOMChange = useCallback(
    async (index: number, uomUuid: string) => {
      const item = items[index];
      if (!item.item) return;

      const selectedUOM = getItemUOMs(item.item).find((uom) => uom.base_uuid === uomUuid);

      if (selectedUOM) {
        const originalSellingPrice = selectedUOM.selling_price?.toString() ?? "0";
        const documentSellingPrice = await convertCataloguePrice(originalSellingPrice);
        const taxResponse = await calculateUnitPriceWithTax(
          documentSellingPrice,
          item.tax_base_uuid,
          item.tax_type,
        );

        updateItem(index, {
          selected_uom_uuid: uomUuid,
          unit_of_measure:
            uomValueType === "id" ? (selectedUOM.unit_of_measure?.id ?? null) : uomUuid,
          selected_uom_abbreviation:
            selectedUOM.unit_of_measure.unit_abbreviation || selectedUOM.unit_of_measure.unit_name,
          unit_price: documentSellingPrice,
          net_unit_price: taxResponse.netAmount,
          tax_unit_price: taxResponse.taxAmount,
          display_unit_price: taxResponse.amount,
          tax_base_uuid: taxResponse.base_uuid,
          tax_type: taxResponse.type,
        });
      }
    },
    [
      items,
      calculateUnitPriceWithTax,
      convertCataloguePrice,
      getItemUOMs,
      updateItem,
      uomValueType,
    ],
  );

  const handleItemSelected = useCallback(
    async (index: number, item: InventorySelectableItem | null) => {
      if (!item) return;

      const existing = items[index];
      // The selector emits its initial selection while hydrating an existing
      // document line. Preserve that line's historical document-currency price.
      if (existing?.item?.base_uuid === item.base_uuid) return;

      const defaultUOM = getDefaultUOM(item);
      const originalSellingPrice = getSellingPriceFromUOM(item);
      const documentSellingPrice = await convertCataloguePrice(originalSellingPrice);

      const taxResponse = await calculateUnitPriceWithTax(
        documentSellingPrice,
        item.base_uuid,
        "sales",
      );

      updateItem(index, {
        item,
        item_name:
          "inventory_item" in item
            ? (item.inventory_item?.item_name ?? "")
            : "item_name" in item
              ? (item.item_name ?? "")
              : "",
        line_item: item.base_uuid,
        selected_uom_uuid: defaultUOM?.base_uuid,
        unit_of_measure:
          uomValueType === "id" ? (defaultUOM?.unit_of_measure?.id ?? null) : defaultUOM?.base_uuid,
        selected_uom_abbreviation:
          defaultUOM?.unit_of_measure.unit_abbreviation || defaultUOM?.unit_of_measure.unit_name,
        unit_price: documentSellingPrice,
        net_unit_price: taxResponse.netAmount,
        tax_unit_price: taxResponse.taxAmount,
        display_unit_price: taxResponse.amount,
        tax_base_uuid: item.base_uuid,
        tax_type: taxResponse.type,
        quantity: items[index]?.quantity || 1,
        line_total: calculateLineTotal(items[index]?.quantity || 1, documentSellingPrice),
        should_auto_create_manufacturing_order: false,
        bill_of_material_to_be_used: undefined,
        qty_to_be_manufactured: undefined,
        manufacturing_order_description: undefined,
      });
    },
    [
      getDefaultUOM,
      getSellingPriceFromUOM,
      calculateUnitPriceWithTax,
      convertCataloguePrice,
      updateItem,
      calculateLineTotal,
      items,
      inventoryLevel,
      uomValueType,
    ],
  );

  // Add new line item
  const addItem = useCallback(() => {
    setItems((prev) => [
      ...prev,
      {
        line_item: "",
        item_name: "",
        quantity: 1,
        quantity_issued: 0,
        unit_price: "0",
        net_unit_price: "0",
        tax_unit_price: "0",
        line_total: "0",
      },
    ]);
  }, []);

  // Remove line item
  const removeItem = useCallback(
    (index: number) => {
      setItems((prev) => {
        const newItems = prev.filter((_, i) => i !== index);

        // Clear error for this item
        setErrors((prevErrors) => {
          const newErrors = {...prevErrors};
          delete newErrors[`quantity_${index}`];
          delete newErrors[`unit_price_${index}`];
          delete newErrors[`line_item_${index}`];
          return newErrors;
        });

        return newItems;
      });
    },
    [items.length],
  );

  const lineSummaries = useMemo(() => {
    return items.map((item) => {
      const quantity = Number(item.quantity) || 0;
      const unitPrice = Number(item.unit_price) || 0;
      const netUnitPrice = Number(item.net_unit_price ?? item.unit_price) || 0;
      const taxUnitPrice = Number(item.tax_unit_price ?? 0) || 0;
      const grossUnitPrice = Number(item.display_unit_price ?? item.unit_price) || 0;
      const lineAmount = Number(item.line_total) || 0;

      const {totalDiscount, discountedTotal, breakdown} = calculateSalesLineDiscounts(
        item.discounts,
        lineAmount,
      );

      const ratio = lineAmount > 0 ? discountedTotal / lineAmount : 1;
      const taxInclusive = taxUnitPrice > 0 && Math.abs(grossUnitPrice - unitPrice) < 0.005;

      const taxAfter = taxUnitPrice * quantity * ratio;
      const exclusiveTaxAfter = taxInclusive ? 0 : taxAfter;

      return {
        lineAmount,
        totalDiscount,
        discountedTotal,
        breakdown,
        ratio,
        taxInclusive,
        netAfter: netUnitPrice * quantity * ratio,
        taxAfter,
        exclusiveTaxAfter,
        payable: discountedTotal + exclusiveTaxAfter,
      };
    });
  }, [items]);

  const invoiceTotals = useMemo(() => {
    return lineSummaries.reduce(
      (totals, line) => {
        totals.subtotal += line.lineAmount;
        totals.totalDiscount += line.totalDiscount;
        totals.subtotalAfterDiscount += line.discountedTotal;
        totals.taxTotal += line.taxAfter;
        totals.exclusiveTaxTotal += line.exclusiveTaxAfter;
        totals.grossTotal += line.payable;
        return totals;
      },
      {
        subtotal: 0,
        totalDiscount: 0,
        subtotalAfterDiscount: 0,
        taxTotal: 0,
        exclusiveTaxTotal: 0,
        grossTotal: 0,
      },
    );
  }, [lineSummaries]);

  const totalDiscount = invoiceTotals.totalDiscount;

  const grandTotal = useMemo(() => {
    return invoiceTotals.grossTotal.toFixed(2);
  }, [invoiceTotals.grossTotal]);

  const taxesAreInclusive = useMemo(() => {
    const taxed = lineSummaries.filter((line) => line.taxAfter > 0);

    return taxed.length > 0 && taxed.every((line) => line.taxInclusive);
  }, [lineSummaries]);

  const validateQuantity = useCallback((index: number, value: number) => {
    if (value <= 0) {
      setErrors((prev) => ({
        ...prev,
        [`quantity_${index}`]: "Quantity must be greater than 0",
      }));
      return false;
    }

    setErrors((prev) => {
      const newErrors = {...prev};
      delete newErrors[`quantity_${index}`];
      return newErrors;
    });
    return true;
  }, []);

  const validateUnitPrice = useCallback((index: number, value: string) => {
    const price = parseFloat(value);
    if (isNaN(price) || price < 0) {
      setErrors((prev) => ({
        ...prev,
        [`unit_price_${index}`]: "Unit price must be 0 or greater",
      }));
      return false;
    }

    setErrors((prev) => {
      const newErrors = {...prev};
      delete newErrors[`unit_price_${index}`];
      return newErrors;
    });
    return true;
  }, []);

  const handleSellingPriceChange = useCallback(
    async (index: number, value: number | null) => {
      const stringValue = (value ?? 0).toString();
      validateUnitPrice(index, stringValue);

      updateItem(index, {
        unit_price: stringValue,
        net_unit_price: stringValue,
        tax_unit_price: "0",
        display_unit_price: stringValue,
      });

      const entry = items[index];
      if (!entry) return;

      const requestVersion = (pricingRequestVersion.current[index] ?? 0) + 1;
      pricingRequestVersion.current[index] = requestVersion;

      const taxResponse = await calculateUnitPriceWithTax(
        stringValue,
        entry.tax_base_uuid || entry.item?.base_uuid,
        entry.tax_type || "sales",
      );

      if (pricingRequestVersion.current[index] !== requestVersion) return;

      updateItem(index, {
        unit_price: stringValue,
        net_unit_price: taxResponse.netAmount,
        tax_unit_price: taxResponse.taxAmount,
        display_unit_price: taxResponse.amount,
        tax_base_uuid: taxResponse.base_uuid,
        tax_type: taxResponse.type,
      });
    },
    [calculateUnitPriceWithTax, items, updateItem, validateUnitPrice],
  );

  const columnCount =
    2 +
    (showUOMSelector ? 1 : 0) +
    1 +
    (showQtyIssued ? 1 : 0) +
    (showCurrencyPreview ? 1 : 0) +
    1 +
    (enableDiscounts ? 1 : 0) +
    (showTaxPricingDetails ? 2 : 0) +
    (canDelete && !readonly ? 1 : 0);

  const modalItem = discountModalIndex !== null ? items[discountModalIndex] : null;
  const modalSummary = discountModalIndex !== null ? lineSummaries[discountModalIndex] : null;
  const baseCurrencyCode = typeof currency === "string" ? currency : currency?.code;

  const modalHasErrors =
    discountModalIndex !== null &&
    Object.keys(errors).some((key) => key.startsWith(`discount_${discountModalIndex}_`));

  const modalHasBlank = (modalItem?.discounts ?? []).some(
    (d) => String(d.discount_value ?? "").trim() === "",
  );

  const modalInvalid = modalHasErrors || modalHasBlank;

  return (
    <div className="">
      <div className="space-y-2">
        <h4 className="text-lg font-semibold text-gray-900">Items</h4>
        <p className="text-sm text-gray-600 leading-relaxed">
          Contains the list of products or services being quoted, including quantities, unit prices,
          and totals.
        </p>
      </div>
      <div className="overflow-x-auto rounded-md border mt-4">
        <Table
          className={
            spreadColumns || showCurrencyPreview
              ? "w-full min-w-[1180px] table-fixed"
              : "w-full min-w-[1180px]"
          }
        >
          <TableHeader>
            <TableRow className="text-base text-slate-800 hover:bg-background">
              <TableHead className={spreadColumns ? "" : "w-12"}>#</TableHead>
              <TableHead className="w-[320px] min-w-[280px] max-w-[360px]">
                Item Description
              </TableHead>
              {showUOMSelector && <TableHead className="w-36 min-w-36">Unit of Measure</TableHead>}
              <TableHead className="w-24 min-w-24 text-center">Qty</TableHead>
              {showQtyIssued && (
                <TableHead className={spreadColumns ? "" : "w-32"}>Qty Issued</TableHead>
              )}
              <TableHead className="w-32 min-w-32 text-center">
                Unit Price
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({typeof currency === "string" ? currency : currency?.code})
                  </span>
                )}
              </TableHead>
              {showCurrencyPreview && (
                <TableHead className="w-36 min-w-36 text-center">
                  Unit Price ({previewCurrency?.code})
                </TableHead>
              )}
              <TableHead className="w-36 min-w-36 text-right">
                {showTaxPricingDetails ? "Net Amount" : "Total Amount"}
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">({totalsCurrencyCode})</span>
                )}
              </TableHead>
              <TableHead className="w-36 min-w-36 text-right">
                Discount
                {currency && !hideCurrency && (
                  <span className="ml-1 text-xs text-muted-foreground">({totalsCurrencyCode})</span>
                )}
              </TableHead>
              {showTaxPricingDetails && (
                <TableHead className="w-36 min-w-36 text-right">
                  Tax Amount
                  {currency && !hideCurrency && (
                    <span className="ml-1 text-xs text-muted-foreground">
                      ({totalsCurrencyCode})
                    </span>
                  )}
                </TableHead>
              )}
              {showTaxPricingDetails && (
                <TableHead className="w-36 min-w-36 text-right">
                  Gross Amount
                  {currency && !hideCurrency && (
                    <span className="ml-1 text-xs text-muted-foreground">
                      ({totalsCurrencyCode})
                    </span>
                  )}
                </TableHead>
              )}
              {canDelete && !readonly && <TableHead className="w-12 min-w-12" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columnCount} className="text-center text-muted-foreground py-8">
                  No items added. Click &quot;Add Row&quot; to get started.
                </TableCell>
              </TableRow>
            ) : (
              items.map((entry, index) => {
                const inventoryItem =
                  entry.item && "inventory_item" in entry.item
                    ? entry.item.inventory_item
                    : entry.item;
                const canManufacture =
                  showManufacturingOptions && inventoryItem?.item_type === "GOODS";
                const summary = lineSummaries[index];
                const lineDiscounts = sortSalesLineDiscounts(entry.discounts || []);

                return (
                  <Fragment key={index}>
                    <TableRow className="align-top hover:bg-muted/50">
                      <TableCell className="align-top font-medium text-muted-foreground">
                        <div className="flex h-10 items-center">{index + 1}</div>
                      </TableCell>
                      <TableCell className="w-[320px] max-w-[360px] align-top">
                        <div className="space-y-1">
                          <InventoryItemSelect
                            level={inventoryLevel}
                            canBeSold
                            placeholder="Select item"
                            searchPlaceholder="Search items..."
                            emptyMessage="No items found"
                            value={entry.item?.base_uuid || undefined}
                            initialData={entry.item ? [entry.item] : []}
                            onValueChange={() => {}}
                            onItemSelected={(item) => handleItemSelected(index, item)}
                            disabled={readonly}
                          />
                          {errors[`line_item_${index}`] && (
                            <p className="text-xs text-red-600">{errors[`line_item_${index}`]}</p>
                          )}
                        </div>
                      </TableCell>

                      {showUOMSelector && (
                        <TableCell className="align-top">
                          {entry.item && getItemUOMs(entry.item).length ? (
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
                                {getItemUOMs(entry.item).map((uom) => (
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
                          {errors[`unit_of_measure_${index}`] && (
                            <p className="text-xs text-red-600">
                              {errors[`unit_of_measure_${index}`]}
                            </p>
                          )}
                        </TableCell>
                      )}

                      <TableCell className="align-top">
                        <div className="space-y-1">
                          <Input
                            required
                            type="number"
                            min="1"
                            step="1"
                            placeholder="0"
                            className="text-center"
                            value={entry.quantity}
                            onChange={(e) => {
                              const value = parseInt(e.target.value) || 0;
                              validateQuantity(index, value);
                              updateItem(index, {
                                quantity: value,
                                qty_to_be_manufactured: entry.should_auto_create_manufacturing_order
                                  ? value
                                  : entry.qty_to_be_manufactured,
                              });
                            }}
                            disabled={readonly}
                          />
                          {errors[`quantity_${index}`] && (
                            <p className="text-xs text-red-600">{errors[`quantity_${index}`]}</p>
                          )}
                        </div>
                      </TableCell>
                      {showQtyIssued && (
                        <TableCell className="align-top">
                          <div className="space-y-1">
                            <Input
                              required
                              type="number"
                              min="1"
                              step="1"
                              placeholder="0"
                              className="text-center"
                              value={entry.quantity_issued ?? 0}
                              onChange={(e) => {
                                const value = parseInt(e.target.value) || 0;
                                validateQuantity(index, value);
                                updateItem(index, {quantity_issued: value});
                              }}
                              disabled={readonly}
                            />
                            {errors[`quantity_issued_${index}`] && (
                              <p className="text-xs text-red-600">
                                {errors[`quantity_issued_${index}`]}
                              </p>
                            )}
                          </div>
                        </TableCell>
                      )}
                      <TableCell className="align-top">
                        <div className="space-y-1">
                          <FormattedNumberInput
                            value={
                              showTaxPricingDetails
                                ? entry.unit_price
                                : entry.display_unit_price || entry.unit_price
                            }
                            onValueChange={(value) => {
                              if (showTaxPricingDetails) {
                                handleSellingPriceChange(index, value);
                                return;
                              }

                              const stringValue = (value ?? 0).toString();
                              validateUnitPrice(index, stringValue);
                              updateItem(index, {
                                unit_price: stringValue || "0",
                                display_unit_price: undefined,
                                display_line_total: undefined,
                              });
                            }}
                            disabled={readonly || (!allowUnitPriceOverride && !!entry.item)}
                            className="text-center"
                          />
                          {errors[`unit_price_${index}`] && (
                            <p className="text-xs text-red-600">{errors[`unit_price_${index}`]}</p>
                          )}
                        </div>
                      </TableCell>
                      {showCurrencyPreview && (
                        <TableCell className="align-top">
                          <div className="flex h-10 items-center justify-end overflow-hidden rounded-md border bg-muted/30 px-3 text-right font-medium tabular-nums">
                            <span className="truncate">
                              {formatPreviewAmount(convertPreviewAmount(entry.unit_price))}
                            </span>
                          </div>
                        </TableCell>
                      )}

                      <TableCell className="align-top overflow-hidden text-right font-medium">
                        <div className="flex h-10 items-center justify-end tabular-nums">
                          <span className="truncate">
                            {formatPreviewAmount(
                              convertPreviewAmount(
                                showTaxPricingDetails
                                  ? (summary?.netAfter ?? 0)
                                  : entry.display_line_total
                                    ? Number(entry.display_line_total) * (summary?.ratio ?? 1)
                                    : (summary?.discountedTotal ?? 0),
                              ),
                            )}
                          </span>
                        </div>
                      </TableCell>

                      {enableDiscounts && (
                        <TableCell className="align-top overflow-hidden text-right font-medium">
                          <div className="flex h-10 items-center justify-end tabular-nums">
                            {lineDiscounts.length === 0 ? (
                              <Button
                                type="button"
                                variant="link"
                                size="sm"
                                className="h-auto p-0 text-xs"
                                onClick={() => {
                                  addDiscount(index);
                                  setExpandedDiscount("0");
                                  setDiscountModalIndex(index);
                                }}
                                disabled={readonly}
                              >
                                Add discount
                              </Button>
                            ) : (
                              <button
                                type="button"
                                className="truncate underline-offset-2 hover:underline"
                                onClick={() => {
                                  setExpandedDiscount("0");
                                  setDiscountModalIndex(index);
                                }}
                                disabled={readonly}
                              >
                                {formatPreviewAmount(
                                  convertPreviewAmount((summary?.totalDiscount ?? 0).toFixed(2)),
                                )}
                              </button>
                            )}
                          </div>
                        </TableCell>
                      )}

                      {showTaxPricingDetails && (
                        <TableCell className="align-top overflow-hidden text-right font-medium">
                          <div className="flex h-10 items-center justify-end tabular-nums">
                            <span className="truncate">
                              {formatPreviewAmount(
                                convertPreviewAmount(
                                  (Number(entry.quantity) || 0) *
                                    (parseFloat(entry.tax_unit_price ?? "0") || 0) *
                                    (summary?.ratio ?? 1),
                                ),
                              )}
                            </span>
                          </div>
                        </TableCell>
                      )}

                      {showTaxPricingDetails && (
                        <TableCell className="align-top overflow-hidden text-right font-medium">
                          <div className="flex h-10 items-center justify-end tabular-nums">
                            <span className="truncate">
                              {formatPreviewAmount(
                                convertPreviewAmount(
                                  (Number(entry.quantity) || 0) *
                                    (parseFloat(entry.display_unit_price ?? entry.unit_price) ||
                                      0) *
                                    (summary?.ratio ?? 1),
                                ),
                              )}
                            </span>
                          </div>
                        </TableCell>
                      )}

                      {canDelete && !readonly && (
                        <TableCell className="align-top">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeItem(index)}
                            className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                            title="Remove item"
                          >
                            <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>

                    {canManufacture && inventoryItem && (
                      <TableRow className="border-t-0 bg-muted/20 hover:bg-muted/30">
                        <TableCell />
                        <TableCell
                          colSpan={columnCount - 1}
                          className={
                            entry.should_auto_create_manufacturing_order
                              ? "px-4 pb-4 pt-2"
                              : "px-4 py-2"
                          }
                        >
                          <div className="flex flex-wrap items-end gap-4">
                            <div
                              className={
                                entry.should_auto_create_manufacturing_order
                                  ? "min-w-[150px] space-y-1"
                                  : "flex h-8 min-w-[150px] items-center"
                              }
                            >
                              {entry.should_auto_create_manufacturing_order && (
                                <Label className="text-xs">Manufacturing</Label>
                              )}
                              <div
                                className={
                                  entry.should_auto_create_manufacturing_order
                                    ? "flex h-10 items-center gap-2"
                                    : "flex items-center gap-2"
                                }
                              >
                                <Switch
                                  checked={!!entry.should_auto_create_manufacturing_order}
                                  disabled={readonly}
                                  onCheckedChange={(checked) =>
                                    updateItem(index, {
                                      should_auto_create_manufacturing_order: checked,
                                      bill_of_material_to_be_used: checked
                                        ? entry.bill_of_material_to_be_used
                                        : undefined,
                                      qty_to_be_manufactured: checked
                                        ? entry.qty_to_be_manufactured || entry.quantity
                                        : undefined,
                                      manufacturing_order_description: checked
                                        ? entry.manufacturing_order_description
                                        : undefined,
                                    })
                                  }
                                />
                                <span className="whitespace-nowrap text-sm font-medium">
                                  Manufacture
                                </span>
                              </div>
                            </div>

                            {entry.should_auto_create_manufacturing_order && (
                              <>
                                <div className="min-w-[260px] flex-1 space-y-1">
                                  <Label showOptional className="text-xs">
                                    Bill of Material
                                  </Label>
                                  <PaginatedSearchableSelect<BomOption>
                                    fetchFirstPage={async (args) => {
                                      const response =
                                        await BILL_OF_MATERIAL_API.fetchBillOfMaterials({
                                          ...args,
                                          inventory_item_uuid: inventoryItem.base_uuid,
                                        });

                                      return {
                                        ...response,
                                        results: response.results.map((bom) => ({
                                          ...bom,
                                          display_name: `${bom.inventory_item.item_name} · ${
                                            bom.unit_of_measure.unit_abbreviation ||
                                            bom.unit_of_measure.unit_name
                                          }`,
                                        })),
                                      };
                                    }}
                                    fetchFromUrl={async ({url}) => {
                                      const response =
                                        await BILL_OF_MATERIAL_API.fetchBillOfMaterialsFromUrl({
                                          url,
                                        });

                                      return {
                                        ...response,
                                        results: response.results.map((bom) => ({
                                          ...bom,
                                          display_name: `${bom.inventory_item.item_name} · ${
                                            bom.unit_of_measure.unit_abbreviation ||
                                            bom.unit_of_measure.unit_name
                                          }`,
                                        })),
                                      };
                                    }}
                                    idKey="base_uuid"
                                    valueKey="base_uuid"
                                    labelKey="reference_code"
                                    labelDescKey="display_name"
                                    value={entry.bill_of_material_to_be_used}
                                    onValueChange={(values) =>
                                      updateItem(index, {
                                        bill_of_material_to_be_used: values[0] || undefined,
                                      })
                                    }
                                    placeholder="Select BOM"
                                    searchPlaceholder="Search BOMs..."
                                    emptyMessage="No BOM is configured for this item; the order can still be created"
                                  />
                                </div>

                                <div className="w-[180px] space-y-1">
                                  <Label required className="whitespace-nowrap text-xs">
                                    Quantity to Manufacture
                                  </Label>
                                  <FormattedNumberInput
                                    min={1}
                                    value={entry.qty_to_be_manufactured ?? entry.quantity}
                                    onValueChange={(value) =>
                                      updateItem(index, {
                                        qty_to_be_manufactured: value ?? 0,
                                      })
                                    }
                                  />
                                </div>

                                <div className="min-w-[280px] flex-1 space-y-1">
                                  <Label showOptional className="text-xs">
                                    Notes
                                  </Label>
                                  <Input
                                    value={entry.manufacturing_order_description ?? ""}
                                    placeholder="Optional production instructions"
                                    maxLength={1000}
                                    disabled={readonly}
                                    onChange={(event) =>
                                      updateItem(index, {
                                        manufacturing_order_description:
                                          event.target.value || undefined,
                                      })
                                    }
                                  />
                                </div>
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })
            )}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={columnCount}>
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
      {enableDiscounts && discountModalIndex !== null && modalItem && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setDiscountModalIndex(null);
          }}
        >
          <DialogContent className="flex max-h-[90vh] max-w-3xl flex-col gap-0 overflow-hidden p-0">
            <DialogHeader className="shrink-0 border-b px-5 py-4 pr-14">
              <DialogTitle>Apply discounts</DialogTitle>
              <DialogDescription className="text-sm">
                Discounts apply in order, each to the amount remaining after the previous one.
              </DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-5 py-4">
              <DiscountItemSummary
                itemName={
                  modalItem.item_name ||
                  (modalItem.item ? getItemName(modalItem.item) : undefined) ||
                  `Item ${discountModalIndex + 1}`
                }
                currency={baseCurrencyCode}
                unitPrice={modalItem.unit_price}
                quantity={modalItem.quantity}
                unitOfMeasure={modalItem.selected_uom_abbreviation}
                originalTotal={modalSummary?.lineAmount ?? 0}
                totalDiscount={modalSummary?.totalDiscount ?? 0}
                discountedTotal={modalSummary?.discountedTotal ?? 0}
                taxInclusive={modalSummary?.taxInclusive}
              />
              <Accordion
                type="single"
                collapsible
                value={expandedDiscount}
                onValueChange={setExpandedDiscount}
                className="space-y-3"
              >
              {sortSalesLineDiscounts(modalItem.discounts || []).map(
                (discount, discountIndex, discounts) => {
                  const discountError = errors[`discount_${discountModalIndex}_${discountIndex}`];
                  const breakdown = modalSummary?.breakdown ?? [];
                  const breakdownAmount = breakdown[discountIndex]?.amount;
                  const appliedBefore = breakdown
                    .slice(0, discountIndex)
                    .reduce((sum, b) => sum + (Number(b?.amount) || 0), 0);
                  const remainingBefore =
                    Math.round(Math.max(0, (modalSummary?.lineAmount ?? 0) - appliedBefore) * 100) /
                    100;

                  return (
                    <AccordionItem
                      key={
                        discount.id ??
                        discount.base_uuid ??
                        `${discountModalIndex}-${discountIndex}`
                      }
                      value={String(discountIndex)}
                      className="overflow-hidden rounded-lg border data-[state=open]:border-primary/30"
                    >
                      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 px-4">
                        <AccordionTrigger className="gap-3 py-3 text-left hover:no-underline">
                          <span className="min-w-0">
                            <span className="block text-sm font-semibold">
                              Discount {discountIndex + 1}
                              {discount.discount_value !== "" && (
                                <span className="ml-2 font-normal text-muted-foreground">
                                  {discount.discount_type === "percentage"
                                    ? `${discount.discount_value}%`
                                    : `${baseCurrencyCode ?? ""} ${formatCurrency(discount.discount_value)}`}
                                </span>
                              )}
                            </span>
                            <span
                              className={`mt-1 block text-xs ${
                                discountError ? "text-destructive" : "text-muted-foreground"
                              }`}
                            >
                              {discountError ||
                                (discount.discount_value === ""
                                  ? "Enter discount details"
                                  : `Reduction: ${baseCurrencyCode ?? ""} ${formatCurrency(
                                      breakdownAmount ?? 0,
                                    )}`)}
                            </span>
                          </span>
                        </AccordionTrigger>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => {
                            removeDiscount(discountModalIndex, discountIndex);
                            setExpandedDiscount(String(Math.max(0, discountIndex - 1)));
                          }}
                          disabled={readonly}
                        >
                          Remove
                        </Button>
                      </div>
                      <AccordionContent className="border-t px-4 pt-4">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Discount type</Label>
                          <Select
                            value={discount.discount_type}
                            onValueChange={(value) =>
                              updateDiscount(discountModalIndex, discountIndex, {
                                discount_type: value as LineItemDiscount["discount_type"],
                              })
                            }
                            disabled={readonly}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="percentage">Percentage</SelectItem>
                              <SelectItem value="fixed">Fixed amount</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">
                            {discount.discount_type === "percentage"
                              ? "Percentage"
                              : `Amount${baseCurrencyCode ? ` (${baseCurrencyCode})` : ""}`}
                          </Label>
                          <DiscountValueInput
                            autoFocus={expandedDiscount === String(discountIndex)}
                            value={discount.discount_value ?? ""}
                            discountType={discount.discount_type}
                            suffix={discount.discount_type === "percentage" ? "%" : undefined}
                            max={discount.discount_type === "fixed" ? remainingBefore : undefined}
                            onChange={(value) =>
                              updateDiscount(discountModalIndex, discountIndex, {
                                discount_value: value,
                              })
                            }
                            disabled={readonly}
                            error={discountError}
                          />
                          {discount.discount_type === "percentage" ? (
                            breakdownAmount !== undefined && (
                              <p className="text-xs text-muted-foreground">
                                Discount amount: {formatCurrency(breakdownAmount.toFixed(2))}
                              </p>
                            )
                          ) : (
                            <p className="text-xs text-muted-foreground">
                              Max: {formatCurrency(remainingBefore.toFixed(2))}
                            </p>
                          )}
                        </div>
                        <div className="sm:col-span-2">
                          <Textarea
                            label="Description"
                            showOptional
                            collapsible
                            defaultExpanded={false}
                            aria-label={`Discount ${discountIndex + 1} description`}
                            value={discount.description || ""}
                            onChange={(event) =>
                              updateDiscount(discountModalIndex, discountIndex, {
                                description: event.target.value || undefined,
                              })
                            }
                            disabled={readonly}
                            placeholder="e.g. Promotional discount, bulk discount, loyalty discount…"
                          />
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            moveDiscount(discountModalIndex, discountIndex, discountIndex - 1);
                            setExpandedDiscount(String(discountIndex - 1));
                          }}
                          disabled={discountIndex === 0 || readonly}
                        >
                          Move up
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            moveDiscount(discountModalIndex, discountIndex, discountIndex + 1);
                            setExpandedDiscount(String(discountIndex + 1));
                          }}
                          disabled={discountIndex === discounts.length - 1 || readonly}
                        >
                          Move down
                        </Button>
                      </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                },
              )}
              </Accordion>
            </div>
            <div className="shrink-0 space-y-3 border-t px-5 py-4">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="flex items-center gap-2"
                onClick={() => {
                  setExpandedDiscount(String(modalItem.discounts?.length ?? 0));
                  addDiscount(discountModalIndex);
                }}
                disabled={readonly || modalInvalid}
              >
                <Icon icon="hugeicons:plus-sign" className="h-4 w-4" />
                Add discount
              </Button>

              {modalInvalid && (
                <p className="text-center text-xs text-destructive">
                  Fix or remove the highlighted discounts to continue.
                </p>
              )}

              <Button
                type="button"
                className="w-full"
                onClick={() => setDiscountModalIndex(null)}
                disabled={modalInvalid}
              >
                Done
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
      {previewError && <p className="mt-2 text-sm text-destructive">{previewError}</p>}
      {showTaxPricingDetails && (
        <div className="mt-4 ml-auto w-full max-w-sm rounded-md border bg-muted/20 p-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Subtotal{taxesAreInclusive ? " (incl. tax)" : " (excl. tax)"}
              </span>
              <span className="font-medium">
                {previewCurrency?.code ?? ""}{" "}
                {formatPreviewAmount(convertPreviewAmount(invoiceTotals.subtotal))}
              </span>
            </div>
            {totalDiscount > 0 && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Total Discount</span>
                <span className="font-medium text-destructive">
                  {previewCurrency?.code ?? ""} -
                  {formatPreviewAmount(convertPreviewAmount(totalDiscount.toFixed(2)))}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Tax Amount{taxesAreInclusive ? " (incl. in total)" : ""}
              </span>
              <span className="font-medium">
                {previewCurrency?.code ?? ""}{" "}
                {formatPreviewAmount(convertPreviewAmount(invoiceTotals.taxTotal))}
              </span>
            </div>
            <div className="border-t pt-3">
              <div className="flex items-center justify-between text-base">
                <span className="font-semibold">Total (payable)</span>
                <span className="font-bold">
                  {previewCurrency?.code ?? ""}{" "}
                  {formatPreviewAmount(convertPreviewAmount(invoiceTotals.grossTotal))}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
