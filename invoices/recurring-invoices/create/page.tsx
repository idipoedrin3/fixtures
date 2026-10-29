"use client";

import {useState} from "react";
import {useRouter} from "next/navigation";
import {useSelector} from "react-redux";
import {Icon} from "@iconify/react";
import {format} from "date-fns";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Switch} from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {useToast} from "#/_hooks/use-toast";
import {showErrorToast} from "#/_lib/utils";
import {RECURRING_INVOICES_API, CUSTOMERS_API} from "#/_api/api.helpers";
import {
  Currency,
  ICustomer,
  IRecurringInvoiceFormData,
  IRecurringInvoiceLineItemFormData,
} from "#/_types/api.types";
import {selectSelectedBranches, selectSelectedInstitution} from "@/store/auth/selectors";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import PageLayout from "#/_components/common/layouts/page-layout";
import LineItemsInput, {LineItem} from "#/_components/custom/sales/line-items-input";
import FormSection from "#/_components/common/form-section";
import React from "react";
import ReferenceCodeInput from "#/_components/custom/reference-code-input";
import {ChipMultiSelect} from "../_components/chip-multi-select";
import {DAY_OPTIONS, WEEK_OPTIONS, MONTH_OPTIONS} from "../_components/option-constants";
import FormattedDatePicker from "#/_components/common/inputs/formatted-date-picker";

