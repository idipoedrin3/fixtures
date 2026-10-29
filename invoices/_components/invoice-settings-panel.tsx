"use client";

import {useEffect, useMemo, useState} from "react";
import {useDispatch, useSelector} from "react-redux";
import {toast} from "sonner";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {SlideOverPanel} from "#/_components/common/slide-over-pannel";
import {INSTITUTIONS_API} from "#/_api/api.helpers";
import {CASH_ACCOUNTS_API} from "#/_api/approvals.helpers";
import {ICashAccount} from "#/_types/approvals.types";
import {setSelectedInstitution} from "@/store/auth/actions";
import {selectSelectedInstitution} from "@/store/auth/selectors";

const MIN_PAYMENT_TERM_DAYS = 0;
const MAX_PAYMENT_TERM_DAYS = 18250;

interface Props {
  open: boolean;
  onClose: () => void;
}

type PaymentOption = {content_type: number; content_object_uuid: string};

export function InvoiceSettingsPanel({open, onClose}: Props) {
  const dispatch = useDispatch();
  const selectedInstitution = useSelector(selectSelectedInstitution);

  const [dueDays, setDueDays] = useState<string>("");
  const [initialDueDays, setInitialDueDays] = useState<string>("");

  const [initialAccounts, setInitialAccounts] = useState<ICashAccount[]>([]);
  const [paymentOptions, setPaymentOptions] = useState<PaymentOption[]>([]);
  const [initialPaymentOptions, setInitialPaymentOptions] = useState<PaymentOption[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open || !selectedInstitution?.base_uuid) return;

    const load = async () => {
      setIsLoading(true);
      try {
        const response = await INSTITUTIONS_API.getInstitutionById(selectedInstitution.base_uuid);

        // due days
        const days = response.default_invoice_due_days?.toString() ?? "";
        setDueDays(days);
        setInitialDueDays(days);

        const active: ICashAccount[] = (response.payment_options ?? [])
          .filter((p: any) => !p.deleted_at && p.payment_option)
          .map((p: any) => p.payment_option as ICashAccount);

        const mapped: PaymentOption[] = active.map((a) => ({
          content_type: a.model.id,
          content_object_uuid: a.base_uuid,
        }));

        setInitialAccounts(active);
        setPaymentOptions(mapped);
        setInitialPaymentOptions(mapped);
      } catch {
        toast.error("Failed to load invoice settings");
      } finally {
        setIsLoading(false);
      }
    };

    load();
  }, [open, selectedInstitution?.base_uuid]);

  const paymentOptionsChanged = useMemo(
    () => JSON.stringify(paymentOptions) !== JSON.stringify(initialPaymentOptions),
    [paymentOptions, initialPaymentOptions],
  );

  const hasChanges = dueDays !== initialDueDays || paymentOptionsChanged;

  const validateDueDays = (value: string): string | null => {
    if (value === "" || value === null || value === undefined) {
      return "Invoice due days must be a whole number between 0 and 18,250 days (50 years).";
    }

    const numValue = value.trim() === "" ? NaN : Number(value);

    if (isNaN(numValue)) {
      return "Invoice due days must be a whole number between 0 and 18,250 days (50 years).";
    }

    if (!Number.isInteger(numValue)) {
      return "Invoice due days must be a whole number between 0 and 18,250 days (50 years).";
    }

    if (numValue < MIN_PAYMENT_TERM_DAYS || numValue > MAX_PAYMENT_TERM_DAYS) {
      return "Invoice due days must be a whole number between 0 and 18,250 days (50 years).";
    }

    return null;
  };

  const handleSave = async () => {
    if (!selectedInstitution?.base_uuid) return;

    const validationError = validateDueDays(dueDays);
    if (validationError) {
      toast.error(validationError);
      return;
    }

    setIsSaving(true);
    try {
      const trimmed = dueDays.trim();
      const payload: Record<string, any> = {
        default_invoice_due_days: Number(trimmed),
      };

      // only send payment_options if the user actually changed the selection
      if (paymentOptionsChanged) {
        payload.payment_options = paymentOptions;
      }

      const response = await INSTITUTIONS_API.institutionUpdate(
        selectedInstitution.base_uuid,
        payload,
      );

      if (response) {
        dispatch(setSelectedInstitution({...selectedInstitution, ...response}));
        toast.success("Invoice settings updated successfully");
        onClose();
      }
    } catch {
      toast.error("Failed to update invoice settings");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <SlideOverPanel
      open={open}
      onClose={onClose}
      title={
        <span className="text-xl font-semibold tracking-wide text-gray-950">Invoice Settings</span>
      }
      description="Configure how invoices behave for this institution."
      onSubmit={handleSave}
      submitLabel="Save Changes"
      isSubmitting={isSaving}
      submitDisabled={!hasChanges || isLoading}
    >
      {isLoading ? (
        <div className="space-y-4">
          <div className="h-6 w-2/3 bg-gray-200 animate-pulse rounded" />
          <div className="h-10 w-full bg-gray-200 animate-pulse rounded" />
          <div className="h-6 w-1/2 bg-gray-200 animate-pulse rounded" />
          <div className="h-10 w-full bg-gray-200 animate-pulse rounded" />
        </div>
      ) : (
        <div className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="cash_account">Payment options</Label>
            <PaginatedSearchableSelect<ICashAccount>
              id="cash_account"
              multiple
              fetchFirstPage={(params) =>
                CASH_ACCOUNTS_API.fetchCashAccounts({...params, excludeCashbooks: true})
              }
              fetchFromUrl={CASH_ACCOUNTS_API.fetchCashAccountsFromUrl}
              idKey="base_uuid"
              valueKey="base_uuid"
              labelKey="account_name"
              labelDescKeyFn={(item) => `${item.reference_code} • ${item.model.model_name}`}
              placeholder="Select account"
              searchPlaceholder="Search accounts..."
              emptyMessage="No accounts found"
              initialData={initialAccounts}
              onItemsChange={(items: ICashAccount[]) => {
                setPaymentOptions(
                  items.map((item) => ({
                    content_type: item.model.id,
                    content_object_uuid: item.base_uuid,
                  })),
                );
              }}
              onValueChange={() => {}}
              description="Choose the cash, bank, mobile money or wallet account where the payment is deposited."
            />
          </div>

          <div className="space-y-2">
            <Label>Invoice Due Days</Label>
            <Input
              type="number"
              min={MIN_PAYMENT_TERM_DAYS}
              max={MAX_PAYMENT_TERM_DAYS}
              value={dueDays}
              onChange={(e) => setDueDays(e.target.value)}
              className="rounded-lg"
              placeholder="e.g. 30"
              description="Specify the number of days after the invoice date that payment is due."
            />
          </div>
        </div>
      )}
    </SlideOverPanel>
  );
}
