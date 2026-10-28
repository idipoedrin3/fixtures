"use client";

import {Icon} from "@iconify/react";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {useSelector} from "react-redux";
import {
  BRANCHES_API,
  INVOICES_API,
  PAYMENT_TERMS_API,
  VENDOR_BILLS_API,
  VENDOR_PURCHASE_ORDERS_API,
  VENDORS_API,
} from "#/_api/api.helpers";
import FormSection from "#/_components/common/form-section";
import {type SaveAction, SaveActionButton} from "#/_components/common/save-action-button";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import TaxPicker from "#/_components/custom/tax-picker";
import {useToast} from "#/_hooks/use-toast";
import {IVendor, IVendorBillFormData, IVendorPurchaseOrder} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {Label} from "@/components/ui/label";
import {Switch} from "@/components/ui/switch";
import {Textarea} from "@/components/ui/textarea";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {useSearchParams} from "next/navigation";
import UnifiedLineItemsInput, {
  UnifiedLineItem,
} from "#/_components/custom/purchases/unified-line-items-inputs";
import React from "react";
import {CreateVendorPanel} from "#/_components/common/create-vendor-panel";
import ExchangeRateInput from "#/_components/custom/exchange-rate-input";
import {IExchangeRateInput} from "#/_api/services/system.service";

