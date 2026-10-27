"use client";

import {useEffect, useRef, useState, type FormEvent} from "react";
import {toast} from "sonner";
import {LOAN_REPAYMENTS_API} from "#/_api/loans.helpers";
import type {
  IAllocationSuggestion,
  ILoanRepayment,
  ILoanScheduleRow,
  LoanAccountingTreatment,
} from "#/_types/loans.types";
import {formatCurrency, formatDate, showErrorToast} from "#/_lib/utils";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import FormattedDatePicker from "#/_components/common/inputs/formatted-date-picker";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TREATMENTS: [LoanAccountingTreatment, string, string][] = [
  ["cash", "Current cash transaction", "Money was just paid or received."],
  ["historical_cash", "Historical cash transaction", "A past cash movement still to be posted."],
  ["already_recorded", "Already in the ledger", "Requires a supporting reference."],
];

const AMOUNT_FIELDS = [
  ["principal_amount", "principal_outstanding", "Principal"],
  ["interest_amount", "interest_outstanding", "Interest"],
  ["fee_amount", "fees_outstanding", "Fees"],
] as const;

const money = (value: number | string) =>
  formatCurrency(value, {minimumFractionDigits: 2, maximumFractionDigits: 2});

export function LoanPaymentFormDialog({
  loanUuid,
  currencyCode,
  payment,
  schedule,
  onClose,
  onSaved,
}: {
  loanUuid: string;
  currencyCode: string;
  payment?: ILoanRepayment;
  schedule?: ILoanScheduleRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const initialAmount = payment
    ? String(Number(payment.amount))
    : schedule
      ? String(Number(schedule.payable))
      : "";

  const [date, setDate] = useState(() => payment?.date ?? new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState(initialAmount);
  const [treatment, setTreatment] = useState<LoanAccountingTreatment>(
    payment?.accounting_treatment ?? "cash",
  );
  const [reference, setReference] = useState(payment?.accounting_reference ?? "");
  const [rows, setRows] = useState<IAllocationSuggestion[]>([]);
  const [unallocated, setUnallocated] = useState("0");
  const [previewing, setPreviewing] = useState(Boolean(payment));
  const [previewError, setPreviewError] = useState("");
  const [saving, setSaving] = useState(false);
  const skipPreviewFor = useRef<string | null>(payment ? initialAmount : null);

  useEffect(() => {
    if (!payment) return;
    let cancelled = false;
    void LOAN_REPAYMENTS_API.previewAllocation(loanUuid, {payment: payment.base_uuid})
      .then((result) => {
        if (cancelled) return;
        setRows(result.allocations);
        setUnallocated("0");
      })
      .catch(() => {
        if (!cancelled) setPreviewError("Unable to load the repayment allocation.");
      })
      .finally(() => {
        if (!cancelled) setPreviewing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [payment, loanUuid]);

  useEffect(() => {
    if (skipPreviewFor.current === amount) return;
    skipPreviewFor.current = null;
    if (!(Number(amount) > 0)) {
      setRows([]);
      setUnallocated("0");
      setPreviewError("");
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPreviewing(true);
      setPreviewError("");
      try {
        const result = await LOAN_REPAYMENTS_API.previewAllocation(loanUuid, {
          amount,
          ...(schedule?.base_uuid ? {repayment_schedule: schedule.base_uuid} : {}),
          ...(payment ? {payment: payment.base_uuid} : {}),
        });
        if (cancelled) return;
        setRows(result.allocations);
        setUnallocated(result.unallocated);
      } catch {
        if (cancelled) return;
        setRows([]);
        setPreviewError("Unable to allocate this amount to the open installments.");
      } finally {
        if (!cancelled) setPreviewing(false);
      }
    }, 400);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [amount, loanUuid, schedule, payment]);

  const lineTotal = (row: IAllocationSuggestion) =>
    Number(row.principal_amount || 0) +
    Number(row.interest_amount || 0) +
    Number(row.fee_amount || 0);
  const allocated = rows.reduce((total, row) => total + lineTotal(row), 0);

  const exceeds = (row: IAllocationSuggestion) =>
    AMOUNT_FIELDS.some(
      ([field, outstanding]) => Number(row[field] || 0) > Number(row[outstanding]) + 1e-9,
    );

  function editRow(index: number, field: (typeof AMOUNT_FIELDS)[number][0], value: number | null) {
    const next = rows.map((row, i) =>
      i === index ? {...row, [field]: value == null ? "0" : String(value)} : row,
    );
    setRows(next);
    setUnallocated("0");
    const total = next.reduce((sum, row) => sum + lineTotal(row), 0);
    const nextAmount = String(Number(total.toFixed(6)));
    skipPreviewFor.current = nextAmount;
    setAmount(nextAmount);
  }

  const blocking = !date
    ? "Choose the payment date."
    : !(Number(amount) > 0)
      ? "Enter the amount received."
      : previewing
        ? "Allocating..."
        : previewError
          ? previewError
          : Number(unallocated) > 0
            ? `The amount exceeds the outstanding balance by ${currencyCode} ${money(unallocated)}.`
            : !rows.length || !(allocated > 0)
              ? "Nothing to allocate."
              : rows.some(exceeds)
                ? "An allocation exceeds what is outstanding on its installment."
                : treatment === "already_recorded" && !reference.trim()
                  ? "Provide the supporting reference."
                  : "";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || blocking) return;
    setSaving(true);
    try {
      const data = {
        date,
        amount,
        accounting_treatment: treatment,
        accounting_reference: reference.trim(),
        allocations: rows
          .filter((row) => lineTotal(row) > 0)
          .map((row) => ({
            repayment_schedule: row.repayment_schedule,
            principal_amount: row.principal_amount || "0",
            interest_amount: row.interest_amount || "0",
            fee_amount: row.fee_amount || "0",
          })),
      };
      if (payment) await LOAN_REPAYMENTS_API.update(loanUuid, payment.base_uuid, data);
      else await LOAN_REPAYMENTS_API.create(loanUuid, data);
      toast.success(payment ? "Repayment update submitted" : "Repayment recorded");
      onSaved();
    } catch (error) {
      showErrorToast({
        error,
        defaultMessage: payment ? "Unable to update repayment" : "Unable to record repayment",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !saving) onClose();
      }}
    >
      <DialogContent
        className="z-[90] flex h-[64vh] min-h-0 max-h-[64vh] w-[64vw] max-w-[64vw] flex-col gap-0 overflow-hidden p-0"
        onOpenAutoFocus={(event) => event.preventDefault()}
        onPointerDownOutside={(event) => event.preventDefault()}
        onEscapeKeyDown={(event) => {
          if (saving) event.preventDefault();
        }}
      >
        <DialogHeader className="shrink-0 border-b px-6 py-4 text-left">
          <DialogTitle className="text-2xl">
            {payment ? `Edit Repayment — ${payment.reference_code ?? ""}` : "Record Repayment"}
          </DialogTitle>
          <DialogDescription>
            {schedule
              ? `Recording against installment ${schedule.installation_number}. Any excess flows to the next open installments.`
              : "Enter the amount received. It is allocated to the oldest open installments first, and you can adjust the split."}
          </DialogDescription>
        </DialogHeader>

        <form className="flex min-h-0 flex-1 flex-col" noValidate onSubmit={submit}>
          <fieldset
            disabled={saving}
            className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormattedDatePicker
                id="loan-payment-date"
                label="Payment Date"
                required
                showAsterisk
                maxDate={new Date()}
                limitMaxWidth={false}
                inputClassName="w-full bg-card border-border/50 h-10"
                value={date}
                onChange={(value) => setDate(value || "")}
              />
              <div className="space-y-2">
                <Label required>Amount Received ({currencyCode})</Label>
                <FormattedNumberInput
                  aria-label="Amount Received"
                  value={amount}
                  min={0}
                  placeholder="0.00"
                  onValueChange={(value) => setAmount(value == null ? "" : String(value))}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label required>Accounting Treatment</Label>
                <Select
                  value={treatment}
                  onValueChange={(value) => setTreatment(value as LoanAccountingTreatment)}
                >
                  <SelectTrigger aria-label="Accounting Treatment">
                    <SelectValue placeholder="Select treatment">
                      {TREATMENTS.find(([key]) => key === treatment)?.[1]}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {TREATMENTS.map(([key, label, hint]) => (
                      <SelectItem key={key} value={key}>
                        <span className="flex flex-col gap-1 text-left">
                          <span>{label}</span>
                          <span className="text-xs font-normal text-muted-foreground">{hint}</span>
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {treatment === "already_recorded" && (
                <div className="space-y-2">
                  <Label required>Supporting Reference</Label>
                  <Input
                    value={reference}
                    onChange={(event) => setReference(event.target.value)}
                    placeholder="Journal or ledger reference"
                  />
                </div>
              )}
            </div>

            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-semibold">Allocation</h3>
                <p className="text-xs text-muted-foreground">
                  Each installment is paid in the order fees, interest, then principal.
                </p>
              </div>

              {previewing ? (
                <div className="space-y-2">
                  {Array.from({length: 2}).map((_, index) => (
                    <div key={index} className="h-24 animate-pulse rounded-xl bg-muted" />
                  ))}
                </div>
              ) : rows.length === 0 ? (
                <p className="rounded-xl border border-dashed p-4 text-center text-sm text-muted-foreground">
                  Enter an amount to see how it is allocated.
                </p>
              ) : (
                rows.map((row, index) => (
                  <div
                    key={row.repayment_schedule}
                    className={`rounded-xl border p-4 ${exceeds(row) ? "border-destructive" : ""}`}
                  >
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="font-medium">Installment {row.installation_number}</p>
                      <p className="text-xs text-muted-foreground">
                        Due {formatDate(row.due_date)}
                      </p>
                    </div>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                      {AMOUNT_FIELDS.map(([field, outstanding, label]) => (
                        <div key={field} className="space-y-1">
                          <Label>{label}</Label>
                          <FormattedNumberInput
                            aria-label={`${label} for installment ${row.installation_number}`}
                            value={row[field]}
                            min={0}
                            onValueChange={(value) => editRow(index, field, value)}
                          />
                          <p className="text-xs text-muted-foreground">
                            Outstanding {money(row[outstanding])}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}

              {rows.length > 0 && !previewing && (
                <div className="grid w-full grid-cols-3 divide-x overflow-hidden rounded-lg border bg-muted/30">
                  {[
                    ["Amount", Number(amount || 0), ""],
                    ["Allocated", allocated, ""],
                    [
                      "Unallocated",
                      Number(unallocated || 0),
                      Number(unallocated) > 0 ? "text-destructive" : "text-emerald-600",
                    ],
                  ].map(([label, value, tone]) => (
                    <div key={label as string} className="min-w-0 px-2 py-2 text-center">
                      <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                        {label}
                      </span>
                      <span className={`mt-0.5 block truncate text-xs font-semibold ${tone}`}>
                        {currencyCode} {money(value as number)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </fieldset>

          <div className="shrink-0 space-y-2 border-t bg-background px-6 py-4">
            {blocking && Number(amount) > 0 && !previewing && (
              <p role="alert" className="text-sm text-destructive">
                {blocking}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={saving || Boolean(blocking)}>
              {saving ? "Saving..." : payment ? "Save Changes" : "Record Repayment"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