export default function RecurringInvoiceCreatePage() {
  const router = useRouter();
  const {toast} = useToast();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const selectedBranches = useSelector(selectSelectedBranches);
  const selectedBranch = selectedBranches[0];
  const [customer, setCustomer] = useState<ICustomer | null>(null);
  const setField = (key: keyof typeof formData, value: any) => {
    setFormData((prev) => ({...prev, [key]: value}));
    if (errors[key]) setErrors((prev) => ({...prev, [key]: ""}));
  };

  const [formData, setFormData] = useState<
    Omit<IRecurringInvoiceFormData, "customer" | "branch"> & {
      customer: string | null;
    }
  >({
    customer: null,
    recurring_frequency: "monthly",
    start_date: new Date().toISOString().split("T")[0],
    end_date: null,
    recurring_items: [],
    should_always_use_template_price: false,
    description: "",
    reference_code: "",
    schedule: {
      interval: 1,
      days_of_week: [],
      days_of_month: [],
      weeks_of_month: [],
      months_of_year: [],
    },
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleFrequencyChange = React.useCallback(
    (value: IRecurringInvoiceFormData["recurring_frequency"]) => {
      setFormData((prev) => ({
        ...prev,
        recurring_frequency: value,
        schedule: {
          ...prev.schedule,
          days_of_week: [],
          days_of_month: [],
          weeks_of_month: [],
          months_of_year: [],
        },
      }));
    },
    [],
  );

  const handleItemsChange = React.useCallback((items: LineItem[]) => {
    const mapped: IRecurringInvoiceLineItemFormData[] = items.map((item) => ({
      line_item: String(item.line_item),
      item_name: item.item_name ?? "",
      quantity: Number(item.quantity),
      unit_cost: String(item.unit_price),
      line_total: String(item.line_total),
      unit_of_measure: String(item.unit_of_measure ?? ""),
    }));
    setFormData((prev) => ({...prev, recurring_items: mapped}));
  }, []);

  const getCurrency = (): Currency => {
    return {
      id: 0,
      code: "UGX",
      name: "Ugandan Shilling",
      symbol: "USh",
      decimail_places: 0,
      rate: "1",
      base_uuid: "UGX",
    };
  };

  const previewNextRunDate = () => {
    if (!formData.start_date) return "";

    const start = new Date(formData.start_date);
    let next = new Date(start);

    switch (formData.recurring_frequency) {
      case "daily":
        if (formData.schedule.days_of_week?.length) {
          for (let offset = 1; offset <= 7; offset += 1) {
            const candidate = new Date(start);
            candidate.setDate(candidate.getDate() + offset);
            const backendWeekday = (candidate.getDay() + 6) % 7;

            if (formData.schedule.days_of_week.includes(backendWeekday)) {
              next = candidate;
              break;
            }
          }
        } else {
          next.setDate(next.getDate() + 1);
        }
        break;
      case "weekly":
        next.setDate(next.getDate() + 7);
        break;
      case "monthly":
        next.setMonth(next.getMonth() + 1);
        break;
      case "bi-annually":
        next.setMonth(next.getMonth() + 6);
        break;
      case "annually":
        next.setFullYear(next.getFullYear() + 1);
        break;
    }

    return format(next, "yyyy-MM-dd");
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.customer) newErrors.customer = "Customer is required";
    if (!selectedBranch) newErrors.branch = "Branch is required";
    if (!formData.recurring_frequency)
      newErrors.recurring_frequency = "Recurrence Frequency is required";
    if (!formData.start_date) newErrors.start_date = "Start date is required";
    if (formData.start_date && formData.end_date && formData.end_date < formData.start_date) {
      newErrors.end_date = "End date cannot be earlier than start date";
    }
    if (!formData.schedule.interval || formData.schedule.interval < 1) {
      newErrors.interval = "Number of occurrences must be at least 1";
    }
    if (
      formData.recurring_frequency === "daily" &&
      formData.schedule.days_of_week?.length &&
      formData.start_date
    ) {
      const startDay = (new Date(`${formData.start_date}T00:00:00`).getDay() + 6) % 7;

      if (!formData.schedule.days_of_week.includes(startDay)) {
        newErrors.start_date = "Start date must be one of the selected weekdays";
      }
    }
    if (formData.recurring_items.length === 0)
      newErrors.recurring_items = "At least one line item is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleCustomerChange = (cust: ICustomer | null) => {
    setCustomer(cust);
    setFormData((prev) => ({...prev, customer: cust?.base_uuid ?? null}));
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
      const payload: IRecurringInvoiceFormData = {
        customer: formData.customer!,
        branch: selectedBranch.base_uuid,
        recurring_frequency: formData.recurring_frequency,
        start_date: formData.start_date,
        end_date: formData.end_date,
        description: formData.description,
        reference_code: formData.reference_code,
        recurring_items: formData.recurring_items,
        schedule: formData.schedule,
        should_always_use_template_price: formData.should_always_use_template_price,
      };

      await RECURRING_INVOICES_API.createRecurringInvoice({templateData: payload});

      toast({title: "Success", description: "Recurring template created successfully"});

      router.push("/invoices?tab=recurring");
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to create recurring template",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  const fetchCustomers = React.useCallback(
    async (q: any) => await CUSTOMERS_API.fetchCustomers({...q, status: "approved"}),
    [],
  );

  if (!currentInstitution) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">
          Please select an institution to create recurring templates.
        </p>
      </div>
    );
  }

  return (
    <PageLayout title="Create Recurring Invoice Template">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="sm"
          className="border rounded-full h-10 w-10 flex items-center justify-center shrink-0"
          onClick={() => router.push("/invoices?tab=recurring")}
        >
          <Icon icon="hugeicons:arrow-left-02" className="w-4 h-4" />
        </Button>
        <h1 className="text-2xl font-bold">Create New Recurring Invoice</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Template Details */}
        <FormSection
          title="Template Details"
          description="Define the customer, schedule, and basic information for this recurring invoice template."
          gridClassName="grid-cols-1 lg:grid-cols-2 gap-6"
        >
          <ReferenceCodeInput
            label="Recurring Invoice Code"
            prefix="RIC"
            value={formData.reference_code ?? ""}
            onChange={(value) => setField("reference_code", value)}
            error={errors.reference_code}
          />
          {/* Customer */}
          <div className="space-y-2 lg:col-span-1">
            <Label htmlFor="customer" required>
              Customer
            </Label>
            <PaginatedSearchableSelect<ICustomer>
              fetchFirstPage={fetchCustomers}
              fetchFromUrl={CUSTOMERS_API.fetchCustomersFromUrl}
              idKey="id"
              valueKey="id"
              labelKey="customer_name"
              labelDescKey="email"
              onValueChange={() => {}}
              onItemSelected={(item) => handleCustomerChange(item)}
              placeholder="Select customer"
              searchPlaceholder="Search customers..."
              emptyMessage="No approved customers found"
              description="The customer who will receive recurring invoices."
            />
            {errors.customer && <p className="text-sm text-red-600">{errors.customer}</p>}
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
                <SelectItem value="bi-annually">Biannual</SelectItem>
                <SelectItem value="annually">Annual</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              Select the recurrence cycle for automatically generated invoices.
            </p>
            {errors.recurring_frequency && (
              <p className="text-sm text-red-600">{errors.recurring_frequency}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="interval" required>
              Number of Occurrences
            </Label>
            <Input
              id="interval"
              type="number"
              min={1}
              step={1}
              value={formData.schedule.interval}
              onChange={(event) =>
                setFormData((prev) => ({
                  ...prev,
                  schedule: {
                    ...prev.schedule,
                    interval: Number(event.target.value),
                  },
                }))
              }
            />
            <p className="text-sm text-muted-foreground">
              Maximum number of invoices that this schedule should generate.
            </p>
            {errors.interval && <p className="text-sm text-red-600">{errors.interval}</p>}
          </div>

          {["daily", "weekly", "monthly"].includes(formData.recurring_frequency) && (
            <div className="space-y-5 rounded-xl border border-border/70 bg-muted/20 p-5 lg:col-span-2">
              <div className="space-y-1">
                <h3 className="font-semibold text-base">Schedule Details</h3>
                <p className="text-sm text-muted-foreground">
                  Choose when invoices should run within the selected recurrence cycle.
                </p>
              </div>

              {formData.recurring_frequency === "daily" && (
                <div className="space-y-3">
                  <Label>Run on these days</Label>
                  <ChipMultiSelect
                    options={DAY_OPTIONS}
                    selected={formData.schedule.days_of_week ?? []}
                    onChange={(val) =>
                      setFormData((prev) => ({
                        ...prev,
                        schedule: {...prev.schedule, days_of_week: val},
                      }))
                    }
                    helperText="No selection means the invoice will run every day."
                  />
                </div>
              )}

              {formData.recurring_frequency === "weekly" && (
                <div className="space-y-3">
                  <Label>Run during these weeks</Label>
                  <ChipMultiSelect
                    options={WEEK_OPTIONS}
                    selected={formData.schedule.weeks_of_month ?? []}
                    onChange={(val) =>
                      setFormData((prev) => ({
                        ...prev,
                        schedule: {...prev.schedule, weeks_of_month: val},
                      }))
                    }
                    helperText="No selection means the invoice will run every week."
                  />
                </div>
              )}

              {formData.recurring_frequency === "monthly" && (
                <div className="space-y-3">
                  <Label>Run during these months</Label>
                  <ChipMultiSelect
                    options={MONTH_OPTIONS}
                    selected={formData.schedule.months_of_year ?? []}
                    onChange={(val) =>
                      setFormData((prev) => ({
                        ...prev,
                        schedule: {...prev.schedule, months_of_year: val},
                      }))
                    }
                    helperText="No selection means the invoice will run every month."
                  />
                </div>
              )}
            </div>
          )}

          {/* Start Date */}
          <div className="space-y-2">
            <FormattedDatePicker
              value={formData.start_date}
              onChange={(value) => setFormData((prev) => ({...prev, start_date: value || ""}))}
              id="start_date"
              label="Start Date"
              required={true}
              showAsterisk={true}
              limitMaxWidth={false}
              inputClassName="w-full bg-card border-border/50 h-10"
            />
            {errors.start_date && <p className="text-sm text-red-600">{errors.start_date}</p>}
          </div>

          {/* End Date */}
          <div className="space-y-2">
            <FormattedDatePicker
              value={formData.end_date ?? ""}
              onChange={(value) => setFormData((prev) => ({...prev, end_date: value || ""}))}
              id="end_date"
              label="End Date"
              showOptional
              showAsterisk={false}
              minDate={
                formData.start_date ? new Date(`${formData.start_date}T00:00:00`) : undefined
              }
              limitMaxWidth={false}
              inputClassName="w-full bg-card border-border/50 h-10"
            />
            <p className="text-sm text-muted-foreground">
              Leave empty for indefinite recurring invoices.
            </p>
            {errors.end_date && <p className="text-sm text-red-600">{errors.end_date}</p>}
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
              Preview based on start date and recurrence frequency.
            </p>
          </div>

          <div className="flex flex-col gap-2 mt-5 ml-4 lg:col-span-2">
            <div className="flex items-center gap-4">
              <Switch
                id="should_always_use_template_price"
                checked={formData.should_always_use_template_price}
                onCheckedChange={(checked) =>
                  setFormData((prev) => ({
                    ...prev,
                    should_always_use_template_price: checked,
                  }))
                }
              />
              <Label
                htmlFor="should_always_use_template_price"
                className="font-medium text-gray-700 cursor-pointer"
              >
                Always Use Template Prices
              </Label>
            </div>
            <span className="text-sm text-muted-foreground">
              Keep the unit prices entered on this template when generating invoices, even if
              inventory prices change.
            </span>
          </div>
        </FormSection>

        {/* Line Items */}
        <div className="space-y-4 -pt-8">
          <LineItemsInput
            inventoryLevel="institution"
            currency={getCurrency()}
            initialItems={[]}
            showUOMSelector={true}
            allowUnitPriceOverride={true}
            onItemsChange={handleItemsChange}
          />
          {errors.recurring_items && (
            <p className="text-sm text-red-600">{errors.recurring_items}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label showOptional htmlFor="description">
            Notes
          </Label>
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
                Creating Invoice...
              </>
            ) : (
              "Create Recurring Invoice"
            )}
          </Button>
        </div>
      </form>
    </PageLayout>
  );
}
