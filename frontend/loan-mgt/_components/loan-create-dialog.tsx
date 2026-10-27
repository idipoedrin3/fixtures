"use client";

import {useRef, useState, type FormEvent, type ReactNode} from "react";
import {toast} from "sonner";
import {LoanSchedulePreviewDialog} from "./loan-schedule-preview-dialog";
import {
  ACCOUNTS_API,
  CUSTOMERS_API,
  INSTITUTIONS_API,
  INSTITUTION_CURRENCIES_API,
} from "#/_api/api.helpers";
import {LENDERS_API, LOANS_API} from "#/_api/loans.helpers";
import type {
  ILoanCreateData,
  ILoanDetail,
  LoanInitialAccountingTreatment,
} from "#/_types/loans.types";
import {formatCurrency, showErrorToast} from "#/_lib/utils";
import FormSection from "#/_components/common/form-section";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import FormattedDatePicker from "#/_components/common/inputs/formatted-date-picker";
import {PaginatedSearchableSelect} from "#/_components/custom/paginated-searchable-select";
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
import {Textarea} from "#/_components/common/inputs/text-area";

const FREQUENCIES = [
  ["daily", "Daily"],
  ["weekly", "Weekly"],
  ["biweekly", "Every Two Weeks"],
  ["monthly", "Monthly"],
  ["quarterly", "Quarterly"],
  ["semiannually", "Every Six Months"],
  ["annually", "Annually"],
] as const;

const CHOICE_DESCRIPTIONS: Record<string, string> = {
  inflow: "Money comes into the institution. The institution borrows from a lender.",
  outflow: "Money leaves the institution. The institution lends to a customer.",
  reducing: "Interest is calculated on the remaining principal as repayments reduce the balance.",
  flat: "Interest is calculated on the original principal throughout the loan.",
  simple: "Interest grows proportionally with time, without compounding.",
  compound: "Interest uses an effective annual rate compounded over the elapsed period.",
  actual_365: "Uses the actual number of days divided by 365.",
  actual_360: "Uses the actual number of days divided by 360.",
  actual_actual_isda: "Uses actual days, dividing each year's portion by 365 or 366.",
  periodic: "Repay the loan through scheduled installments.",
  single: "Repay the loan in one payment on the maturity date.",
  daily: "Schedule a repayment every day.",
  weekly: "Schedule a repayment every week.",
  biweekly: "Schedule a repayment every two weeks.",
  monthly: "Schedule a repayment every month.",
  quarterly: "Schedule a repayment every three months.",
  semiannually: "Schedule a repayment every six months.",
  annually: "Schedule a repayment every year.",
  equal_installments:
    "Keep the total installment similar while principal and interest portions change.",
  equal_principal: "Repay the same principal each period; interest may change the total payment.",
  beginning: "Payments fall at the beginning of each period, starting on the disbursement date.",
  end: "Payments fall at the end of each period, after disbursement.",
};

