"use client";

import {Icon} from "@iconify/react";
import {useParams} from "next/navigation";
import {useEffect, useState} from "react";
import {
  PAYMENT_TERMS_API,
  VENDOR_BILLS_API,
  VENDOR_PURCHASE_ORDERS_API,
  VENDORS_API,
} from "#/_api/api.helpers";
import PageLayout from "#/_components/common/layouts/page-layout";
import {PaginatedSearchableSelect} from "#/_components/custom/paginated-searchable-select";
import {useToast} from "#/_hooks/use-toast";
import {Currency, IVendorBill, IVendorBillFormData} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {Label} from "@/components/ui/label";
import {Textarea} from "@/components/ui/textarea";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import UnifiedLineItemsInput, {
  UnifiedLineItem,
} from "#/_components/custom/purchases/unified-line-items-inputs";
import {useSelector} from "react-redux";
import {selectSelectedInstitution} from "@/store/auth/selectors";

export default function VendorBillEditPage() {
  const router = useRouter();
  const params = useParams();
  const {toast} = useToast();
  const currentInstitution = useSelector(selectSelectedInstitution);

  const [bill, setBill] = useState<IVendorBill | null>(null);
  const [unifiedLineItems, setUnifiedLineItems] = useState<UnifiedLineItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const billId = params.id as string;
  const [vendorUUID, setVendorUUID] = useState("");

  const [formData, setFormData] = useState<IVendorBillFormData>({
    vendor: "" as any,
    purchase_order: "" as any,
    description: "",
    payment_terms: undefined,
    other_expenses: [],
  });

  const setField = (field: string, value: any) => {
    setFormData((prev) => ({...prev, [field]: value}));
    if (errors[field]) {
      setErrors((prev) => ({...prev, [field]: ""}));
    }
  };

  // Map fetched bill line items → UnifiedLineItem[]
  const mapBillToUnifiedItems = (response: IVendorBill): UnifiedLineItem[] => {
    const inventoryItems = (response.inventory_line_items ?? []).map((i: any) => ({
      type: i.inventory_item?.item_type === "SERVICES"
              ? "service" as const
              : "inventory" as const,
      line_item: i.inventory_item?.base_uuid ?? String(i.id),
      item_name: i.inventory_item?.item_name ?? "",
      quantity: Number(i.quantity),
      unit_price: String(i.unit_price),
      line_total: String(i.line_total),
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
    }));

    const otherItems = (response.other_line_items ?? []).map((i: any) => ({
      type: "other" as const,
      line_item: i.line_item_name ?? String(i.id),
      item_name: i.line_item_name ?? "",
      quantity: Number(i.quantity),
      unit_price: String(i.unit_price),
      line_total: String(i.line_total),
      selected_uom_abbreviation: i.other_asset_unit_of_measure ?? "",
      applicable_taxes: (i.line_item_tax_breakdowns ?? []).map((t: any) => ({
        tax: t.tax?.base_uuid,
        is_inclusive: false,
      })),
    }));

    const fixedAssetItems = (response.fixed_asset_line_items ?? []).map((i: any) => ({
      type: "fixed_asset" as const,
      line_item: i.line_item_name ?? String(i.id),
      item_name: i.line_item_name ?? "",
      quantity: Number(i.quantity),
      unit_price: String(i.unit_price),
      line_total: String(i.line_total),
      asset_category: i.asset_category?.base_uuid,
      categoryData: i.asset_category ?? undefined,  
      applicable_taxes: (i.line_item_tax_breakdowns ?? []).map((t: any) => ({
        tax: t.tax?.base_uuid,
        is_inclusive: false,
      })),
    }));

    const expenseItems = (response.order_expenses ?? []).map((i: any) => ({
      type: "other_expense" as const,
      line_item: i.expense_name ?? String(i.id),
      item_name: i.expense_name ?? "",
      expense_name: i.expense_name ?? "",
      quantity: 1,
      unit_price: String(i.amount),
      line_total: String(i.amount),
      account_to_record_expense: i.account_to_record_expense?.base_uuid ?? "",
      applicable_taxes: (i.line_item_tax_breakdowns ?? []).map((t: any) => ({
        tax: t.tax?.base_uuid,
        is_inclusive: false,
      })),
    }));

    return [...inventoryItems, ...otherItems, ...fixedAssetItems, ...expenseItems];
  };

  const fetchBill = async () => {
    if (!billId) return;
    setIsLoading(true);
    try {
      const response = await VENDOR_BILLS_API.fetchVendorBillById({billUuid: billId});
      setBill(response);

      setUnifiedLineItems(mapBillToUnifiedItems(response));

      setFormData((prev) => ({
        ...prev,
        vendor: response.vendor?.base_uuid ?? response.purchase_order?.vendor?.base_uuid ?? "",
        purchase_order: response.purchase_order?.base_uuid ?? "",
        payment_terms: response.payment_terms?.base_uuid ?? response.payment_terms?.id?.toString(),
        description: response.description ?? "",
        other_expenses: [],
      }));

      if (response.vendor?.base_uuid) {
        setVendorUUID(response.vendor.base_uuid);
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to fetch bill details",
        variant: "destructive",
      });
      router.push("/vendor-bills");
    } finally {
      setIsLoading(false);
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.vendor && !formData.purchase_order) {
      newErrors.vendor = "A vendor or purchase order is required";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const inventoryItems = unifiedLineItems.filter(
        (i) => i.type === "inventory" || i.type === "service",
      );
      const otherItems = unifiedLineItems.filter((i) => i.type === "other");
      const fixedAssetItems = unifiedLineItems.filter((i) => i.type === "fixed_asset");
      const expenseItems = unifiedLineItems.filter((i) => i.type === "other_expense");

      await VENDOR_BILLS_API.updateVendorBill({
        billUuid: billId,
        billData: {
          ...(formData.purchase_order
            ? {purchase_order: formData.purchase_order}
            : formData.vendor
              ? {vendor: formData.vendor}
              : {}),
          ...(formData.description && {description: formData.description}),
          ...(formData.payment_terms ? {payment_terms: formData.payment_terms} : {}),
          ...(inventoryItems.length
            ? {
                inventory_line_items: inventoryItems.map((i) => ({
                  line_item: String(i.line_item),
                  unit_of_measure: i.selected_uom_uuid ?? String(i.unit_of_measure),
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
        } as any,
      });

      toast({title: "Success", description: "Vendor bill updated successfully"});
      router.push(`/vendor-bills/${billId}`);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to update vendor bill",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    fetchBill();
  }, [billId]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-4 bg-gray-200 animate-pulse rounded" />
        ))}
      </div>
    );
  }

  if (!bill) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">Bill not found</p>
        <Button onClick={() => router.push("/vendor-bills")} className="mt-4">
          Back to Vendor Bills
        </Button>
      </div>
    );
  }

  return (
    <PageLayout>
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="icon"
          className="rounded-full"
          onClick={() => router.push(`/vendor-bills/${billId}`)}
        >
          <Icon icon="hugeicons:arrow-left-02" className="size-5" />
        </Button>
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold">Edit Bill {bill.reference_code || "-"}</h1>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 mt-6">
        {/* Basic Information */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="vendor">Vendor</Label>
            <PaginatedSearchableSelect
              idKey="base_uuid"
              valueKey="base_uuid"
              labelKey="vendor_name"
              labelDescKey="address"
              value={formData.vendor ? String(formData.vendor) : undefined}
              initialData={
                bill.vendor
                  ? [bill.vendor]
                  : bill.purchase_order?.vendor
                    ? [bill.purchase_order.vendor]
                    : []
              }
              fetchFirstPage={VENDORS_API.fetchVendors}
              fetchFromUrl={VENDORS_API.fetchVendorsFromUrl}
              onValueChange={(list) => setField("vendor", list[0] || "")}
              onItemSelected={(item) => item && setVendorUUID(item.base_uuid)}
              placeholder="Select vendor"
              emptyMessage="No vendors found"
              searchPlaceholder="Search vendor..."
            />
            {errors.vendor && <p className="text-sm text-red-600">{errors.vendor}</p>}
          </div>

          <div>
            <Label htmlFor="vendor-po">Purchase Order</Label>
            <PaginatedSearchableSelect
              idKey="base_uuid"
              valueKey="base_uuid"
              labelKey="reference_code"
              labelDescKey="status"
              value={formData.purchase_order ? String(formData.purchase_order) : undefined}
              initialData={bill.purchase_order ? [bill.purchase_order] : []}
              query={{vendor_base_uuid: vendorUUID}}
              fetchFirstPage={VENDOR_PURCHASE_ORDERS_API.fetchVendorPurchaseOrders}
              fetchFromUrl={VENDOR_PURCHASE_ORDERS_API.fetchVendorPurchaseOrdersFromUrl}
              onValueChange={(list) => setField("purchase_order", list[0] || null)}
              placeholder="Select purchase order"
              emptyMessage="No purchase orders found"
              searchPlaceholder="Search purchase order..."
            />
          </div>

          <div>
            <Label>Payment Terms</Label>
            <PaginatedSearchableSelect
              idKey="base_uuid"
              valueKey="base_uuid"
              labelKey="term_name"
              value={formData.payment_terms ? String(formData.payment_terms) : undefined}
              initialData={bill.payment_terms ? [bill.payment_terms] : []}
              fetchFirstPage={PAYMENT_TERMS_API.fetchPaymentTerms}
              fetchFromUrl={PAYMENT_TERMS_API.fetchPaymentTermsFromUrl}
              onValueChange={(list) => setField("payment_terms", list[0] || null)}
              placeholder="Select payment terms"
              emptyMessage="No payment terms found"
              searchPlaceholder="Search payment terms..."
            />
          </div>
        </div>

        {/* Unified Line Items */}
        <UnifiedLineItemsInput
          initialItems={unifiedLineItems}
          onItemsChange={(items) => setUnifiedLineItems(items)}
          withTaxes
          taxEnabledTypes={["other", "fixed_asset", "other_expense"]}
          currency={bill.currency as Currency}
          previewCurrency={
            currentInstitution?.currency &&
            bill.currency?.id !== currentInstitution.currency.id
              ? currentInstitution.currency
              : null
          }
          allowedTypes={["inventory", "service", "other", "fixed_asset", "other_expense"]}
        />

        <div className="space-y-2 lg:col-span-2">
          <Label htmlFor="description" showOptional>
            Notes
          </Label>
          <Textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData((prev) => ({...prev, description: e.target.value}))}
            placeholder="Enter bill notes"
            rows={3}
          />
        </div>

        {/* Form Actions */}
        <div className="flex justify-start gap-2 pt-12">
          <Button type="submit" disabled={isSubmitting} className="w-1/2 rounded-full h-12">
            {isSubmitting ? "Updating..." : "Update Bill"}
          </Button>
        </div>
      </form>
    </PageLayout>
  );
}
