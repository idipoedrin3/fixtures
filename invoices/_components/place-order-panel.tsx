"use client";

import {useEffect, useState} from "react";
import {toast} from "sonner";
import {Icon} from "@iconify/react";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {SlideOverPanel} from "#/_components/common/slide-over-pannel";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import FormattedDatePicker from "#/_components/common/inputs/formatted-date-picker";
import {BILL_OF_MATERIAL_API, ORDERS_API} from "#/_api/notifications.utils";
import type {IBillOfMaterial} from "#/_types/types.utils";
import type {IInvoice} from "#/_types/api.types";

type BomOption = IBillOfMaterial & {display_name?: string};

const withDisplayName = (b: IBillOfMaterial): BomOption => ({
  ...b,
  display_name: b.inventory_item?.item_name ?? b.reference_code,
});

const PRIORITY_OPTIONS = [
  {value: "low", label: "Low"},
  {value: "normal", label: "Normal"},
  {value: "high", label: "High"},
  {value: "urgent", label: "Urgent"},
] as const;

type Priority = (typeof PRIORITY_OPTIONS)[number]["value"];

interface OrderRow {
  bill_of_material: string;
  priority: Priority;
  quantity_to_produce: number;
  issue_date: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  invoice: IInvoice;
  onCreated?: () => void;
}

const emptyRow = (): OrderRow => ({
  bill_of_material: "",
  priority: "normal",
  quantity_to_produce: 1,
  issue_date: new Date().toISOString().slice(0, 10),
});