export default function VendorBillCreatePage() {
  const router = useRouter();
  const {toast} = useToast();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [billTaxes, setBillTaxes] = useState(false);
  const [poSelectionCount, setPoSelectionCount] = useState(0);
  const [unifiedLineItems, setUnifiedLineItems] = useState<UnifiedLineItem[]>([]);
  const searchParams = useSearchParams();
  const purchaseOrderId = searchParams.get("purchaseOrderId");
  const [vendorUUID, setVendorUUID] = useState("");
  const expenseItems = unifiedLineItems.filter((i) => i.type === "other_expense");
  const [hasPurchaseOrder, setHasPurchaseOrder] = useState(!!purchaseOrderId);
  const [loading, setLoading] = useState(!!purchaseOrderId);
  const [showCreateVendor, setShowCreateVendor] = useState(false);
  const [vendor, setVendor] = useState<IVendor | null>(null);
  const [selectedVendor, setSelectedVendor] = useState<IVendor | null>(null);
  const [preselectedVendorLabel, setPreselectedVendorLabel] = useState<string | undefined>();
  const [formData, setFormData] = useState<IVendorBillFormData>({
    vendor: undefined,
    purchase_order: undefined,
    branch: undefined,
    description: "",
    payment_terms: undefined,
    other_expenses: [],
    inventory_line_items: [],
    other_line_items: [],
    fixed_asset_line_items: [],
  });
  const lastPrefillId = useRef<string | null>(null);
  const setField = (field: string, value: any) => {
    setFormData((prev) => ({...prev, [field]: value}));
    if (errors[field]) {
      setErrors((prev) => ({...prev, [field]: ""}));
    }
  };
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [prefillPO, setPrefillPO] = useState<IVendorPurchaseOrder | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<any>(null);
  const fromDuplicate = searchParams.get("from") === "duplicate";
  const dupKey = searchParams.get("dup");
  const vendorIdFromQuery = searchParams.get("vendor_id");
  const vendorUuidFromQuery = searchParams.get("vendor_uuid");
  const documentCurrency =
    prefillPO?.currency ?? vendor?.currency ?? currentInstitution?.currency ?? null;
  const isForeignCurrencyOrder = useMemo(
    () =>
      !!documentCurrency &&
      !!currentInstitution?.currency &&
      documentCurrency.id !== currentInstitution.currency.id,
    [currentInstitution?.currency, documentCurrency],
  );

  const handleExchangeRateChange = useCallback((exchangeRate: IExchangeRateInput | undefined) => {
    setFormData((previous) => ({...previous, exchange_rate: exchangeRate}));
  }, []);

  useEffect(() => {
    if (!vendorIdFromQuery || !vendorUuidFromQuery) return;

    const prefillVendor = async () => {
      try {
        const vendorData = await VENDORS_API.fetchVendorById({baseUuuid: vendorUuidFromQuery});
        setVendor(vendorData);
        setSelectedVendor(vendorData);
        setPreselectedVendorLabel(vendorData.vendor_name);
        setFormData((prev) => ({...prev, vendor: vendorData.id as any}));
      } catch (error) {}
    };

    prefillVendor();
  }, [vendorIdFromQuery, vendorUuidFromQuery]);

  useEffect(() => {
    if (!fromDuplicate || !dupKey) return;
    let cancelled = false;

    const hydrateDuplicate = async () => {
      setLoading(true);
      try {
        const [source, itemResponse] = await Promise.all([
          VENDOR_BILLS_API.fetchVendorBillById({billUuid: dupKey}),
          VENDOR_BILLS_API.fetchLineItems({billUuid: dupKey}),
        ]);
        if (cancelled) return;

        const unified: UnifiedLineItem[] = [
          ...(itemResponse.line_items ?? []).map((item: any) => ({
            type: item.item_type === "inventory" && item.inventory_item?.item_type === "SERVICES"
              ? "service" as const
              : item.item_type as "inventory" | "other" | "fixed_asset",
            line_item:
              item.item_type === "inventory"
                ? (item.inventory_item?.base_uuid ?? "")
                : (item.line_item_name ?? ""),
            item_name:
              item.inventory_item?.item_name ??
              item.line_item_name ??
              item.asset_category?.category_name ??
              "",
            quantity: Number(item.quantity) || 1,
            unit_price: "0",
            net_unit_price: "0",
            tax_unit_price: "0",
            display_unit_price: "0",
            line_total: "0",
            selected_uom_uuid: item.unit_of_measure?.base_uuid ?? "",
            selected_uom_abbreviation:
              item.unit_of_measure?.unit_name ?? item.other_asset_unit_of_measure ?? "",
            unit_of_measure:
              item.unit_of_measure?.base_uuid ?? item.other_asset_unit_of_measure ?? "",
            asset_category: item.asset_category?.base_uuid ?? "",
            item:
              item.item_type === "inventory"
                ? {
                    id: item.inventory_item?.id,
                    base_uuid: item.inventory_item?.base_uuid,
                    item_name: item.inventory_item?.item_name ?? "",
                    inventory_item_units_of_measure: item.unit_of_measure
                      ? [
                          {
                            base_uuid: item.unit_of_measure.base_uuid,
                            is_base_unit_of_measure: true,
                            selling_price: 0,
                            unit_of_measure: {
                              id: item.unit_of_measure.id,
                              unit_name: item.unit_of_measure.unit_name,
                              unit_abbreviation: item.unit_of_measure.unit_name,
                            },
                          },
                        ]
                      : [],
                  }
                : undefined,
          })),
          ...(itemResponse.expenses ?? []).map((expense: any) => ({
            type: "other_expense" as const,
            line_item: expense.expense_name ?? "",
            item_name: expense.expense_name ?? "",
            expense_name: expense.expense_name ?? "",
            account_to_record_expense: expense.account_to_record_expense?.base_uuid ?? "",
            quantity: 1,
            unit_price: "0",
            net_unit_price: "0",
            tax_unit_price: "0",
            display_unit_price: "0",
            line_total: "0",
          })),
        ];

        const sourceVendor = source.vendor ?? null;
        setVendor(sourceVendor);
        setSelectedVendor(sourceVendor);
        setPreselectedVendorLabel(sourceVendor?.vendor_name);
        setPrefillPO(null);
        setSelectedBranch(null);
        setHasPurchaseOrder(false);
        setUnifiedLineItems(unified);
        setPoSelectionCount((count) => count + 1);
        setFormData((previous) => ({
          ...previous,
          vendor: sourceVendor?.base_uuid,
          purchase_order: undefined,
          branch: undefined,
          description: "",
          payment_terms: undefined,
          other_expenses: [],
          inventory_line_items: [],
          other_line_items: [],
          fixed_asset_line_items: [],
        }));
      } catch {
        if (!cancelled) {
          toast({
            title: "Error",
            description: "Failed to duplicate vendor bill",
            variant: "destructive",
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void hydrateDuplicate();
    return () => {
      cancelled = true;
    };
  }, [dupKey, fromDuplicate, toast]);

  const fetchVendorPurchaseOrders = React.useCallback(
    async (q: any) =>
      await VENDOR_PURCHASE_ORDERS_API.fetchVendorPurchaseOrders({
        ...q,
        get_only_not_full_billed: true,
        only_approved: true,
      }),
    [],
  );

  const fetchPurchaseOrderWithItems = async (
    purchaseOrderUuid: string,
  ): Promise<IVendorPurchaseOrder> => {
    const [purchaseOrder, lineItemResponse] = await Promise.all([
      VENDOR_PURCHASE_ORDERS_API.fetchVendorPurchaseOrderById({purchaseOrderUuid}),
      VENDOR_PURCHASE_ORDERS_API.fetchLineItems({purchaseOrderUuid}),
    ]);
    const lineItems = lineItemResponse.results ?? [];

    return {
      ...purchaseOrder,
      inventory_items: lineItems.filter((item: any) => item.item_type === "inventory"),
      other_items: lineItems.filter((item: any) => item.item_type === "other"),
      fixed_asset_items: lineItems.filter((item: any) => item.item_type === "fixed_asset"),
    };
  };

  const buildUnifiedFromPO = async (po: IVendorPurchaseOrder): Promise<UnifiedLineItem[]> => {
    const calculateInventoryTaxPricing = async (item: {
      unit_price: string;
      inventory_item?: {base_uuid?: string};
    }) => {
      const fallback = {
        netAmount: item.unit_price,
        taxAmount: "0",
        grossAmount: item.unit_price,
      };

      if (!item.inventory_item?.base_uuid) return fallback;

      try {
        const response = await INVOICES_API.previewTaxCalculation({
          amount: parseFloat(item.unit_price).toFixed(2),
          base_uuid: item.inventory_item.base_uuid,
          type: "purchase",
        });

        return {
          netAmount: response.net_amount.toString(),
          taxAmount: response.tax_amount.toString(),
          grossAmount: response.gross_amount.toString(),
        };
      } catch {
        return fallback;
      }
    };

    const calculateCopiedTaxPricing = async (item: {
      unit_price: string;
      line_item_tax_breakdowns?: any[];
    }) => {
      const applicableTaxes = (item.line_item_tax_breakdowns ?? [])
        .map((breakdown: any) => ({
          tax: breakdown.tax?.base_uuid,
          is_inclusive: breakdown.is_inclusive,
        }))
        .filter((tax: {tax?: string}) => !!tax.tax);

      const fallback = {
        netAmount: item.unit_price,
        taxAmount: "0",
        grossAmount: item.unit_price,
        applicableTaxes,
      };

      if (!applicableTaxes.length) return fallback;

      try {
        const response = await INVOICES_API.previewTaxCalculation({
          amount: parseFloat(item.unit_price).toFixed(2),
          applicable_taxes: applicableTaxes,
        });

        return {
          netAmount: response.net_amount.toString(),
          taxAmount: response.tax_amount.toString(),
          grossAmount: response.gross_amount.toString(),
          applicableTaxes,
        };
      } catch {
        return fallback;
      }
    };

    const inventoryItems = await Promise.all(
      (po.inventory_items ?? []).map(async (i) => {
        const pricing = await calculateInventoryTaxPricing(i);

        return {
          type: i.inventory_item?.item_type === "SERVICES"
              ? "service" as const
              : "inventory" as const,
          line_item: i.inventory_item?.base_uuid ?? String(i.id),
          item_name: i.inventory_item?.item_name ?? "",
          quantity: i.quantity,
          unit_price: i.unit_price,
          net_unit_price: pricing.netAmount,
          tax_unit_price: pricing.taxAmount,
          display_unit_price: pricing.grossAmount,
          line_total: (Number(i.quantity) * parseFloat(pricing.grossAmount)).toFixed(2),
          applicable_taxes: [],
          selected_uom_uuid: i.unit_of_measure?.base_uuid,
          unit_of_measure: i.unit_of_measure?.base_uuid,
          item: {
            id: i.inventory_item?.id,
            base_uuid: i.inventory_item?.base_uuid,
            item_name: i.inventory_item?.item_name ?? "",
            inventory_item_units_of_measure: i.unit_of_measure
              ? [
                  {
                    base_uuid: i.unit_of_measure.base_uuid,
                    is_base_unit_of_measure: true,
                    selling_price: i.unit_price,
                    unit_of_measure: {
                      id: i.unit_of_measure.id,
                      unit_name: i.unit_of_measure.unit_name,
                      unit_abbreviation: i.unit_of_measure.unit_name,
                    },
                  },
                ]
              : [],
          } as any,
        };
      }),
    );

    const otherItems = await Promise.all(
      (po.other_items ?? []).map(async (i) => {
        const pricing = await calculateCopiedTaxPricing(i);

        return {
          type: "other" as const,
          line_item: i.line_item_name,
          item_name: i.line_item_name,
          quantity: i.quantity,
          unit_price: i.unit_price,
          net_unit_price: pricing.netAmount,
          tax_unit_price: pricing.taxAmount,
          display_unit_price: pricing.grossAmount,
          line_total: (Number(i.quantity) * parseFloat(pricing.grossAmount)).toFixed(2),
          selected_uom_abbreviation: i.other_unit_of_measure,
          applicable_taxes: pricing.applicableTaxes,
        };
      }),
    );

    const fixedAssetItems = await Promise.all(
      (po.fixed_asset_items ?? []).map(async (i) => {
        const pricing = await calculateCopiedTaxPricing(i);

        return {
          type: "fixed_asset" as const,
          line_item: i.line_item_name,
          item_name: i.line_item_name,
          quantity: i.quantity,
          unit_price: i.unit_price,
          net_unit_price: pricing.netAmount,
          tax_unit_price: pricing.taxAmount,
          display_unit_price: pricing.grossAmount,
          line_total: (Number(i.quantity) * parseFloat(pricing.grossAmount)).toFixed(2),
          asset_category: i.asset_category?.base_uuid,
          applicable_taxes: pricing.applicableTaxes,
        };
      }),
    );

    return [
      ...inventoryItems,
      ...otherItems,
      ...fixedAssetItems,
    ];
  };

  useEffect(() => {
    if (!purchaseOrderId) return;
    if (lastPrefillId.current === purchaseOrderId) return;
    lastPrefillId.current = purchaseOrderId;
    let cancelled = false;

    const prefill = async () => {
      setLoading(true);
      try {
        const po = await fetchPurchaseOrderWithItems(purchaseOrderId);
        if (cancelled) return;
        const unified = await buildUnifiedFromPO(po);
        if (cancelled) return;
        setUnifiedLineItems(unified);
        setPoSelectionCount((c) => c + 1);
        setPrefillPO(po);
        setHasPurchaseOrder(true);
        setFormData((prev) => ({
          ...prev,
          vendor: po.vendor?.base_uuid ?? prev.vendor,
          purchase_order: po.base_uuid,
          branch: po.branch?.base_uuid,
        }));
        setSelectedBranch(po?.branch ?? null);
      } catch (error) {
        if (!cancelled)
          toast({
            title: "Error",
            description: "Failed to load purchase order data",
            variant: "destructive",
          });
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    prefill();
    return () => {
      cancelled = true;
      lastPrefillId.current = null;
    };
  }, [purchaseOrderId]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.purchase_order && !formData.vendor) {
      newErrors.vendor = "Vendor is required when you didn't make a purchase order for this bill";
    }
    if (hasPurchaseOrder && !formData.purchase_order) {
      newErrors.purchase_order =
        "Purchase order is required when you have selected a purchase order";
    }

    unifiedLineItems.forEach((item, index) => {
      if (item.type !== "inventory" && item.type !== "service") return;

      const inventoryItemUuid =
        item.item?.base_uuid ??
        (typeof item.line_item === "string" ? item.line_item : undefined);
      const unitOfMeasureUuid =
        item.selected_uom_uuid ??
        (typeof item.unit_of_measure === "string" ? item.unit_of_measure : undefined);

      if (!inventoryItemUuid) {
        newErrors[`line_item_${index}`] =
          item.type === "service" ? "Service is required" : "Inventory item is required";
      }

      if (!unitOfMeasureUuid) {
        newErrors[`unit_of_measure_${index}`] = "Unit of measure is required";
      }
    });

    (formData.other_expenses ?? []).forEach((expense, index) => {
      if (!expense.expense_name.trim()) {
        newErrors[`name_${index}`] = "Expense name is required";
      }
      if (!expense.amount || parseFloat(expense.amount + "") <= 0) {
        newErrors[`amount_${index}`] = "Amount must be greater than 0";
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (
    event?: React.FormEvent<HTMLFormElement>,
    action: SaveAction = "save-and-view",
  ) => {
    event?.preventDefault();

    if (!validateForm()) return;

    if (!currentInstitution) {
      toast({
        title: "Error",
        description: "No institution selected",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const inventoryItems = unifiedLineItems.filter(
        (i) => i.type === "inventory" || i.type === "service",
      );
      const otherItems = unifiedLineItems.filter((i) => i.type === "other");
      const fixedAssetItems = unifiedLineItems.filter((i) => i.type === "fixed_asset");

      const response = await VENDOR_BILLS_API.createVendorBill({
        billData: {
          ...(formData.purchase_order
            ? {purchase_order: formData.purchase_order}
            : formData.vendor
              ? {vendor: formData.vendor}
              : {}),
          ...(formData.description && {description: formData.description}),
          ...(formData.payment_terms ? {payment_terms: formData.payment_terms} : {}),
          ...(formData.branch ? {branch: formData.branch} : {}),
          ...(isForeignCurrencyOrder && formData.exchange_rate
            ? {exchange_rate: formData.exchange_rate}
            : {}),
          ...(inventoryItems.length
            ? {
                inventory_line_items: inventoryItems.map((i) => ({
                  line_item: i.item?.base_uuid ?? (i.line_item as string),
                  unit_of_measure:
                    i.selected_uom_uuid ?? (i.unit_of_measure as string),
                  quantity: i.quantity,
                  unit_price: i.unit_price,
                })),
              }
            : {}),
          ...(otherItems.length
            ? {
                other_line_items: otherItems.map((i) => ({
                  line_item: i.item_name,
                  unit_of_measure: i.selected_uom_abbreviation || "",
                  quantity: i.quantity,
                  unit_price: i.unit_price,
                  applicable_taxes: (i.applicable_taxes ?? []).filter((t) => !!t.tax),
                })),
              }
            : {}),
          ...(fixedAssetItems.length
            ? {
                fixed_asset_line_items: fixedAssetItems.map((i) => ({
                  ...(i.item_name?.trim() && {line_item: i.item_name.trim()}),
                  asset_category: i.asset_category!,
                  quantity: i.quantity,
                  unit_price: i.unit_price,
                  applicable_taxes: (i.applicable_taxes ?? []).filter((t) => !!t.tax),
                })),
              }
            : {}),
          ...(formData.other_expenses?.length
            ? {
                other_expenses: formData.other_expenses.map((e) => ({
                  ...e,
                  applicable_taxes: (e.applicable_taxes ?? []).filter((t) => !!t.tax),
                })),
              }
            : {}),
          ...(expenseItems.length
            ? {
                other_expenses: expenseItems.map((i) => ({
                  expense_name: i.expense_name ?? i.item_name,
                  amount: i.unit_price,
                  account_to_record_expense: i.account_to_record_expense ?? "",
                  applicable_taxes: (i.applicable_taxes ?? []).filter((t) => !!t.tax),
                })),
              }
            : {}),
        },
      });

      toast({
        title: "Success",
        description: "Vendor bill created successfully",
      });

      if (action === "save-and-new") {
        window.location.assign("/vendor-bills/create");
      } else if (action === "save-and-close") {
        router.push("/vendor-bills");
      } else {
        router.push(`/vendor-bills/${response.base_uuid}`);
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to create vendor bill",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!currentInstitution) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">
          Please select an institution to create vendor bills.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 bg-white rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="icon"
          className="rounded-full"
          onClick={() => router.push("/vendor-bills")}
        >
          <Icon icon="hugeicons:arrow-left-02" className="size-5" />
        </Button>
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold">Create New Vendor Bill</h1>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-4 bg-gray-200 animate-pulse rounded" />
          ))}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          <FormSection
            title="Basic Information"
            description="Select a vendor or purchase order together with other details to create a vendor bill."
          >
            <div>
              <div className="flex items-center gap-4">
                <Label className="pt-4">Did you make an order for this bill?</Label>
                <span className="pt-4 pr-4">
                  <Switch
                    id="has-purchase-order"
                    checked={hasPurchaseOrder}
                    onCheckedChange={(checked) => setHasPurchaseOrder(checked)}
                  />
                </span>
              </div>
              <span className="text-xs md:text-sm opacity-50">
                <p>If you did not make an order, you can still create a vendor bill.</p>
              </span>
            </div>

            {!hasPurchaseOrder ? (
              <div className="">
                <Label required htmlFor="vendor">
                  Vendor
                </Label>

                <PaginatedSearchableSelect<IVendor>
                  fetchFirstPage={VENDORS_API.fetchVendors}
                  fetchFromUrl={VENDORS_API.fetchVendorsFromUrl}
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  labelKey="vendor_name"
                  labelDescKey="vendor_type"
                  value={selectedVendor?.base_uuid ? String(selectedVendor.base_uuid) : undefined}
                  initialData={selectedVendor ? [selectedVendor] : undefined}
                  initialSelectedLabel={preselectedVendorLabel}
                  onValueChange={(ids) =>
                    setFormData((prev) => ({...prev, vendor: ids.length ? ids[0] : ("" as any)}))
                  }
                  onItemSelected={(item) => {
                    setVendor(item);
                    setSelectedVendor(item);
                  }}
                  placeholder="Select vendor"
                  searchPlaceholder="Search vendors..."
                  emptyMessage="No vendors found"
                  description="Select the vendor you're placing this purchase order with."
                  createAction={{
                    label: "Create new vendor",
                    onClick: () => setShowCreateVendor(true),
                  }}
                />
                {errors.vendor && <p className="text-sm text-red-600">{errors.vendor}</p>}
              </div>
            ) : (
              <div>
                <Label required htmlFor="pooo">
                  Purchase Order
                </Label>
                <PaginatedSearchableSelect
                  key={prefillPO?.base_uuid || "no-po"}
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  labelKey="reference_code"
                  labelDescKey="status"
                  value={formData.purchase_order ? String(formData.purchase_order) : undefined}
                  initialData={prefillPO ? [prefillPO] : []}
                  query={{vendor_base_uuid: vendorUUID}}
                  fetchFirstPage={fetchVendorPurchaseOrders}
                  fetchFromUrl={VENDOR_PURCHASE_ORDERS_API.fetchVendorPurchaseOrdersFromUrl}
                  onItemSelected={async (item) => {
                    if (!item) return;
                    try {
                      const po = await fetchPurchaseOrderWithItems(item.base_uuid);

                      const unified = await buildUnifiedFromPO(po);
                      setUnifiedLineItems(unified);
                      setPoSelectionCount((c) => c + 1);
                      setPrefillPO(po);
                      setSelectedBranch(po?.branch ?? null);
                      setFormData((prev) => ({
                        ...prev,
                        purchase_order: po.base_uuid,
                        branch: po.branch?.base_uuid,
                      }));
                    } catch (error) {
                      toast({
                        title: "Error",
                        description: "Failed to load purchase order data",
                        variant: "destructive",
                      });
                    }
                  }}
                  onValueChange={(list) => {
                    const value = list[0] || null;
                    setField("purchase_order", value);
                    if (!value) {
                      setUnifiedLineItems([]);
                      setPrefillPO(null);
                      setPoSelectionCount((c) => c + 1);
                    }
                  }}
                  placeholder="Select purchase order"
                  emptyMessage="No purchase orders found"
                  searchPlaceholder="Search purchase order..."
                  description="Select a purchase order from the list below since there is an existing purchase order."
                />
                {errors.purchase_order && (
                  <p className="text-sm text-red-600">{errors.purchase_order}</p>
                )}
              </div>
            )}

            <div>
              <Label showOptional htmlFor="branch">
                Branch
              </Label>
              <PaginatedSearchableSelect
                key={selectedBranch?.base_uuid ?? "no-branch"}
                idKey="base_uuid"
                valueKey="base_uuid"
                labelKey="branch_name"
                value={formData.branch ? String(formData.branch) : undefined}
                initialData={selectedBranch ? [selectedBranch] : []}
                fetchFirstPage={BRANCHES_API.fetchAll}
                fetchFromUrl={BRANCHES_API.fetchAllFromUrl}
                labelDescKeyFn={(item) => `(${item.reference_code})`}
                onValueChange={(list) => setField("branch", list[0] || null)}
                onItemSelected={(item) => setSelectedBranch(item ?? null)}
                placeholder="Select branch"
                emptyMessage="No branches found"
                searchPlaceholder="Search branch..."
              />
            </div>
            <div>
              <Label showOptional htmlFor="payment-terms">
                Payment Terms
              </Label>
              <PaginatedSearchableSelect
                idKey="base_uuid"
                valueKey="base_uuid"
                labelKey="term_name"
                labelDescKeyFn={(item) => item.reference_code ?? ""}
                fetchFirstPage={PAYMENT_TERMS_API.fetchPaymentTerms}
                fetchFromUrl={PAYMENT_TERMS_API.fetchPaymentTermsFromUrl}
                onValueChange={(list) => setField("payment_terms", list[0] || null)}
                placeholder="Select payment terms"
                emptyMessage="No payment terms found"
                searchPlaceholder="Search payment terms..."
              />
            </div>
          </FormSection>

          {billTaxes && (
            <TaxPicker
              onChange={(taxes) => setFormData((prev) => ({...prev, applicable_taxes: taxes}))}
            />
          )}

          {isForeignCurrencyOrder && currentInstitution.currency && documentCurrency && (
            <FormSection
              title="Bill Currency"
              description="Use the configured rate or provide a custom rate for this vendor bill."
            >
              <ExchangeRateInput
                baseCurrency={currentInstitution.currency}
                transactionCurrency={documentCurrency}
                value={formData.exchange_rate ?? undefined}
                onChange={handleExchangeRateChange}
              />
            </FormSection>
          )}

          {/* Unified Line Items */}
          <div className="space-y-4 pt-4">
            <UnifiedLineItemsInput
              key={`unified-${poSelectionCount}`}
              initialItems={unifiedLineItems}
              onItemsChange={(items) => setUnifiedLineItems(items)}
              withTaxes
              taxEnabledTypes={["other", "fixed_asset", "other_expense"]}
              showPricingPreview
              calculateTaxOnUnitPrice
              currency={documentCurrency}
              previewCurrency={isForeignCurrencyOrder ? currentInstitution.currency : null}
              exchangeRate={isForeignCurrencyOrder ? formData.exchange_rate : null}
              allowedTypes={["inventory", "service", "other", "fixed_asset", "other_expense"]}
              lineItemErrors={errors}
            />
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="description" showOptional>
              Notes
            </Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData((prev) => ({...prev, description: e.target.value}))}
              placeholder="Enter bill description"
              rows={3}
            />
          </div>
          {/* Form Actions */}
          <div className="flex justify-start gap-2 pt-4">
            <SaveActionButton
              primaryLabel="Create Bill"
              pendingLabel="Creating..."
              isPending={isSubmitting}
              className="w-1/2"
              onAction={(action) => {
                void handleSubmit(undefined, action);
              }}
            />
          </div>
        </form>
      )}
      <CreateVendorPanel
        open={showCreateVendor}
        onClose={() => setShowCreateVendor(false)}
        onCreated={(id, name, newVendor) => {
          setVendor(newVendor);
          setSelectedVendor(newVendor);
          setPreselectedVendorLabel(name);
          setFormData((prev) => ({...prev, vendor: id as any}));
          setShowCreateVendor(false);
        }}
      />
    </div>
  );
}
