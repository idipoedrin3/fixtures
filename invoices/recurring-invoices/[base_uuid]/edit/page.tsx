"use client";

import {useState, useEffect, useCallback} from "react";
import {useParams, useRouter} from "next/navigation";
import {useSelector} from "react-redux";
import {Icon} from "@iconify/react";
import {format} from "date-fns";
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
import {useToast} from "#/_hooks/use-toast";
import {showErrorToast} from "#/_lib/utils";
import {RECURRING_INVOICES_API} from "#/_api/api.helpers";
import {
  IRecurringInvoice,
  IRecurringInvoiceFormData,
  IRecurringInvoiceLineItem,
} from "#/_types/api.types";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import PageLayout from "#/_components/common/layouts/page-layout";
import LineItemsInput from "#/_components/custom/sales/line-items-input";
import FormSection from "#/_components/common/form-section";
import React from "react";
import { ChipMultiSelect } from "../../_components/chip-multi-select";
import { DAY_OPTIONS, MONTH_OPTIONS, WEEK_OPTIONS } from "../../_components/option-constants";

type RecurringFrequency = "daily" | "weekly" | "monthly" | "biannual" | "annual";

export default function RecurringInvoiceEditPage() {
  const router = useRouter();
  const params = useParams();
  const {toast} = useToast();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [recurringInvoice, setRecurringInvoice] = useState<IRecurringInvoice | null>(null);
  

  const [formData, setFormData] = useState<IRecurringInvoiceFormData>({
    customer: 0,
    recurring_frequency: "monthly",
    start_date: new Date().toISOString().split("T")[0],
    end_date: null,
    recurring_items: [],
    name: "",
    notes: "",
    description: "",
    weekdays: [],
    week_of_month: [],
    months: [],
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const base_uuid = params.base_uuid as string;

  const fetchRecurringInvoice = useCallback(async () => {
    if (!base_uuid) return;

    setIsLoading(true);
    try {
      const response = await RECURRING_INVOICES_API.fetchRecurringInvoiceById({base_uuid});

      setRecurringInvoice(response);

      setFormData({
        customer: response.customer.id,
        recurring_frequency: response.recurring_frequency,
        start_date: response.start_date,
        end_date: response.end_date || null,
        name: response.name || "",
        notes: response.notes || "",
        description: response.description || "",
        weekdays: response.weekdays ?? [],
        week_of_month: response.week_of_month ?? [],
        months: response.months ?? [],
        recurring_items: response.recurring_items.map((item: IRecurringInvoiceLineItem) => {
          const quantity = parseFloat(item.quantity || "0");
          const unitCost = parseFloat(item.unit_cost || "0");

          return {
            line_item: item.line_item?.base_uuid ?? "",
            item_name: item.line_item?.item_name ?? "",
            item_category: "",
            quantity: quantity,
            unit_cost: item.unit_cost || "0.00",
            line_total: (quantity * unitCost).toFixed(2),
            unit_of_measure: item.unit_of_measure?.id?.toString() || "",
            item: {
                id: item.line_item?.id,
                base_uuid: item.line_item?.base_uuid,
                inventory_item: {
                  item_name: item.line_item?.item_name ?? "",
                  item_code: item.line_item?.item_code ?? "",
                  id: item.line_item?.id,
                },
              item_name: item.line_item?.item_name,
              item_code: item.line_item?.item_code,
              quantity: quantity,
              branch_inventory_item: {
                id: item.line_item?.id,
                item_name: item.line_item?.item_name,
                item_code: item.line_item?.item_code,
              },
              branch_inventory_item_units_of_measure: item.unit_of_measure
                ? [
                    {
                      base_uuid: item.unit_of_measure.id?.toString() || "",
                      unit_of_measure: {
                        unit_name: item.unit_of_measure.unit_name,
                        unit_abbreviation: item.unit_of_measure.unit_abbreviation || "",
                      },
                      selling_price: item.unit_of_measure.selling_price || item.unit_cost,
                      is_base_unit_of_measure:
                        item.unit_of_measure.is_base_unit_of_measure || false,
                    },
                  ]
                : [],
            },
            selected_uom_uuid: item.unit_of_measure?.id?.toString() || "",
            unit_price: item.unit_cost || "0.00",
          };
        }),
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to fetch recurring invoice details",
        variant: "destructive",
      });
      router.push("/invoices/recurring-invoices");
    } finally {
      setIsLoading(false);
    }
  }, [base_uuid, toast, router]);

  useEffect(() => {
    fetchRecurringInvoice();
  }, [fetchRecurringInvoice]);

  const handleFrequencyChange = useCallback((value: RecurringFrequency) => {
  setFormData((prev) => ({
    ...prev,
    recurring_frequency: value,
    weekdays: [],
    week_of_month: [],
    months: [],
  }));
}, []);

  const handleItemsChange = useCallback((items: any[]) => {
    setFormData((prev) => ({...prev, recurring_items: items}));
  }, []);

  const getCurrency = () => recurringInvoice?.currency ?? null;

  const previewNextRunDate = () => {
    if (!formData.start_date) return "";

    const start = new Date(formData.start_date);
    let next = new Date(start);

    switch (formData.recurring_frequency) {
      case "daily":
        next.setDate(next.getDate() + 1);
        break;
      case "weekly":
        next.setDate(next.getDate() + 7);
        break;
      case "monthly":
        next.setMonth(next.getMonth() + 1);
        break;
      case "biannual":
        next.setMonth(next.getMonth() + 6);
        break;
      case "annual":
        next.setFullYear(next.getFullYear() + 1);
        break;
    }

    return format(next, "yyyy-MM-dd");
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.customer) newErrors.customer = "Customer is required";
    if (!formData.recurring_frequency) newErrors.frequency = "Frequency is required";
    if (!formData.start_date) newErrors.start_date = "Start date is required";
    if (formData.recurring_items.length === 0)
      newErrors.recurring_items = "At least one line item is required";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      showErrorToast({defaultMessage: "Please fill in all required fields."});
      return;
    }

    if (!currentInstitution) {
      toast({title: "Error", description: "No institution selected", variant: "destructive"});
      return;
    }

    if (!formData.customer) {
      showErrorToast({defaultMessage: "Customer is required"});
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = {
        customer: formData.customer,
        recurring_frequency: formData.recurring_frequency,
        start_date: formData.start_date,
        end_date: formData.end_date,
        name: formData.name,
        notes: formData.notes,
        description: formData.description,
        recurring_items: formData.recurring_items.map((item) => ({
          line_item: String(item.line_item),
          item_name: item.item_name,
          item_category: item.item_category || "",
          quantity: Number(item.quantity),
          unit_cost: item.unit_cost,
          line_total: item.line_total,
          unit_of_measure: item.unit_of_measure,
        })),
        ...(formData.weekdays?.length ? {weekdays: formData.weekdays} : {}),
        ...(formData.week_of_month?.length ? {week_of_month: formData.week_of_month} : {}),
        ...(formData.months?.length ? {months: formData.months} : {}),
      };
      await RECURRING_INVOICES_API.updateRecurringInvoice({
        base_uuid,
        templateData: payload,
      });

      toast({title: "Success", description: "Recurring template updated successfully"});

      router.push(`/invoices/recurring-invoices/${base_uuid}`);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to update recurring template",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageLayout title="Edit Recurring Invoice Template">
      {isLoading ? (
        <div className="space-y-6">
          <div className="h-8 bg-gray-200 animate-pulse rounded w-1/4" />
          <div className="h-64 bg-gray-200 animate-pulse rounded" />
        </div>
      ) : !recurringInvoice ? (
        <div className="text-center py-8">
          <p className="text-muted-foreground">Recurring invoice not found</p>
          <Button onClick={() => router.push("/invoices/recurring-invoices")} className="mt-4">
            Back to Recurring Invoices
          </Button>
        </div>
      ) : (
        // Main content
        <>
          {/* Header */}
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="sm"
              className="border rounded-full h-10 w-10 flex items-center justify-center shrink-0"
              onClick={() => router.push(`/invoices/recurring-invoices/${base_uuid}`)}
            >
              <Icon icon="hugeicons:arrow-left-02" className="w-4 h-4" />
            </Button>
            <h1 className="text-2xl font-bold">
              Edit Recurring Invoice - {recurringInvoice.customer.customer_name}
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Template Details */}
            <FormSection
              title="Template Details"
              description="Define the customer, schedule, and basic information for this recurring invoice template."
              gridClassName="grid-cols-1 lg:grid-cols-2 gap-6"
            >
              <div className="space-y-2">
              <Label htmlFor="reference_code">Recurring Invoice Code</Label>
              <Input
                id="reference_code"
                type="text"
                value={recurringInvoice.reference_code || "—"}
                readOnly
                disabled
                className="bg-muted"
              />
              <p className="text-sm text-muted-foreground">
                Auto-generated code for this recurring invoice.
              </p>
            </div>
          
              {/* Customer - Read Only */}
              <div className="space-y-2">
                <Label htmlFor="customer">Customer</Label>
                <Input
                  id="customer"
                  type="text"
                  value={recurringInvoice.customer.customer_name}
                  readOnly
                  disabled
                  className="bg-muted"
                />
                <p className="text-sm text-muted-foreground">
                  The customer for this recurring invoice template.
                </p>
              </div>

              {/* Frequency */}
              <div className="space-y-2">
                <Label required>Recurring Frequency</Label>
                <Select value={formData.recurring_frequency} onValueChange={handleFrequencyChange}>
                  <SelectTrigger className="mt-1.5 w-full">
                    <SelectValue placeholder="Select frequency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="biannual">Biannual</SelectItem>
                    <SelectItem value="annual">Annual</SelectItem>
                  </SelectContent>
                </Select>
                {formData.recurring_frequency === "daily" && (
                <div className="space-y-2 lg:col-span-2">
                  <Label>Days of the Week</Label>
                  <ChipMultiSelect
                    options={DAY_OPTIONS}
                    selected={formData.weekdays ?? []}
                    onChange={(val) => setFormData((prev) => ({...prev, weekdays: val}))}
                    helperText="Leave blank to repeat every day."
                  />
                </div>
              )}

              {formData.recurring_frequency === "weekly" && (
                <div className="space-y-2 lg:col-span-2">
                  <Label>Weeks of the Month</Label>
                  <ChipMultiSelect
                    options={WEEK_OPTIONS}
                    selected={formData.week_of_month ?? []}
                    onChange={(val) => setFormData((prev) => ({...prev, week_of_month: val}))}
                    helperText="Leave blank to repeat every week."
                  />
                </div>
              )}

              {formData.recurring_frequency === "monthly" && (
                <div className="space-y-2 lg:col-span-2">
                  <Label>Months of the Year</Label>
                  <ChipMultiSelect
                    options={MONTH_OPTIONS}
                    selected={formData.months ?? []}
                    onChange={(val) => setFormData((prev) => ({...prev, months: val}))}
                    helperText="Leave blank to repeat every month."
                  />
                </div>
              )}
                <p className="text-sm text-muted-foreground">
                  How often invoices will be automatically generated.
                </p>
                {errors.frequency && <p className="text-sm text-red-600">{errors.frequency}</p>}
              </div>

              {/* Start Date */}
              <div className="space-y-2">
                <Label htmlFor="start_date" required>
                  Start Date
                </Label>
                <Input
                  id="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData((prev) => ({...prev, start_date: e.target.value}))}
                  min={new Date().toISOString().split("T")[0]}
                />
                <p className="text-sm text-muted-foreground">
                  The date when recurring invoices should begin.
                </p>
                {errors.start_date && <p className="text-sm text-red-600">{errors.start_date}</p>}
              </div>

              {/* End Date */}
              <div className="space-y-2">
                <Label htmlFor="end_date">End Date (Optional)</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date || ""}
                  onChange={(e) =>
                    setFormData((prev) => ({...prev, end_date: e.target.value || null}))
                  }
                  min={formData.start_date}
                />
                <p className="text-sm text-muted-foreground">
                  Leave empty for indefinite recurring invoices.
                </p>
              </div>

              {/* Next Run Date Preview */}
              <div className="space-y-2">
                <Label htmlFor="next_run_date">Next Run Date</Label>
                <Input
                  id="next_run_date"
                  type="text"
                  value={previewNextRunDate()}
                  readOnly
                  disabled
                  className="bg-muted"
                />
                <p className="text-sm text-muted-foreground">
                  Preview based on start date and frequency.
                </p>
              </div>
            </FormSection>

            {/* Line Items */}
            <div className="space-y-4">
              <LineItemsInput
                key={recurringInvoice.id}
                currency={getCurrency()}
                initialItems={formData.recurring_items.map((item) => ({
                  ...item,
                  line_item: String(item.line_item),
                  unit_price: item.unit_cost,
                }))}
                showUOMSelector={true}
                allowUnitPriceOverride={true}
                canAdd={false}
                canDelete={false}
                onItemsChange={handleItemsChange}
              />
              {errors.recurring_items && (
                <p className="text-sm text-red-600">{errors.recurring_items}</p>
              )}
            </div>

             <div className="space-y-2">
                <Label htmlFor="description" showOptional>Notes</Label>
                <textarea
                  id="description"
                  value={formData.description ?? ""}
                  onChange={(e) => setFormData((prev) => ({...prev, description: e.target.value}))}
                  placeholder="Enter description..."
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-4 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                />
              </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3 pt-8">
              <Button type="submit" disabled={isSubmitting} className="w-1/2 rounded-full h-12">
                {isSubmitting ? (
                  <>
                    <Icon icon="svg-spinners:180-ring" className="w-5 h-5 mr-2 animate-spin" />
                    Updating Template...
                  </>
                ) : (
                  "Update Recurring Template"
                )}
              </Button>
            </div>
          </form>
        </>
      )}
    </PageLayout>
  );
}