export function PlaceOrderPanel({open, onClose, invoice, onCreated}: Props) {
  const [orders, setOrders] = useState<OrderRow[]>([emptyRow()]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [errors, setErrors] = useState<Record<number, Partial<Record<keyof OrderRow, string>>>>({});
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setOrders([emptyRow()]);
      setErrors({});
      setActiveIndex(0);
    }
  }, [open]);

  const setField = <K extends keyof OrderRow>(index: number, field: K, value: OrderRow[K]) => {
    setOrders((prev) => prev.map((row, i) => (i === index ? {...row, [field]: value} : row)));
    if (errors[index]?.[field]) {
      setErrors((prev) => ({...prev, [index]: {...prev[index], [field]: ""}}));
    }
  };

  const addOrder = () =>
    setOrders((prev) => {
      setActiveIndex(prev.length);
      return [...prev, emptyRow()];
    });

  const removeOrder = (index: number) => {
  setOrders((prev) => {
    const next = prev.filter((_, i) => i !== index);
    setActiveIndex((ai) => Math.max(0, Math.min(ai, next.length - 1)));
    return next;
  });
  setErrors((prev) => {
    const nextErrors: typeof prev = {};
    Object.entries(prev).forEach(([k, v]) => {
      const i = Number(k);
      if (i < index) nextErrors[i] = v;
      else if (i > index) nextErrors[i - 1] = v;
    });
    return nextErrors;
  });
};

  const validate = () => {
    const newErrors: Record<number, Partial<Record<keyof OrderRow, string>>> = {};
    orders.forEach((row, i) => {
      const rowErrors: Partial<Record<keyof OrderRow, string>> = {};
      if (!row.bill_of_material) rowErrors.bill_of_material = "Bill of material is required";
      if (!row.quantity_to_produce || row.quantity_to_produce < 1)
        rowErrors.quantity_to_produce = "Quantity must be at least 1";
      if (!row.issue_date) rowErrors.issue_date = "Issue date is required";
      if (Object.keys(rowErrors).length) newErrors[i] = rowErrors;
    });
    setErrors(newErrors);
    const errorIndexes = Object.keys(newErrors).map(Number);
    if (errorIndexes.length) setActiveIndex(errorIndexes[0]);
    return errorIndexes.length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setIsSaving(true);
    try {
      const payload = orders.map((row) => ({
        bill_of_material: row.bill_of_material,
        quantity_to_produce: row.quantity_to_produce,
        priority: row.priority,
        issue_date: new Date(row.issue_date).toISOString(),
        ...(invoice.customer?.base_uuid ? {client: invoice.customer.base_uuid} : {}),
        ...(invoice.branch?.base_uuid ? {branch: invoice.branch.base_uuid} : {}),
      }));

      await ORDERS_API.createOrders({data: payload});
      toast.success(
        payload.length > 1
          ? `${payload.length} manufacturing orders placed successfully`
          : "Manufacturing order placed successfully",
      );
      onCreated?.();
      onClose();
    } catch (error: any) {
      toast.error(error?.response?.data?.message || "Failed to place order");
    } finally {
      setIsSaving(false);
    }
  };

  const uomCombinations = (invoice.line_items ?? [])
    .map((li: any) => ({
      inventory_item_uuid: li.branch_item?.inventory_item?.base_uuid,
      inventory_item_unit_of_measure_uuid:
        li.unit_of_measure?.inventory_item_unit_of_measure?.base_uuid ??
        li.unit_of_measure?.base_uuid,
    }))
    .filter(
      (c: {inventory_item_uuid?: string; inventory_item_unit_of_measure_uuid?: string}) =>
        c.inventory_item_uuid && c.inventory_item_unit_of_measure_uuid,
    );

  const canFilterBoms = uomCombinations.length > 0;

  const activeOrder = orders[activeIndex];

  return (
    <SlideOverPanel
      open={open}
      onClose={() => !isSaving && onClose()}
      title="Place Order"
      description={`Create manufacturing orders for ${invoice.customer?.customer_name ?? "this invoice"}.`}
      onSubmit={handleSubmit}
      submitLabel={orders.length > 1 ? `Place ${orders.length} Orders` : "Place Order"}
      isSubmitting={isSaving}
      width="md"
      closeOnOutsideClick={false}
    >
      <div className="space-y-4">
        {/* Order tabs */}
        <div className="flex flex-wrap items-center gap-2">
          {orders.map((_, index) => (
            <Button
              key={index}
              type="button"
              variant={index === activeIndex ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveIndex(index)}
              className={`rounded-full ${
                errors[index] && Object.values(errors[index]).some(Boolean)
                  ? "border-red-400 text-red-500"
                  : ""
              }`}
            >
              Order {index + 1}
            </Button>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addOrder}
            className="rounded-full flex items-center gap-1"
          >
            <Icon icon="hugeicons:plus-sign" className="h-4 w-4" />
            Add Order
          </Button>
          {orders.length > 1 && (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => removeOrder(activeIndex)}
              className="rounded-full flex items-center gap-1"
            >
              <Icon icon="hugeicons:delete-02" className="h-4 w-4" />
              Remove Current
            </Button>
          )}
        </div>

        {/* Active order form */}
        {activeOrder && (
          <div className="space-y-1">
            <div>
              <h3 className="font-semibold">Order {activeIndex + 1} Details</h3>
              <p className="text-sm text-muted-foreground">
                Define this manufacturing order&apos;s details.
              </p>
            </div>

            <div className="space-y-4 pt-3">
              <div className="space-y-2">
                <Label required>Bill of Material</Label>
                <PaginatedSearchableSelect<BomOption>
                  fetchFirstPage={async (args) => {
                    if (!canFilterBoms) {
                      return {count: 0, next: null, previous: null, results: []};
                    }
                    const res = await BILL_OF_MATERIAL_API.fetchBillOfMaterials({
                      ...args,
                      inventory_item_uom_combinations: uomCombinations,
                    });
                    return {...res, results: (res.results ?? []).map(withDisplayName)};
                  }}
                  fetchFromUrl={async ({url}) => {
                    const res = await BILL_OF_MATERIAL_API.fetchBillOfMaterialsFromUrl({url});
                    return {...res, results: (res.results ?? []).map(withDisplayName)};
                  }}
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  labelKey="reference_code"
                  labelDescKey="display_name"
                  value={activeOrder.bill_of_material || undefined}
                  onValueChange={(ids) =>
                    setField(activeIndex, "bill_of_material", String(ids[0] ?? ""))
                  }
                  placeholder="Select bill of material"
                  searchPlaceholder="Search BOMs..."
                  emptyMessage={
                    canFilterBoms
                      ? "No bills of material match this invoice's items"
                      : "Item details are unavailable for this invoice, so matching BOMs can't be loaded"
                  }
                />
                {errors[activeIndex]?.bill_of_material && (
                  <p className="text-sm text-red-500">{errors[activeIndex].bill_of_material}</p>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-1 gap-4">
                <div className="space-y-2">
                  <Label required>Quantity to Produce</Label>
                  <Input
                    type="number"
                    min={1}
                    value={activeOrder.quantity_to_produce || ""}
                    onChange={(e) =>
                      setField(
                        activeIndex,
                        "quantity_to_produce",
                        e.target.value === "" ? 0 : Number(e.target.value),
                      )
                    }
                    onBlur={() => {
                      if (!activeOrder.quantity_to_produce || activeOrder.quantity_to_produce < 1) {
                        setField(activeIndex, "quantity_to_produce", 1);
                      }
                    }}
                    placeholder="1"
                  />
                  {errors[activeIndex]?.quantity_to_produce && (
                    <p className="text-sm text-red-500">
                      {errors[activeIndex].quantity_to_produce}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label required>Priority</Label>
                  <Select
                    value={activeOrder.priority}
                    onValueChange={(val) => setField(activeIndex, "priority", val as Priority)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select priority" />
                    </SelectTrigger>
                    <SelectContent className="z-[1000]">
                      {PRIORITY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <FormattedDatePicker
                  value={activeOrder.issue_date}
                  onChange={(value) => setField(activeIndex, "issue_date", value || "")}
                  id={`place-order-issue-date-${activeIndex}`}
                  label="Issue Date"
                  required
                  showAsterisk
                  limitMaxWidth={false}
                  inputClassName="w-full bg-card border-border/50 h-10"
                />
                {errors[activeIndex]?.issue_date && (
                  <p className="text-sm text-red-500">{errors[activeIndex].issue_date}</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </SlideOverPanel>
  );
}
