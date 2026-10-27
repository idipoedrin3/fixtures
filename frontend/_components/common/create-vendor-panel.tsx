"use client";

import {useCallback, useState} from "react";
import {useSelector} from "react-redux";
import {ACCOUNTS_API, CURRENCIES_API, PAYMENT_TERMS_API, VENDORS_API} from "#/_api/api.helpers";
import {showSuccessToast} from "#/_api/helpers";
import {showErrorToast} from "#/_lib/utils";
import FormattedNumberInput from "#/_components/common/inputs/formatted-number-input";
import {LocationAutocomplete} from "#/_components/custom/location-autocomplete";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {PhoneNumberInput} from "#/_components/custom/phone-number-input";
import {SlideOverPanel} from "#/_components/common/slide-over-pannel";
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
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {
  type Currency,
  type IPaymentTerm,
  type IVendor,
  type IVendorFormData,
  type IVendorType,
} from "#/_types/api.types";
import type {ICountry} from "#/_types/types.utils";
import {CreatePaymentTermPanel} from "#/(dashboard)/customers/_components/create-payment-terms-panel";
import ReferenceCodeInput from "../custom/reference-code-input";
import BeneficiaryPaymentMethodsInput, {
  serializePaymentMethodDraft,
} from "#/(dashboard)/requisitions/_components/beneficiary-payment-methods-input";
import SwitchSetting from "#/_components/common/inputs/switch-setting";
import ExchangeRateInput from "#/_components/custom/exchange-rate-input";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (id: string, name: string, vendor: IVendor) => void;
}

const VENDOR_TYPE_OPTIONS: {value: IVendorType; label: string}[] = [
  {value: "individual", label: "Individual"},
  {value: "business", label: "Business"},
];

const EMPTY_FORM: IVendorFormData = {
  vendor_name: "",
  vendor_type: "individual",
  reference_code: "",
  address: "",
  phone_number: "",
  email: "",
  gender: "",
  currency: "",
  default_account_payable: "",
  opening_balance_account: "",
  tax_identification_number: null,
  opening_balance: "",
  opening_balance_received_date: new Date().toISOString().split("T")[0],
  payment_term: undefined,
  payment_options: [],
  website: "",
};

