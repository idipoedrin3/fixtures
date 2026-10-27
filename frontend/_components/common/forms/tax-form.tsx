"use client";

import type {ITax, ITaxFormData, IAccount} from "#/_types/api.types";
import {useState, useEffect, useRef} from "react";

import FormSection from "../form-section";
import TaxRulesInput from "./tax-rules-input";

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
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import ReferenceCodeInput from "../../custom/reference-code-input";
import {showSuccessToast} from "#/_api/helpers";
import {ACCOUNTS_API} from "#/_api/api.helpers";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {CreateAccountPanel} from "../create-chart-of-accounts-panel";
import SwitchSetting from "../inputs/switch-setting";
import {Textarea} from "../inputs/text-area";

interface TaxFormProps {
  tax: ITax | null;
  defaultIsStatutory?: boolean;
  onSubmit: (
    data: ITaxFormData,
    onSuccess: () => void,
    onError: (errors: Record<string, string>) => void,
  ) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export default function TaxForm({
  tax,
  defaultIsStatutory = false,
  onSubmit,
  onCancel,
  isSubmitting,
}: TaxFormProps) {
  const [formData, setFormData] = useState<ITaxFormData>({
    reference_code: "",
    tax_name: "",
    description: "",
    rate_type: "percentage",
    is_institution_contribution: true,
    institution_contribution: null,
    liable_party_contribution: null,
    has_rules: false,
    rule_application_type: null,
    is_inclusive: false,
    rules: [],
    is_statutory_obligation: tax?.is_statutory_obligation ?? defaultIsStatutory,
    is_applicable_to_invoice_or_bill: false,
    applicability: null,
  });
  const [taxAccount, setTaxAccount] = useState<string | null>(
    () => tax?.tax_account?.base_uuid ?? null,
  );

  const [showTaxAccountErrors, setShowTaxAccountErrors] = useState(false);
  const [initialAccounts, setInitialAccounts] = useState<any[]>([]);
  const [showCreateAccountPanel, setShowCreateAccountPanel] = useState(false);
  const onAccountCreatedCallbackRef = useRef<((id: string, name: string) => void) | null>(null);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [referenceCode, setReferenceCode] = useState("");
  const [rulesValid, setRulesValid] = useState(
    () => !!(tax?.has_rules && tax?.rule_on_tax?.length > 0),
  );

  const setField = (field: string, value: any) => {
    setFormData((prev) => ({...prev, [field]: value}));
    if (errors[field]) setErrors((prev) => ({...prev, [field]: ""}));
  };

  useEffect(() => {
    if (tax) {
      setTaxAccount(tax.tax_account?.base_uuid ?? null);
      setInitialAccounts(tax.tax_account ? [tax.tax_account] : []);

      setRulesValid(!!(tax.has_rules && tax.rule_on_tax?.length > 0));
      setReferenceCode(tax.reference_code || "");
      setFormData({
        reference_code: tax.reference_code || "",
        tax_name: tax.tax_name,
        description: tax.description || "",
        rate_type: tax.rate_type,
        is_institution_contribution: tax.institution_contribution != null,
        institution_contribution: tax.institution_contribution,
        liable_party_contribution: tax.liable_party_contribution,
        has_rules: tax.has_rules,
        rule_application_type: tax.has_rules ? tax.rule_application_type : null,
        is_inclusive: tax.is_inclusive,
        rules: tax.rule_on_tax.map((rule) => ({
          value_min: rule.value_min || "",
          value_max: rule.value_max || "",
          rate_type: rule.rate_type,
          rate_value: rule.rate_value,
        })),
        is_statutory_obligation: tax.is_statutory_obligation ?? false,
        is_applicable_to_invoice_or_bill: tax.is_applicable_to_invoice_or_bill ?? false,
        applicability: tax.applicability ?? null,
      });
    }
  }, [tax]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setShowTaxAccountErrors(true);

    const newErrors: Record<string, string> = {};

    if (!formData.tax_name.trim()) newErrors.tax_name = "Name is required";

    if (formData.rate_type === "percentage") {
      const institution = formData.is_institution_contribution
        ? Number(formData.institution_contribution)
        : 0;
      const liableParty = Number(formData.liable_party_contribution);
      if (institution + liableParty > 100) {
        newErrors.institution_contribution =
          "Institution and liable party contributions cannot exceed 100% combined.";
      }
    }

    if (
      formData.rate_type === "percentage" &&
      formData.is_institution_contribution &&
      Number(formData.institution_contribution) > 100
    ) {
      newErrors.institution_contribution = "Institution contribution cannot exceed 100%.";
    }

    if (formData.rate_type === "percentage" && Number(formData.liable_party_contribution) > 100)
      newErrors.liable_party_contribution = "Liable party contribution cannot exceed 100%.";

    if (formData.has_rules && formData.rules.length === 0)
      newErrors.rules = "At least one rule is required when rules are enabled";

    if (formData.is_applicable_to_invoice_or_bill && !formData.applicability)
      newErrors.applicability = "Please select an applicability option.";

    if (Object.keys(newErrors).length > 0 || !taxAccount) {
      setErrors(newErrors);
      return;
    }

    const payload: Partial<ITaxFormData> = {};

    if (!tax) {
      payload.tax_name = formData.tax_name;
      payload.description = formData.description;
      payload.is_statutory_obligation = formData.is_statutory_obligation;
      payload.rate_type = formData.rate_type;
      payload.is_inclusive = formData.is_inclusive;
      payload.liable_party_contribution = formData.liable_party_contribution;
      payload.has_rules = formData.has_rules;
      payload.rule_application_type = formData.has_rules ? formData.rule_application_type : null;
      payload.is_applicable_to_invoice_or_bill = formData.is_applicable_to_invoice_or_bill;

      payload.tax_account = taxAccount;

      if (formData.reference_code?.trim()) payload.reference_code = formData.reference_code;
      payload.institution_contribution = formData.is_institution_contribution
        ? formData.institution_contribution
        : null;
      if (formData.is_applicable_to_invoice_or_bill) {
        payload.applicability = formData.applicability;
      }
      if (formData.has_rules) {
        payload.rules = formData.rules;
      }
    } else {
      if (formData.tax_name !== tax.tax_name) payload.tax_name = formData.tax_name;
      if (formData.description !== (tax.description || ""))
        payload.description = formData.description;
      if (formData.is_statutory_obligation !== tax.is_statutory_obligation)
        payload.is_statutory_obligation = formData.is_statutory_obligation;
      if (formData.rate_type !== tax.rate_type) payload.rate_type = formData.rate_type;
      if (formData.is_inclusive !== tax.is_inclusive) payload.is_inclusive = formData.is_inclusive;
      if (formData.liable_party_contribution !== tax.liable_party_contribution)
        payload.liable_party_contribution = formData.liable_party_contribution;
      if (formData.has_rules !== tax.has_rules) payload.has_rules = formData.has_rules;
      const ruleApplicationType = formData.has_rules ? formData.rule_application_type : null;
      if (ruleApplicationType !== tax.rule_application_type)
        payload.rule_application_type = ruleApplicationType;
      if (
        formData.is_applicable_to_invoice_or_bill !==
        (tax.is_applicable_to_invoice_or_bill ?? false)
      )
        payload.is_applicable_to_invoice_or_bill = formData.is_applicable_to_invoice_or_bill;
      if (formData.applicability !== (tax.applicability ?? null))
        payload.applicability = formData.applicability;
      const institutionContribution = formData.is_institution_contribution
        ? formData.institution_contribution
        : null;
      if (institutionContribution !== tax.institution_contribution) {
        payload.institution_contribution = institutionContribution;
      }
      if (formData.has_rules) payload.rules = formData.rules;

      payload.tax_account = taxAccount;

      if (Object.keys(payload).length === 0) {
        showSuccessToast("No changes to save");
        return;
      }
    }

    onSubmit(
      payload as ITaxFormData,
      () => {},
      (errors) => setErrors(errors),
    );
  };

  const isPercentage = formData.rate_type === "percentage";

  return (
    <form onSubmit={handleSubmit} className="space-y-0">
      <FormSection
        title="Basic Information"
        description="General details about this deduction or statutory obligation."
        className="pt-2"
      >
        <div className="flex flex-col gap-4 !space-y-0 sm:flex-row sm:items-stretch sm:[&>div]:flex sm:[&>div]:flex-col sm:[&>div]:justify-center">
          <SwitchSetting
            className="min-w-0 flex-1"
            id="is_statutory_obligation"
            checked={formData.is_statutory_obligation}
            onCheckedChange={(checked) => setField("is_statutory_obligation", checked)}
            label="Statutory obligation"
            description="Enable for obligations required by law, such as PAYE or NSSF. Leave off for other deductions."
          />
          <div className="min-w-0 flex-1 sm:border-l sm:border-border sm:pl-4">
            <ReferenceCodeInput
              label="Reference Code"
              prefix="TAX"
              value={referenceCode}
              onChange={(value) => setReferenceCode(value)}
              error={errors.reference_code}
              disabled={!!tax}
            />
          </div>
        </div>

        <div>
          <Label required htmlFor="tax_name">
            Name
          </Label>
          <Input
            id="tax_name"
            value={formData.tax_name}
            onChange={(e) => setField("tax_name", e.target.value)}
            placeholder="e.g., PAYE, NSSF, Staff Savings"
            description="Enter the name of the deduction or statutory obligation."
          />
          {errors.tax_name && <p className="text-xs text-destructive mt-1">{errors.tax_name}</p>}
        </div>

        <div className="lg:col-span-1 space-y-2">
          <Label required htmlFor="tax_account">
            Ledger Account
          </Label>
          <PaginatedSearchableSelect<IAccount>
            key={tax?.base_uuid ?? "new"}
            idKey="base_uuid"
            valueKey="base_uuid"
            labelKey="account_name"
            labelDescKey="reference_code"
            fetchFirstPage={ACCOUNTS_API.fetchAccounts}
            fetchFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
            fetchById={(accountId) => ACCOUNTS_API.fetchAccountById({accountId})}
            value={taxAccount ?? undefined}
            onValueChange={() => {}}
            onItemSelected={(account) => setTaxAccount(account?.base_uuid ?? null)}
            placeholder="Select account"
            searchPlaceholder="Search accounts..."
            emptyMessage="No accounts found"
            initialData={
              taxAccount ? initialAccounts.filter((a) => a.base_uuid === taxAccount) : []
            }
            description="Link the ledger account used for this deduction or obligation."
            createAction={{
              label: "Create new account",
              onClick: () => {
                onAccountCreatedCallbackRef.current = (id: string, name: string) => {
                  setTaxAccount(id);
                  setInitialAccounts((prev) => [
                    ...prev,
                    {base_uuid: id, account_name: name} as any,
                  ]);
                };
                setShowCreateAccountPanel(true);
              },
            }}
          />
          {showTaxAccountErrors && !taxAccount && (
            <p className="text-xs text-destructive mt-1">Account is required</p>
          )}
        </div>
        <div className="flex flex-col gap-4 !space-y-0 sm:flex-row sm:items-stretch sm:[&>div]:flex sm:[&>div]:flex-col sm:[&>div]:justify-center">
          <SwitchSetting
            className="min-w-0 flex-1"
            label="Included in gross amount"
            description="The calculated amount is already included in the gross amount."
            id="is_inclusive"
            checked={formData.is_inclusive}
            onCheckedChange={(checked) => {
              setFormData((prev) => ({
                ...prev,
                is_inclusive: checked,
                ...(!checked ? {tax_amount: "0", tax_rate: undefined} : {}),
              }));
            }}
          />
          <SwitchSetting
            className="min-w-0 flex-1 sm:border-l sm:border-border sm:pl-4"
            label="Applicable to invoice or bill"
            description="Indicates whether this deduction or obligation applies to invoices, bills, or both."
            id="is_applicable_to_invoice_or_bill"
            checked={!!formData.is_applicable_to_invoice_or_bill}
            onCheckedChange={(checked) => {
              setFormData((prev) => ({
                ...prev,
                is_applicable_to_invoice_or_bill: checked,
                ...(!checked ? {applicability: null} : {}),
              }));
            }}
          />
        </div>
        {formData.is_applicable_to_invoice_or_bill && (
          <div className="lg:col-span-1">
            <Label htmlFor="applicability">
              Applicability <span className="text-destructive">*</span>
            </Label>
            <Select
              value={formData.applicability ?? ""}
              onValueChange={(value) => setField("applicability", value)}
            >
              <SelectTrigger description="Select whether this applies to invoices, bills, or both.">
                <SelectValue placeholder="Select applicability" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="BOTH" description="Apply to customer invoices and vendor bills.">
                  Both
                </SelectItem>
                <SelectItem value="INVOICE_ONLY" description="Apply only to customer invoices.">
                  Invoice Only
                </SelectItem>
                <SelectItem value="BILL_ONLY" description="Apply only to vendor bills.">
                  Bill Only
                </SelectItem>
              </SelectContent>
            </Select>
            {errors.applicability && (
              <p className="text-xs text-destructive mt-1">{errors.applicability}</p>
            )}
          </div>
        )}
      </FormSection>

      <FormSection
        title="Other Configuration"
        description="Settings that determine how the amount is calculated and applied."
        className="py-4"
        gridClassName="items-start"
      >
        <div className="flex flex-col gap-4 !space-y-0 sm:flex-row sm:items-stretch sm:[&>div]:flex sm:[&>div]:flex-col sm:[&>div]:justify-center">
          <div className="min-w-0 flex-1 space-y-2">
            <Label htmlFor="rate_type">Rate Type</Label>
            <Select
              value={formData.rate_type}
              onValueChange={(value: "percentage" | "fixed") => setField("rate_type", value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select rate type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  value="percentage"
                  description="Calculate a percentage of the applicable amount."
                >
                  Percentage
                </SelectItem>
                <SelectItem
                  value="fixed"
                  description="Use a fixed monetary amount instead of a percentage."
                >
                  Fixed Amount
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <SwitchSetting
            className="min-w-0 flex-1 sm:border-l sm:border-border sm:pl-4"
            label="Use calculation rules"
            description="Enable to calculate the amount using rules or value ranges."
            id="has_rules"
            checked={formData.has_rules}
            onCheckedChange={(checked) => {
              setFormData((prev) => ({
                ...prev,
                has_rules: checked,
                rule_application_type: checked
                  ? (prev.rule_application_type ?? "non_progressive")
                  : null,
                ...(!checked ? {rules: []} : {}),
              }));
            }}
          />
        </div>

        {!formData.has_rules && (
          <>
            {/* Institution contribution toggle */}
            <div className="flex flex-col gap-4 !space-y-0 sm:flex-row sm:items-stretch sm:[&>div]:flex sm:[&>div]:flex-col sm:[&>div]:justify-start">
              <SwitchSetting
                className="min-w-0 flex-1"
                label={
                  <>
                    Institution Contribution{" "}
                    {isPercentage && <span className="text-muted-foreground font-normal">(%)</span>}
                  </>
                }
                description="Enable if the institution contributes to this deduction or obligation. Leave blank if not applicable or determined by calculation rules."
                id="institution_contribution"
                checked={!!formData.is_institution_contribution}
                onCheckedChange={(checked) => {
                  setField("is_institution_contribution", checked);
                  if (!checked) setField("institution_contribution", null);
                }}
              />

              {/* Institution contribution */}
              {formData.is_institution_contribution && (
                <div className="min-w-0 flex-1 space-y-2 sm:border-l sm:border-border sm:pl-4">
                  <Label htmlFor="institution_contribution">
                    Institution Contribution{isPercentage ? " (%)" : ""}
                  </Label>
                  <FormattedNumberInput
                    value={formData.institution_contribution ?? ""}
                    onValueChange={(value) =>
                      setField("institution_contribution", value == null ? null : value.toString())
                    }
                    placeholder="0.00"
                    description="Contribution amount or percentage borne by the institution."
                  />
                  {errors.institution_contribution && (
                    <p className="text-xs text-destructive mt-1">
                      {errors.institution_contribution}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Liable party contribution */}
            <div className="lg:col-span-1">
              <Label htmlFor="liable_party_contribution">
                Liable Party Contribution{isPercentage ? " (%)" : ""}
              </Label>
              <FormattedNumberInput
                value={formData.liable_party_contribution ?? ""}
                onValueChange={(value) =>
                  setField("liable_party_contribution", value == null ? null : value.toString())
                }
                placeholder="0.00"
                description="Contribution borne by the liable party. Leave blank if determined by calculation rules."
              />
              {errors.liable_party_contribution && (
                <p className="text-xs text-destructive mt-1">{errors.liable_party_contribution}</p>
              )}
            </div>
          </>
        )}
      </FormSection>

      {/* ── Calculation Rules ── */}
      {formData.has_rules && (
        <div className="pt-8 space-y-6">
          <TaxRulesInput
            rules={formData.rules}
            onRulesChange={(rules) => setFormData((prev) => ({...prev, rules}))}
            onValidationChange={setRulesValid}
            taxType={formData.rule_application_type ?? "non_progressive"}
            onTaxTypeChange={(value) => setField("rule_application_type", value)}
            rateType={formData.rate_type}
            readonly={false}
          />
          {errors.rules && <p className="text-xs text-destructive mt-1">{errors.rules}</p>}
        </div>
      )}

      <div className="lg:col-span-2 pt-8">
        <Textarea
          id="description"
          label="Notes"
          value={formData.description}
          onChange={(e) => setField("description", e.target.value)}
          placeholder="Describe the purpose and application..."
          rows={3}
          showCount
          showOptional
          maxLength={230}
          description="Add details about the deduction or statutory obligation."
        />
        {errors.description && (
          <p className="text-xs text-destructive mt-1">{errors.description}</p>
        )}
      </div>

      {/* ── Actions ── */}
      <div className="flex justify-start gap-2 pt-6">
        <Button
          type="submit"
          className="w-1/2 h-12 rounded-full"
          disabled={
            isSubmitting || (formData.has_rules && (!rulesValid || formData.rules.length === 0))
          }
        >
          {isSubmitting
            ? "Saving..."
            : tax
              ? formData.is_statutory_obligation
                ? "Update Statutory Obligation"
                : "Update Deduction"
              : formData.is_statutory_obligation
                ? "Add Statutory Obligation"
                : "Add Deduction"}
        </Button>
      </div>

      <CreateAccountPanel
        open={showCreateAccountPanel}
        onClose={() => {
          setShowCreateAccountPanel(false);
          onAccountCreatedCallbackRef.current = null;
        }}
        onCreated={(id, name) => {
          onAccountCreatedCallbackRef.current?.(id, name);
          setShowCreateAccountPanel(false);
          onAccountCreatedCallbackRef.current = null;
        }}
        title="New Ledger Account"
      />
    </form>
  );
}