function titleCase(label: string) {
  return label.replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

export function LoanCreateDialog({
  onClose,
  onCreated,
  loan,
}: {
  onClose: () => void;
  onCreated: () => void;
  loan?: ILoanDetail;
}) {
  const [form, setForm] = useState<ILoanCreateData>(() =>
    loan
      ? loanFormData(loan)
      : {
          reference_code: "",
          direction: "inflow",
          party_object_uuid: "",
          branch: null,
          currency: "",
          principal: "",
          annual_interest_rate: "0",
          interest_method: "reducing",
          interest_type: "simple",
          day_count_convention: "actual_365",
          repayment_structure: "periodic",
          repayment_frequency: "monthly",
          repayment_method: "equal_installments",
          repayment_timing: "end",
          disbursement_date: "",
          first_repayment_date: "",
          maturity_date: "",
          cash_account: "",
          liability_receivable_account: "",
          description: "",
          initial_accounting_treatment: "new_cash",
          initial_accounting_reference: "",
          opening_principal: "",
          opening_balance_account: "",
        },
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [requestError, setRequestError] = useState(false);
  const [previewData, setPreviewData] = useState<ILoanCreateData | null>(null);
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const submissionLock = useRef(false);
  const lending = form.direction === "outflow";
  const periodic = form.repayment_structure === "periodic";
  const canPreview = Boolean(
    form.party_object_uuid &&
    form.currency &&
    form.cash_account &&
    form.liability_receivable_account &&
    form.cash_account !== form.liability_receivable_account &&
    Number(form.principal) > 0 &&
    form.annual_interest_rate !== "" &&
    Number(form.annual_interest_rate) >= 0 &&
    form.disbursement_date &&
    form.maturity_date &&
    form.maturity_date >= form.disbursement_date &&
    (!periodic ||
      (form.repayment_frequency &&
        form.repayment_method &&
        form.repayment_timing &&
        form.first_repayment_date &&
        form.first_repayment_date <= form.maturity_date &&
        (form.repayment_timing === "beginning"
          ? form.first_repayment_date === form.disbursement_date
          : form.first_repayment_date > form.disbursement_date))),
  );

  function update<K extends keyof ILoanCreateData>(key: K, value: ILoanCreateData[K]) {
    setForm((previous) => ({...previous, [key]: value}));
    setErrors((previous) => ({...previous, [key]: ""}));
    setRequestError(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submissionLock.current) return;
    const nextErrors: Record<string, string> = {};
    for (const key of [
      "party_object_uuid",
      "currency",
      "disbursement_date",
      "maturity_date",
      "cash_account",
      "liability_receivable_account",
    ] as const) {
      if (!form[key]) nextErrors[key] = "This field is required.";
    }
    if (!form.principal || Number(form.principal) <= 0)
      nextErrors.principal = "Enter a principal greater than zero.";
    if (!form.annual_interest_rate || Number(form.annual_interest_rate) < 0)
      nextErrors.annual_interest_rate = "Enter a non-negative interest rate.";
    const firstDate = periodic ? form.first_repayment_date : form.maturity_date;
    if (!firstDate) nextErrors.first_repayment_date = "Choose the first repayment date.";
    if (firstDate && form.disbursement_date && firstDate < form.disbursement_date)
      nextErrors.first_repayment_date = "Repayment cannot precede disbursement.";
    if (form.maturity_date && form.disbursement_date && form.maturity_date < form.disbursement_date)
      nextErrors.maturity_date = "Maturity cannot precede disbursement.";
    if (firstDate && form.maturity_date && firstDate > form.maturity_date)
      nextErrors.first_repayment_date = "First repayment cannot follow maturity.";
    if (periodic && form.repayment_timing === "beginning" && firstDate !== form.disbursement_date)
      nextErrors.first_repayment_date =
        "Beginning-of-period repayments must start on the disbursement date.";
    if (
      periodic &&
      form.repayment_timing === "end" &&
      firstDate &&
      firstDate <= form.disbursement_date
    )
      nextErrors.first_repayment_date = "End-of-period repayments must start after disbursement.";
    if (form.cash_account && form.cash_account === form.liability_receivable_account)
      nextErrors.liability_receivable_account = "Choose a different account from the cash account.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    submissionLock.current = true;
    setSaving(true);
    try {
      const payload: ILoanCreateData = {
        ...form,
        reference_code: form.reference_code?.trim() || undefined,
        first_repayment_date: firstDate,
        repayment_frequency: periodic ? form.repayment_frequency : null,
        repayment_method: periodic ? form.repayment_method : null,
        repayment_timing: periodic ? form.repayment_timing : null,
        description: form.description.trim(),
      };
      if (loan) {
        const original = loanFormData(loan);
        const changes = Object.fromEntries(
          Object.entries(payload).filter(
            ([key, value]) =>
              key !== "reference_code" && value !== original[key as keyof ILoanCreateData],
          ),
        ) as Partial<Omit<ILoanCreateData, "reference_code">>;
        if (!Object.keys(changes).length) {
          toast.info("No changes to save");
          return;
        }
        await LOANS_API.update(loan.base_uuid, changes);
      } else {
        await LOANS_API.create(payload);
      }
      toast.success(loan ? "Loan update submitted" : "Loan created");
      onCreated();
    } catch (error) {
      setRequestError(true);
      showErrorToast({
        error,
        defaultMessage: loan ? "Unable to update loan" : "Unable to create loan",
      });
    } finally {
      submissionLock.current = false;
      setSaving(false);
    }
  }

  const selectionProps = {
    idKey: "base_uuid" as const,
    valueKey: "base_uuid" as const,
    disabled: saving,
    popoverContainer: container,
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !saving) onClose();
      }}
    >
      <DialogContent
        className="flex h-[94vh] max-h-[94vh] w-[90vw] max-w-[90vw] flex-col gap-0 overflow-hidden p-0"
        onPointerDownOutside={(event) => event.preventDefault()}
        onEscapeKeyDown={(event) => {
          if (saving) event.preventDefault();
        }}
      >
        <DialogHeader className="shrink-0 border-b px-6 py-4">
          <DialogTitle className="text-2xl">
            {loan ? `Edit Loan — ${loan.reference_code || "Loan"}` : "Create Loan"}
          </DialogTitle>
          <DialogDescription>
            Enter the loan details, repayment terms, and accounting accounts.
          </DialogDescription>
        </DialogHeader>
        <form className="flex min-h-0 flex-1 flex-col" noValidate onSubmit={submit}>
          <div ref={setContainer} className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
            {Object.values(errors).some(Boolean) && (
              <p role="alert" className="mb-4 text-sm text-destructive">
                Please correct the highlighted fields.
              </p>
            )}
            {requestError && (
              <p role="alert" className="mb-4 text-sm text-destructive">
                Unable to save the loan. Review the error and try again.
              </p>
            )}
            <fieldset disabled={saving} className="min-w-0 space-y-5">
              <FormSection
                title="Loan Details"
                description="Choose whether the institution is lending or borrowing."
              >
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:!mt-0">
                  <Field label="Reference Code" optional>
                    <Input
                      aria-label="Reference Code"
                      disabled={Boolean(loan)}
                      value={form.reference_code ?? ""}
                      maxLength={100}
                      placeholder="Auto-generated if left blank"
                      onChange={(event) => update("reference_code", event.target.value)}
                    />
                  </Field>
                  <Choice
                    label="Direction"
                    value={form.direction}
                    options={[
                      ["inflow", "Inflow"],
                      ["outflow", "Outflow"],
                    ]}
                    onChange={(value) => {
                      update("direction", value);
                      update("party_object_uuid", "");
                      update("liability_receivable_account", "");
                    }}
                  />
                </div>
                <Field label={lending ? "Customer" : "Lender"} error={errors.party_object_uuid}>
                  {lending ? (
                    <PaginatedSearchableSelect
                      key="customer"
                      {...selectionProps}
                      fetchFirstPage={CUSTOMERS_API.fetchCustomers}
                      fetchFromUrl={CUSTOMERS_API.fetchCustomersFromUrl}
                      labelKey="customer_name"
                      initialSelectedLabel={
                        loan?.direction === "outflow" &&
                        form.party_object_uuid === loan.party_object_uuid
                          ? loan.party_name || undefined
                          : undefined
                      }
                      placeholder="Select a Customer"
                      searchPlaceholder="Search Customers..."
                      emptyMessage="No customers found."
                      labelDescKeyFn={(item) =>
                        [
                          item.reference_code || "No reference",
                          `Outstanding Receivables: ${
                            item.outstanding_receivables_balance == null
                              ? "Unavailable"
                              : formatCurrency(item.outstanding_receivables_balance)
                          }`,
                        ].join(" • ")
                      }
                      description="Choose the customer receiving the loan."
                      value={form.party_object_uuid}
                      onValueChange={(values) => update("party_object_uuid", values[0] || "")}
                    />
                  ) : (
                    <PaginatedSearchableSelect
                      key="lender"
                      {...selectionProps}
                      fetchFirstPage={LENDERS_API.list}
                      fetchFromUrl={LENDERS_API.fromUrl}
                      labelKey="name"
                      initialSelectedLabel={
                        loan?.direction === "inflow" &&
                        form.party_object_uuid === loan.party_object_uuid
                          ? loan.party_name || undefined
                          : undefined
                      }
                      placeholder="Select a Lender"
                      searchPlaceholder="Search Lenders..."
                      emptyMessage="No lenders found."
                      labelDescKeyFn={(item) =>
                        [
                          item.reference_code || "No reference",
                          item.description || "Loan provider",
                        ].join(" • ")
                      }
                      description="Choose the lender providing funds to the institution."
                      value={form.party_object_uuid}
                      onValueChange={(values) => update("party_object_uuid", values[0] || "")}
                    />
                  )}
                </Field>
                <Field label="Currency" error={errors.currency}>
                  <PaginatedSearchableSelect
                    {...selectionProps}
                    fetchFirstPage={INSTITUTION_CURRENCIES_API.fetchFirstPage}
                    fetchFromUrl={INSTITUTION_CURRENCIES_API.fetchFromUrl}
                    labelKeyFn={(item) => item.currency.code}
                    initialSelectedLabel={
                      form.currency === loan?.currency ? loan.currency_code : undefined
                    }
                    labelDescKeyFn={(item) => item.currency.name}
                    placeholder="Select a Currency"
                    searchPlaceholder="Search Currencies..."
                    emptyMessage="No currencies found."
                    description="The currency in which the principal and repayments are recorded."
                    value={form.currency}
                    onValueChange={(values) => {
                      update("currency", values[0] || "");
                      update("cash_account", "");
                      update("liability_receivable_account", "");
                    }}
                  />
                </Field>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:!mt-0">
                  <Field label="Principal" error={errors.principal}>
                    <FormattedNumberInput
                      aria-label="Principal"
                      value={form.principal}
                      min={0}
                      max={999999999999999}
                      placeholder="0"
                      onValueChange={(value) =>
                        update("principal", value == null ? "" : String(value))
                      }
                    />
                  </Field>
                  <Field label="Annual Interest Rate (%)" error={errors.annual_interest_rate}>
                    <FormattedNumberInput
                      aria-label="Annual Interest Rate (%)"
                      value={form.annual_interest_rate}
                      min={0}
                      max={999.99}
                      step={0.01}
                      onValueChange={(value) =>
                        update("annual_interest_rate", value == null ? "" : String(value))
                      }
                    />
                  </Field>
                </div>
                <Field label="Branch" optional>
                  <PaginatedSearchableSelect
                    {...selectionProps}
                    fetchFirstPage={INSTITUTIONS_API.fetchInstitutionBranches}
                    fetchFromUrl={INSTITUTIONS_API.fetchInstitutionBranchesFromUrl}
                    labelKey="branch_name"
                    initialSelectedLabel={
                      form.branch === loan?.branch ? loan?.branch_name || undefined : undefined
                    }
                    labelDescKey="reference_code"
                    placeholder="Select a Branch"
                    searchPlaceholder="Search Branches..."
                    emptyMessage="No branches found."
                    description="Optionally assign this loan to a branch."
                    value={form.branch}
                    clearButton
                    onValueChange={(values) => update("branch", values[0] || null)}
                  />
                </Field>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:!mt-0">
                  <div className="space-y-2">
                    <FormattedDatePicker
                      id="loan-disbursement-date"
                      label={lending ? "Disbursement Date" : "Funds Receipt Date"}
                      description="The date the loan funds are paid out or received."
                      required
                      value={form.disbursement_date}
                      disabled={saving}
                      onChange={(value) => update("disbursement_date", value || "")}
                    />
                    <FieldError error={errors.disbursement_date} />
                  </div>
                  <div className="space-y-2">
                    <FormattedDatePicker
                      id="loan-maturity-date"
                      label="Maturity Date"
                      description="The date by which the loan must be fully repaid."
                      required
                      value={form.maturity_date}
                      disabled={saving}
                      onChange={(value) => update("maturity_date", value || "")}
                    />
                    <FieldError error={errors.maturity_date} />
                    {!periodic && <FieldError error={errors.first_repayment_date} />}
                  </div>
                </div>
              </FormSection>
              <FormSection
                title="Repayment Terms"
                description="Set the interest calculation and repayment schedule."
              >
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:!mt-0">
                  <Choice
                    label="Interest Method"
                    value={form.interest_method}
                    options={[
                      ["reducing", "Reducing Balance"],
                      ["flat", "Flat"],
                    ]}
                    onChange={(value) => update("interest_method", value)}
                  />
                  <Choice
                    label="Interest Type"
                    value={form.interest_type}
                    options={[
                      ["simple", "Simple"],
                      ["compound", "Compound"],
                    ]}
                    onChange={(value) => update("interest_type", value)}
                  />
                </div>
                <Choice
                  label="Day count convention"
                  value={form.day_count_convention}
                  options={[
                    ["actual_365", "Actual / 365"],
                    ["actual_360", "Actual / 360"],
                    ["actual_actual_isda", "Actual / Actual (ISDA)"],
                  ]}
                  onChange={(value) => update("day_count_convention", value)}
                />
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:!mt-0">
                  <Choice
                    label="Repayment Structure"
                    value={form.repayment_structure}
                    options={[
                      ["periodic", "Periodic Installments"],
                      ["single", "Single Repayment"],
                    ]}
                    onChange={(value) => update("repayment_structure", value)}
                  />
                  {periodic && (
                    <Choice
                      label="Repayment Method"
                      value={form.repayment_method || "equal_installments"}
                      options={[
                        ["equal_installments", "Equal Installments"],
                        ["equal_principal", "Equal Principal"],
                      ]}
                      onChange={(value) => update("repayment_method", value)}
                    />
                  )}
                </div>
                {periodic && (
                  <>
                    <Choice
                      label="Repayment frequency"
                      value={form.repayment_frequency || "monthly"}
                      options={FREQUENCIES}
                      onChange={(value) => update("repayment_frequency", value)}
                    />
                    <Choice
                      label="Repayment timing"
                      value={form.repayment_timing || "end"}
                      options={[
                        ["beginning", "Beginning of period"],
                        ["end", "End of period"],
                      ]}
                      onChange={(value) => update("repayment_timing", value)}
                    />
                    <div>
                      <FormattedDatePicker
                        id="loan-first-repayment-date"
                        label="First Repayment Date"
                        description="The date the first scheduled installment is due."
                        required
                        value={form.first_repayment_date}
                        disabled={saving}
                        onChange={(value) => update("first_repayment_date", value || "")}
                      />
                      <FieldError error={errors.first_repayment_date} />
                    </div>
                  </>
                )}
                <p className="text-sm text-muted-foreground lg:col-span-2">
                  {periodic
                    ? "For end-of-period repayments, maturity must match the final installment date."
                    : "The loan is repaid on the maturity date."}
                  {form.interest_type === "compound" &&
                    " Compound interest uses an effective annual rate."}
                </p>
              </FormSection>
              <FormSection
                title="Initial Accounting"
                description="Specify how the loan's initial principal should be recorded in the ledger."
              >
                <Choice
                  label="Initial Accounting Treatment"
                  value={form.initial_accounting_treatment}
                  options={[
                    ["new_cash", "New Cash Transaction"],
                    ["historical_cash", "Historical Cash Transaction"],
                    ["opening_balance", "Opening Balance Conversion"],
                    ["already_recorded", "Already Recorded in Ledger"],
                  ]}
                  onChange={(value) =>
                    update("initial_accounting_treatment", value as LoanInitialAccountingTreatment)
                  }
                />
              </FormSection>
              <FormSection
                title="Accounts"
                description="Choose the accounts used to record the loan."
              >
                <Field label="Cash account" error={errors.cash_account}>
                  <PaginatedSearchableSelect
                    key={`cash-${form.currency}`}
                    {...selectionProps}
                    fetchFirstPage={(query) =>
                      ACCOUNTS_API.fetchAccounts({
                        ...query,
                        has_children: false,
                        account_role_code: ["cash_account"],
                      })
                    }
                    fetchFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
                    labelKey="account_name"
                    labelDescKey="reference_code"
                    placeholder="Select a Cash Account"
                    searchPlaceholder="Search Cash Accounts..."
                    emptyMessage="No cash accounts found."
                    description="The cash or bank account used to pay out or receive the funds."
                    value={form.cash_account}
                    initialSelectedLabel={
                      form.cash_account === loan?.cash_account ? loan.cash_account_name : undefined
                    }
                    onValueChange={(values) => update("cash_account", values[0] || "")}
                  />
                </Field>
                <Field
                  label={lending ? "Loan receivable account" : "Loan liability account"}
                  error={errors.liability_receivable_account}
                >
                  <PaginatedSearchableSelect
                    key={`balance-${form.direction}-${form.currency}`}
                    {...selectionProps}
                    fetchFirstPage={(query) =>
                      ACCOUNTS_API.fetchAccounts({
                        ...query,
                        has_children: false,
                        system_group_account_type_choice: [lending ? "asset" : "liability"],
                      })
                    }
                    fetchFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
                    labelKey="account_name"
                    labelDescKey="reference_code"
                    placeholder={
                      lending
                        ? "Select a Loan Receivable Account"
                        : "Select a Loan Liability Account"
                    }
                    searchPlaceholder="Search Loan Accounts..."
                    emptyMessage="No loan accounts found."
                    description={
                      lending
                        ? "Records the principal the customer owes the institution."
                        : "Records the principal the institution owes the lender."
                    }
                    value={form.liability_receivable_account}
                    initialSelectedLabel={
                      form.liability_receivable_account === loan?.liability_receivable_account
                        ? loan.loan_account_name
                        : undefined
                    }
                    onValueChange={(values) =>
                      update("liability_receivable_account", values[0] || "")
                    }
                  />
                </Field>
                <div className="lg:col-span-2">
                  <Textarea
                    id="loan-description"
                    value={form.description}
                    onChange={(event) => update("description", event.target.value)}
                    showOptional
                    label="Notes"
                    maxLength={350}
                    collapsible
                    showCount
                  />
                </div>
              </FormSection>
            </fieldset>
          </div>
          <div className="grid shrink-0 grid-cols-1 gap-x-4 border-t bg-background px-6 py-4">
            <Button
              type="button"
              variant="outline"
              className="mb-3 w-full"
              disabled={saving || !canPreview}
              onClick={() =>
                setPreviewData({
                  ...form,
                  reference_code: loan ? undefined : form.reference_code,
                  first_repayment_date: periodic ? form.first_repayment_date : form.maturity_date,
                  repayment_frequency: periodic ? form.repayment_frequency : null,
                  repayment_method: periodic ? form.repayment_method : null,
                  repayment_timing: periodic ? form.repayment_timing : null,
                  description: form.description.trim(),
                })
              }
            >
              View Repayment Schedule
            </Button>
            <Button type="submit" disabled={saving} className="w-full">
              {saving
                ? loan
                  ? "Saving..."
                  : "Creating..."
                : loan
                  ? "Save Changes"
                  : "Create Loan"}
            </Button>
          </div>
        </form>
        {previewData && (
          <LoanSchedulePreviewDialog data={previewData} onClose={() => setPreviewData(null)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

export function loanFormData(loan: ILoanDetail): ILoanCreateData {
  return {
    reference_code: loan.reference_code || "",
    direction: loan.direction,
    party_object_uuid: loan.party_object_uuid,
    branch: loan.branch,
    currency: loan.currency,
    principal: loan.principal,
    annual_interest_rate: loan.annual_interest_rate,
    interest_method: loan.interest_method,
    interest_type: loan.interest_type,
    day_count_convention: loan.day_count_convention,
    repayment_structure: loan.repayment_structure,
    repayment_frequency: loan.repayment_frequency,
    repayment_method: loan.repayment_method,
    repayment_timing: loan.repayment_timing,
    disbursement_date: loan.disbursement_date,
    first_repayment_date: loan.first_repayment_date,
    maturity_date: loan.maturity_date,
    cash_account: loan.cash_account,
    liability_receivable_account: loan.liability_receivable_account,
    description: loan.description || "",
    initial_accounting_treatment: loan.initial_accounting_treatment || "new_cash",
    initial_accounting_reference: loan.initial_accounting_reference || "",
    opening_principal: loan.opening_principal == null ? "" : String(loan.opening_principal),
    opening_balance_account: loan.opening_balance_account || "",
  };
}

function FieldError({error}: {error?: string}) {
  return error ? (
    <p role="alert" className="text-sm text-destructive">
      {error}
    </p>
  ) : null;
}

function Field({
  label,
  optional,
  error,
  children,
}: {
  label: string;
  optional?: boolean;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label required={!optional} showOptional={optional}>
        {titleCase(label)}
      </Label>
      {children}
      <FieldError error={error} />
    </div>
  );
}

function Choice<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly (readonly [T, string])[];
  onChange: (value: T) => void;
}) {
  return (
    <Field label={label}>
      <Select
        value={value}
        onValueChange={(selected) => {
          const option = options.find(([key]) => key === selected);
          if (option) onChange(option[0]);
        }}
      >
        <SelectTrigger aria-label={titleCase(label)}>
          <SelectValue placeholder={`Select ${titleCase(label)}`}>
            {titleCase(options.find(([key]) => key === value)?.[1] || value)}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {options.map(([key, text]) => (
            <SelectItem key={key} value={key}>
              <span className="flex flex-col gap-1 text-left">
                <span>{titleCase(text)}</span>
                <span className="text-xs font-normal text-muted-foreground">
                  {CHOICE_DESCRIPTIONS[key]}
                </span>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}