export function CreateVendorPanel({open, onClose, onCreated}: Props) {
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [formData, setFormData] = useState<IVendorFormData>(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [phoneCountry, setPhoneCountry] = useState<ICountry | null>(null);
  const [selectedCurrency, setSelectedCurrency] = useState<Currency | null>(null);
  const [hasOpeningBalance, setHasOpeningBalance] = useState(false);
  const [selectedPaymentTerm, setSelectedPaymentTerm] = useState<IPaymentTerm | null>(null);
  const [preselectedPaymentTermLabel, setPreselectedPaymentTermLabel] = useState<
    string | undefined
  >();
  const [showCreatePaymentTerm, setShowCreatePaymentTerm] = useState(false);
  const [paymentOptionsValid, setPaymentOptionsValid] = useState(true);
  const [hasNonCashPaymentMethods, setHasNonCashPaymentMethods] = useState(false);

  const setField = (key: keyof IVendorFormData, value: any) => {
    setFormData((prev) => ({...prev, [key]: value}));
    if (errors[key as string]) setErrors((prev) => ({...prev, [key]: ""}));
  };

  const handleClose = () => {
    setFormData(EMPTY_FORM);
    setErrors({});
    setHasOpeningBalance(false);
    setSelectedCurrency(null);
    setSelectedPaymentTerm(null);
    setPreselectedPaymentTermLabel(undefined);
    setPaymentOptionsValid(true);
    setHasNonCashPaymentMethods(false);
    onClose();
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.vendor_name.trim()) newErrors.vendor_name = "Vendor name is required";
    if (!formData.currency) newErrors.currency = "Currency is required";
    if (!formData.address.trim()) newErrors.address = "Address is required";
    if (!formData.phone_number.trim()) newErrors.phone_number = "Phone number is required";
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email))
      newErrors.email = "Please provide a valid email";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate() || !currentInstitution) return;
    setIsSubmitting(true);

    try {
      const optionalFields: (keyof IVendorFormData)[] = [
        "reference_code",
        "gender",
        "tax_identification_number",
        "payment_term",
        "website",
        "default_account_payable",
        "opening_balance_account",
        "foreign_exchange_rate",
      ];

      const alwaysExclude = [
        "opening_balance",
        "opening_balance_received_date",
        "opening_balance_account",
        "foreign_exchange_rate",
      ];

      const isEmpty = (value: unknown) =>
        value === "" || value === null || value === undefined || value === 0 || value === "0";

      const cleanedPayload = Object.fromEntries(
        Object.entries(formData).filter(([key, value]) => {
          if (alwaysExclude.includes(key)) {
            return hasOpeningBalance && !isEmpty(value);
          }

          if (key === "payment_options") {
            return Array.isArray(value) && value.length > 0;
          }

          if (optionalFields.includes(key as keyof IVendorFormData)) {
            return !isEmpty(value);
          }

          return true;
        }),
      ) as IVendorFormData;

      if (cleanedPayload.payment_options) {
        cleanedPayload.payment_options = cleanedPayload.payment_options.map(
          serializePaymentMethodDraft,
        ) as IVendorFormData["payment_options"];
      }

      const created = await VENDORS_API.createVendor({data: cleanedPayload});
      showSuccessToast("Vendor created successfully");
      onCreated(String(created.id), created.vendor_name, created);

      setFormData(EMPTY_FORM);
      setHasOpeningBalance(false);
    } catch (error: any) {
      showErrorToast({error, defaultMessage: "Failed to create vendor"});
    } finally {
      setIsSubmitting(false);
    }
  };

  const fetchPaymentTerms = useCallback(
    ({search}: any) => PAYMENT_TERMS_API.fetchPaymentTerms({page: 1, search}),
    [],
  );

  const isForeignCurrency =
    !!formData.currency &&
    !!currentInstitution?.currency?.id &&
    Number(formData.currency) !== Number(currentInstitution.currency.id);

  const showExchangeRate =
    hasOpeningBalance && Number(formData.opening_balance) !== 0 && isForeignCurrency;

  return (
    <>
      <SlideOverPanel
        open={open}
        onClose={handleClose}
        title="Create Vendor"
        description="Add a new vendor to select from."
        onSubmit={handleSubmit}
        submitLabel="Create Vendor"
        isSubmitting={isSubmitting}
        submitDisabled={!paymentOptionsValid}
        width="lg"
        height="100vh"
      >
        <div className="space-y-5">
          <section>
            <div className="space-y-4">
              <div className="space-y-1">
                <ReferenceCodeInput
                  label="Vendor Code"
                  prefix="VND"
                  value={formData.reference_code ?? ""}
                  onChange={(value) => setField("reference_code", value)}
                  error={errors.reference_code}
                />
              </div>
              <div className="space-y-1">
                <Label required>Vendor Name</Label>
                <Input
                  value={formData.vendor_name}
                  onChange={(e) => setField("vendor_name", e.target.value)}
                  placeholder="Enter vendor name"
                  className={`rounded-xl ${errors.vendor_name ? "border-red-500" : ""}`}
                />
                {errors.vendor_name && <p className="text-xs text-red-500">{errors.vendor_name}</p>}
              </div>

              <div className="space-y-1">
                <Label required>Vendor Type</Label>
                <Select
                  value={formData.vendor_type}
                  onValueChange={(v) => setField("vendor_type", v as IVendorType)}
                >
                  <SelectTrigger className="rounded-xl">
                    <SelectValue placeholder="Select vendor type" />
                  </SelectTrigger>
                  <SelectContent className="z-[1100]">
                    {VENDOR_TYPE_OPTIONS.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label required>Gender</Label>
                {formData.vendor_type === "individual" ? (
                  <Select value={formData.gender} onValueChange={(v) => setField("gender", v)}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue placeholder="Select gender" />
                    </SelectTrigger>
                    <SelectContent className="z-[1100]">
                      <SelectItem value="MALE">Male</SelectItem>
                      <SelectItem value="FEMALE">Female</SelectItem>
                      <SelectItem value="OTHER">Other</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value="OTHER"
                    readOnly
                    className="rounded-xl bg-gray-100 text-gray-500 cursor-not-allowed"
                  />
                )}
              </div>

              <div className="space-y-1 pt-4">
                <Label showOptional>Tax Identification Number</Label>
                <Input
                  value={formData.tax_identification_number ?? ""}
                  onChange={(e) => {
                    const val = e.target.value.trim();
                    setField("tax_identification_number", val === "" ? null : val);
                  }}
                  placeholder="e.g. 1234567890"
                  className="rounded-xl"
                />
              </div>
            </div>
          </section>

          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Contact Information
            </p>
            <div className="space-y-4">
              <div className="space-y-1">
                <Label required>Address</Label>
                <LocationAutocomplete
                  value={formData.address}
                  onChange={(value) => setField("address", value)}
                  placeholder="Search for address..."
                  showCurrentLocationButton={true}
                  className="rounded-xl"
                />
                {errors.address && <p className="text-xs text-red-500">{errors.address}</p>}
              </div>

              <div className="space-y-1">
                <PhoneNumberInput
                  label="Phone Number"
                  required
                  value={formData.phone_number}
                  country={phoneCountry}
                  onChange={({country, phoneNumber}) => {
                    setPhoneCountry(country);
                    setField("phone_number", phoneNumber);
                  }}
                  error={errors.phone_number || null}
                />
              </div>

              <div className="space-y-1">
                <Label showOptional>Email</Label>
                <Input
                  type="email"
                  placeholder="vendor@company.com"
                  value={formData.email}
                  onChange={(e) => setField("email", e.target.value)}
                  className={`rounded-xl ${errors.email ? "border-red-500" : ""}`}
                />
                {errors.email && <p className="text-xs text-red-500">{errors.email}</p>}
              </div>

              <div className="space-y-1">
                <Label showOptional>Website</Label>
                <Input
                  type="url"
                  value={formData.website}
                  onChange={(e) => setField("website", e.target.value)}
                  placeholder="https://vendor.com"
                  className="rounded-xl"
                />
              </div>
            </div>
          </section>

          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Financial Information
            </p>
            <div className="space-y-4">
              <div className="space-y-1">
                <Label required>Currency</Label>
                <PaginatedSearchableSelect
                  idKey="id"
                  valueKey="id"
                  labelKey="name"
                  labelDescKey="code"
                  onValueChange={(values) => {
                    setField("currency", Number(values[0]) || "");
                    setField("foreign_exchange_rate", undefined);
                  }}
                  onItemSelected={(currency) => {
                    setSelectedCurrency(currency);
                    setField("foreign_exchange_rate", undefined);
                  }}
                  placeholder="Select currency"
                  fetchFirstPage={CURRENCIES_API.fetchFirstPage}
                  fetchFromUrl={CURRENCIES_API.fetchFromUrl}
                  query={{is_institution_supported: "true"}}
                />
                {errors.currency && <p className="text-xs text-red-500">{errors.currency}</p>}
              </div>

              <div className="space-y-1 pt-2">
                <Label showOptional>Accounts Payable</Label>
                <PaginatedSearchableSelect
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  labelKey="account_name"
                  labelDescKey="reference_code"
                  onValueChange={(values) => setField("default_account_payable", values[0] || "")}
                  placeholder="Select default accounts payable"
                  fetchFirstPage={(query) =>
                    ACCOUNTS_API.fetchAccounts({
                      ...query,
                      system_group_account_type_choice: ["liability"],
                      has_children: false,
                    })
                  }
                  fetchFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
                  disabled={!formData.currency}
                  query={{currency: formData.currency || ""}}
                />
              </div>

              <div className="flex flex-col gap-2 mt-5 ml-4 pt-4">
                <div className="flex items-center gap-4">
                  <Switch
                    id="has-opening-balance"
                    checked={hasOpeningBalance}
                    onCheckedChange={(checked) => {
                      setHasOpeningBalance(checked);
                      if (!checked) {
                        setField("opening_balance", "");
                        setField(
                          "opening_balance_received_date",
                          new Date().toISOString().split("T")[0],
                        );
                        setField("foreign_exchange_rate", undefined);
                      }
                    }}
                  />
                  <Label
                    htmlFor="has-opening-balance"
                    className="font-medium text-gray-700 cursor-pointer"
                  >
                    Record Opening Balance
                  </Label>
                </div>
                <span className="text-sm text-muted-foreground">
                  Enable this if the vendor has an outstanding balance at the time of setup.
                </span>
              </div>

              {hasOpeningBalance && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="op-balance" required>
                      Opening Balance
                    </Label>
                    <FormattedNumberInput
                      id="op-balance"
                      value={formData.opening_balance}
                      onValueChange={(value) => {
                        setField("opening_balance", value);
                      }}
                      placeholder="0.00"
                      className={`rounded-xl ${errors.opening_balance ? "border-red-500" : ""}`}
                      description="Use a positive balance when you owe the vendor, or a negative balance for a vendor prepayment."
                    />
                    {errors.opening_balance && (
                      <p className="text-sm text-red-500">{errors.opening_balance}</p>
                    )}
                  </div>

                  {Number(formData.opening_balance) ? (
                    <div className="space-y-2">
                      <Label htmlFor="op-balance-date">Opening Balance Received Date</Label>
                      <Input
                        id="op-balance-date"
                        type="date"
                        value={formData.opening_balance_received_date}
                        onChange={(e) => setField("opening_balance_received_date", e.target.value)}
                        className={`rounded-xl ${errors.opening_balance_received_date ? "border-red-500" : ""}`}
                        description="Select the date when the opening balance was received."
                      />
                      {errors.opening_balance_received_date && (
                        <p className="text-sm text-red-500">
                          {errors.opening_balance_received_date}
                        </p>
                      )}
                    </div>
                  ) : null}
                  <div className="space-y-2 pt-4">
                    <Label showOptional>Opening Balance Account</Label>
                    <PaginatedSearchableSelect
                      idKey="base_uuid"
                      valueKey="base_uuid"
                      labelKey="account_name"
                      labelDescKey="reference_code"
                      onValueChange={(values) => {
                        setField("opening_balance_account", values[0] || "");
                      }}
                      placeholder="Select opening balance account"
                      fetchFirstPage={(query) =>
                        ACCOUNTS_API.fetchAccounts({
                          ...query,
                          system_group_account_type_choice: ["equity"],
                          has_children: false,
                        })
                      }
                      fetchFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
                    />
                  </div>

                  {showExchangeRate && currentInstitution?.currency && selectedCurrency && (
                    <div className="space-y-3 py-3">
                      <div>
                        <h3 className="font-semibold">Opening Balance Currency</h3>
                        <p className="text-sm text-muted-foreground">
                          Use the institution&apos;s configured rate or provide a custom rate.
                        </p>
                      </div>

                      <ExchangeRateInput
                        baseCurrency={currentInstitution.currency}
                        transactionCurrency={selectedCurrency}
                        value={formData.foreign_exchange_rate}
                        onChange={(exchangeRate) => setField("foreign_exchange_rate", exchangeRate)}
                      />
                    </div>
                  )}
                </>
              )}

              <div className="space-y-1 pt-2">
                <Label showOptional>Payment Terms</Label>
                <PaginatedSearchableSelect<IPaymentTerm>
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  labelKey="term_name"
                  labelDescKey="days_until_due"
                  fetchFirstPage={fetchPaymentTerms}
                  fetchFromUrl={({url}) => PAYMENT_TERMS_API.fetchPaymentTermsFromUrl({url})}
                  initialData={selectedPaymentTerm ? [selectedPaymentTerm] : undefined}
                  value={formData.payment_term || undefined}
                  onValueChange={(values) => setField("payment_term", values[0] || undefined)}
                  initialSelectedLabel={preselectedPaymentTermLabel}
                  createAction={{
                    label: "Create new term",
                    onClick: () => setShowCreatePaymentTerm(true),
                  }}
                  placeholder="Select payment terms"
                  popoverContainer={typeof document !== "undefined" ? document.body : undefined}
                />
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Payment Methods</h3>
              <p className="text-sm text-muted-foreground">
                Configure how non-cash payments are sent to this vendor.
              </p>
            </div>

            <SwitchSetting
              id="panel-has-non-cash-payment-methods"
              label="Vendor accepts non-cash payments"
              description="Enable this to configure bank, mobile money, or digital-wallet payment methods for this vendor."
              checked={hasNonCashPaymentMethods}
              onCheckedChange={(checked) => {
                setHasNonCashPaymentMethods(checked);
                setField("payment_options", []);
                setPaymentOptionsValid(!checked);
              }}
              className="rounded-lg border bg-muted/30 p-4"
            />

            {hasNonCashPaymentMethods && (
              <BeneficiaryPaymentMethodsInput
                layout="table"
                value={formData.payment_options ?? []}
                onChange={(options) => setField("payment_options", options)}
                onValidationChange={setPaymentOptionsValid}
              />
            )}
          </section>
        </div>
      </SlideOverPanel>

      <CreatePaymentTermPanel
        open={showCreatePaymentTerm}
        onClose={() => setShowCreatePaymentTerm(false)}
        onCreated={(id, name, term) => {
          setPreselectedPaymentTermLabel(name);
          setSelectedPaymentTerm(term);
          setField("payment_term", id);
          setShowCreatePaymentTerm(false);
        }}
      />
    </>
  );
}
