"use client";

import {useCallback, useState} from "react";
import {useSelector} from "react-redux";
import {
  ACCOUNTS_API,
  CURRENCIES_API,
  CUSTOMERS_API,
  PAYMENT_TERMS_API,
  SALES_PERSON_API,
} from "#/_api/api.helpers";
import {showSuccessToast} from "#/_api/helpers";
import {showErrorToast} from "#/_lib/utils";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import ExchangeRateInput from "#/_components/custom/exchange-rate-input";
import type {IExchangeRateInput} from "#/_api/services/system.service";
import {LocationAutocomplete} from "#/_components/custom/location-autocomplete";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import PhoneNumberInput from "#/_components/custom/phone-number-input";
import {SlideOverPanel} from "#/_components/common/slide-over-pannel";
import {CUSTOMER_TYPES} from "#/_constants";
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
  buildCustomerPayload,
  type Currency,
  type ICustomer,
  type ICustomerFormData,
  type ICustomerType,
  type IPaymentTerm,
  type ISalesPerson,
} from "#/_types/api.types";
import type {ICountry} from "#/_types/types.utils";
import {CreatePaymentTermPanel} from "#/(dashboard)/customers/_components/create-payment-terms-panel";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (id: string, name: string, customer: ICustomer) => void;
}

const customerTypeOptions: {value: ICustomerType; label: string}[] = CUSTOMER_TYPES as {
  value: ICustomerType;
  label: string;
}[];

const EMPTY_FORM: Omit<ICustomerFormData, "profile_photo"> = {
  customer_name: "",
  customer_type: "business",
  credit_limit: "",
  outstanding_receivables_balance: "",
  address: "",
  phone_number: "",
  email: "",
  payment_term: "",
  gender: "OTHER",
  currency: "",
  opening_balance: "0",
  opening_balance_account: "",
  opening_balance_received_date: new Date().toISOString().split("T")[0],
  tin: "",
  reference_code: "",
  default_account: undefined,
  //salesperson: undefined,
};

export function CreateCustomerPanel({open, onClose, onCreated}: Props) {
  const currentInstitution = useSelector(selectSelectedInstitution);

  const [profilePhotoFile, setProfilePhotoFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [phoneCountry, setPhoneCountry] = useState<ICountry | null>(null);
  const [isPhoneValid, setIsPhoneValid] = useState(false);
  const [hasOpeningBalance, setHasOpeningBalance] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState<Currency | null>(null);
  const [selectedPaymentTerm, setSelectedPaymentTerm] = useState<IPaymentTerm | null>(null);
  const [selectedSalesPerson, setSelectedSalesPerson] = useState<ISalesPerson | null>(null);
  const [showCreatePaymentTerm, setShowCreatePaymentTerm] = useState(false);
  const [preselectedPaymentTermLabel, setPreselectedPaymentTermLabel] = useState<
    string | undefined
  >();
  const [showCreateSalesPerson, setShowCreateSalesPerson] = useState(false);
  const [preselectedSalesPersonLabel, setPreselectedSalesPersonLabel] = useState<
    string | undefined
  >();

  const setField = (
    field: keyof Omit<ICustomerFormData, "profile_photo">,
    value: string | number | IExchangeRateInput | null | undefined,
  ) => {
    setFormData((prev) => ({...prev, [field]: value}));
    if (errors[field]) setErrors((prev) => ({...prev, [field]: ""}));
  };

  const handleClose = () => {
    setFormData(EMPTY_FORM);
    setProfilePhotoFile(null);
    setPreviewUrl(null);
    setErrors({});
    setHasOpeningBalance(false);
    setSelectedCurrency(null);
    setSelectedPaymentTerm(null);
    //setSelectedSalesPerson(null);
    setPreselectedPaymentTermLabel(undefined);
    // setPreselectedSalesPersonLabel(undefined);
    onClose();
  };

  const validateEmail = (email: string) => {
    if (!email) return true;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.customer_name.trim()) {
      newErrors.customer_name =
        formData.customer_type === "business"
          ? "Business name is required"
          : "Customer name is required";
    }
    if (!formData.currency) newErrors.currency = "Currency is required";
    if (!formData.customer_type) newErrors.customer_type = "Customer type is required";
    if (!formData.address.trim()) newErrors.address = "Address is required";
    if (!formData.phone_number.trim() || !isPhoneValid)
      newErrors.phone_number = "Valid phone number is required";
    if (!validateEmail(formData.email)) newErrors.email = "Please provide a valid email";

    const cl = formData.credit_limit;
    if (cl && isNaN(Number(cl))) newErrors.credit_limit = "Credit limit must be a number";

    const ob = formData.opening_balance;
    if (ob && isNaN(Number(ob))) newErrors.outstanding_receivables = "Balance must be a number";

    if (!formData.opening_balance_received_date && isNaN(Number(formData.opening_balance))) {
      newErrors.opening_balance_received_date = "Opening balance received date is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate() || !currentInstitution) return;

    try {
      setIsSubmitting(true);

      const optionalFields: (keyof Omit<ICustomerFormData, "profile_photo">)[] = [
        "reference_code",
        "tin",
        "default_account",
        "payment_term",
        // "salesperson",
        "deposit_distribution_strategy",
        "foreign_exchange_rate",
        "opening_balance_account",
        "credit_limit",
        "outstanding_receivables_balance",
      ];

      const isEmpty = (value: unknown) =>
        value === "" || value === null || value === undefined || value === 0 || value === "0";

      const cleanedFormData = Object.fromEntries(
        Object.entries(formData).filter(([key, value]) => {
          if (optionalFields.includes(key as keyof Omit<ICustomerFormData, "profile_photo">)) {
            return !isEmpty(value);
          }
          return true;
        }),
      ) as Omit<ICustomerFormData, "profile_photo">;

      if (!hasOpeningBalance) {
        delete (cleanedFormData as any).opening_balance;
        delete (cleanedFormData as any).opening_balance_received_date;
        delete (cleanedFormData as any).opening_balance_account;
        delete (cleanedFormData as any).foreign_exchange_rate;
      }

      const payload = await buildCustomerPayload({
        ...cleanedFormData,
        profile_photo: profilePhotoFile,
      });

      const created = await CUSTOMERS_API.createCustomer({customerData: payload});

      showSuccessToast("Customer created successfully");
      onCreated(String(created.id), created.customer_name, created);

      setFormData(EMPTY_FORM);
      setProfilePhotoFile(null);
      setPreviewUrl(null);
      setHasOpeningBalance(false);
    } catch (error: any) {
      showErrorToast({error, defaultMessage: "Failed to create customer"});
    } finally {
      setIsSubmitting(false);
    }
  };

  const isForeignCurrency =
    !!formData.currency &&
    !!currentInstitution?.currency?.id &&
    Number(formData.currency) !== Number(currentInstitution.currency.id);

  const showExchangeRate =
    hasOpeningBalance && Number(formData.opening_balance) !== 0 && isForeignCurrency;

  const fetchPaymentTerms = useCallback(
    ({search}: any) => PAYMENT_TERMS_API.fetchPaymentTerms({page: 1, search}),
    [],
  );

  return (
    <>
      <SlideOverPanel
        open={open}
        onClose={handleClose}
        title="Create Customer"
        description="Add a new customer to select from."
        onSubmit={handleSubmit}
        submitLabel="Create Customer"
        isSubmitting={isSubmitting}
        width="lg"
        height="100vh"
      >
        <div className="space-y-5">
          {/* ── Customer Profile ───────────────────────────────────────── */}
          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Customer Profile
            </p>
            <div className="space-y-4">
              <div className="space-y-1">
                <Label showOptional>Code</Label>
                <Input
                  placeholder="e.g. CTM-001"
                  value={formData.reference_code}
                  onChange={(e) => setField("reference_code", e.target.value)}
                  className="rounded-xl"
                />
              </div>

              <div className="space-y-1 pt-2">
                <Label required>Customer Type</Label>
                <Select
                  value={formData.customer_type}
                  onValueChange={(value) => setField("customer_type", value)}
                >
                  <SelectTrigger
                    className={`rounded-xl ${errors.customer_type ? "border-red-500" : ""}`}
                  >
                    <SelectValue placeholder="Select customer type" />
                  </SelectTrigger>
                  <SelectContent className="z-[1100]">
                    {customerTypeOptions.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.customer_type && (
                  <p className="text-xs text-red-500">{errors.customer_type}</p>
                )}
              </div>

              <div className="space-y-1 pt-2">
                <Label required>
                  {formData.customer_type === "business" ? "Business Name" : "Customer Name"}
                </Label>
                <Input
                  value={formData.customer_name}
                  onChange={(e) => setField("customer_name", e.target.value)}
                  placeholder={
                    formData.customer_type === "business"
                      ? "Enter business name"
                      : "Enter customer name"
                  }
                  className={`rounded-xl ${errors.customer_name ? "border-red-500" : ""}`}
                />
                {errors.customer_name && (
                  <p className="text-xs text-red-500">{errors.customer_name}</p>
                )}
              </div>

              <div className="space-y-1">
                <Label required>Gender</Label>
                {formData.customer_type === "individual" ? (
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

              <div className="space-y-1 pt-2">
                <Label showOptional>Tax Identification Number (TIN)</Label>
                <Input
                  value={formData.tin || ""}
                  onChange={(e) => setField("tin", e.target.value.trim())}
                  placeholder="e.g. 1234567890"
                  className="rounded-xl"
                />
              </div>

              <div className="space-y-1 pt-2">
                <Label showOptional>Profile Photo</Label>
                <div className="flex items-center gap-4">
                  {previewUrl && (
                    <img
                      src={previewUrl}
                      alt="Profile preview"
                      className="h-12 w-12 rounded-full object-cover border"
                    />
                  )}
                  <Input
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0] ?? null;
                      setProfilePhotoFile(file);
                      setPreviewUrl(file ? URL.createObjectURL(file) : null);
                    }}
                    className="rounded-xl file:mr-3 file:py-1 file:px-3 file:rounded-full file:border-0 file:text-sm file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                  />
                </div>
              </div>
            </div>
          </section>

          <hr className="border-gray-100" />

          {/* ── Contact Information ────────────────────────────────────── */}
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
                  onChange={({country, phoneNumber, isValid}) => {
                    setPhoneCountry(country);
                    setIsPhoneValid(isValid);
                    setField("phone_number", phoneNumber);
                  }}
                  error={errors.phone_number || null}
                />
              </div>

              <div className="space-y-1">
                <Label showOptional>Email</Label>
                <Input
                  type="email"
                  placeholder="name@company.com"
                  value={formData.email}
                  onChange={(e) => setField("email", e.target.value)}
                  className={`rounded-xl ${errors.email ? "border-red-500" : ""}`}
                />
                {errors.email && <p className="text-xs text-red-500">{errors.email}</p>}
              </div>
            </div>
          </section>

          <hr className="border-gray-100" />

          {/* ── Financial Information ──────────────────────────────────── */}
          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Financial Information
            </p>
            <div className="space-y-4">
              <div className="space-y-1">
                <Label showOptional>Accounts Receivable</Label>
                <PaginatedSearchableSelect
                  idKey="id"
                  valueKey="id"
                  labelKey="account_name"
                  labelDescKey="reference_code"
                  onValueChange={() => setField("default_account", undefined)}
                  placeholder="Select default accounts receivable"
                  fetchFirstPage={(query) =>
                    ACCOUNTS_API.fetchAccounts({
                      ...query,
                      system_group_account_type_choice: ["asset", "equity"],
                      has_children: false,
                    })
                  }
                  fetchFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
                />
              </div>

              <div className="space-y-1 pt-2">
                <Label required>Currency</Label>
                <PaginatedSearchableSelect<Currency>
                  idKey="id"
                  valueKey="id"
                  labelKey="name"
                  labelDescKey="code"
                  value={formData.currency || null}
                  initialData={selectedCurrency ? [selectedCurrency] : []}
                  onValueChange={(values) => {
                    setField("currency", values[0] || "");
                    setField("foreign_exchange_rate", undefined);
                  }}
                  onItemSelected={(currency) => {
                    setSelectedCurrency(currency);
                    setField("foreign_exchange_rate", undefined);
                  }}
                  placeholder="Select currency"
                  searchPlaceholder="Search currency..."
                  emptyMessage="No currency found"
                  fetchFirstPage={CURRENCIES_API.fetchFirstPage}
                  fetchFromUrl={CURRENCIES_API.fetchFromUrl}
                  query={{is_institution_supported: "true"}}
                />
                {errors.currency && <p className="text-xs text-red-500">{errors.currency}</p>}
              </div>

              <div className="flex flex-col gap-2 pt-4">
                <div className="flex items-center gap-3">
                  <Switch
                    id="panel-has-opening-balance"
                    checked={hasOpeningBalance}
                    onCheckedChange={(checked) => {
                      setHasOpeningBalance(checked);
                      if (!checked) {
                        setField("opening_balance", "0");
                        setField(
                          "opening_balance_received_date",
                          new Date().toISOString().split("T")[0],
                        );
                        setField("foreign_exchange_rate", undefined);
                      }
                    }}
                  />
                  <Label
                    htmlFor="panel-has-opening-balance"
                    className="cursor-pointer font-medium text-gray-700"
                  >
                    Record Opening Balance
                  </Label>
                </div>
                <span className="text-xs text-muted-foreground">
                  Enable this if the customer has an outstanding balance at the time of setup.
                </span>
              </div>

              {hasOpeningBalance && (
                <>
                  <div className="space-y-1">
                    <Label required>Opening Balance</Label>
                    <FormattedNumberInput
                      value={formData.opening_balance}
                      onValueChange={(value) => setField("opening_balance", value)}
                      placeholder="0.00"
                      className="rounded-xl"
                    />
                  </div>

                  {!!Number(formData.opening_balance) && (
                    <div className="space-y-1">
                      <Label>Opening Balance Received Date</Label>
                      <Input
                        type="date"
                        value={formData.opening_balance_received_date}
                        onChange={(e) => setField("opening_balance_received_date", e.target.value)}
                        className="rounded-xl"
                      />
                    </div>
                  )}

                  <div className="space-y-1">
                    <Label showOptional>Opening Balance Account</Label>
                    <PaginatedSearchableSelect
                      idKey="base_uuid"
                      valueKey="base_uuid"
                      labelKey="account_name"
                      labelDescKey="reference_code"
                      onValueChange={(values) =>
                        setField("opening_balance_account", values[0] || "")
                      }
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
                          Use the institution&apos;s configured rate or provide a custom rate for
                          this opening balance.
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
                <Label showOptional>Credit Limit</Label>
                <FormattedNumberInput
                  value={formData.credit_limit ?? ""}
                  onValueChange={(value) => setField("credit_limit", value)}
                  placeholder="0.00"
                  className={`rounded-xl ${errors.credit_limit ? "border-red-500" : ""}`}
                />
                {errors.credit_limit && (
                  <p className="text-xs text-red-500">{errors.credit_limit}</p>
                )}
              </div>

              <div className="space-y-1 pt-2">
                <Label showOptional>Payment Terms</Label>
                <PaginatedSearchableSelect<IPaymentTerm>
                  idKey="id"
                  valueKey="id"
                  labelKey="term_name"
                  labelDescKey="days_until_due"
                  fetchFirstPage={fetchPaymentTerms}
                  fetchFromUrl={({url}) => PAYMENT_TERMS_API.fetchPaymentTermsFromUrl({url})}
                  initialData={selectedPaymentTerm ? [selectedPaymentTerm] : undefined}
                  value={formData.payment_term || undefined}
                  onValueChange={(values) =>
                    setField("payment_term", values[0] ? Number(values[0]) : undefined)
                  }
                  initialSelectedLabel={preselectedPaymentTermLabel}
                  createAction={{
                    label: "Create new term",
                    onClick: () => setShowCreatePaymentTerm(true),
                  }}
                  placeholder="Select payment terms"
                  searchPlaceholder="Search payment terms..."
                  emptyMessage="No payment terms found"
                  popoverContainer={typeof document !== "undefined" ? document.body : undefined}
                />
              </div>

              <div className="space-y-1 pt-2">
                <Label showOptional>Deposit Distribution Strategy</Label>
                <Select
                  value={formData.deposit_distribution_strategy}
                  onValueChange={(val) => setField("deposit_distribution_strategy", val as any)}
                >
                  <SelectTrigger className="w-full rounded-xl">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent className="z-[1100]">
                    <SelectItem value="PAY_OLDEST_INVOICE_FIRST">
                      Pay Oldest Invoice First
                    </SelectItem>
                    <SelectItem value="PAY_LAST_INVOICE_FIRST">Pay Last Invoice First</SelectItem>
                    <SelectItem value="HOLD_AS_CREDIT">Hold as Customer Credit</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* <div className="space-y-1 pt-2">
                <Label showOptional>Sales Person</Label>
                <PaginatedSearchableSelect<ISalesPerson>
                  idKey="id"
                  valueKey="id"
                  labelKey="name"
                  labelDescKey="email"
                  initialData={selectedSalesPerson ? [selectedSalesPerson] : undefined}
                  value={formData.salesperson || undefined}
                  onValueChange={(values) => setField("salesperson", values[0] || "")}
                  placeholder="Select sales person"
                  searchPlaceholder="Search sales person..."
                  emptyMessage="No sales person found"
                  fetchFirstPage={SALES_PERSON_API.fetchSalesPersons}
                  fetchFromUrl={SALES_PERSON_API.fetchSalesPersonFromUrl}
                  initialSelectedLabel={preselectedSalesPersonLabel}
                  createAction={{
                    label: "Create new sales person",
                    onClick: () => setShowCreateSalesPerson(true),
                  }}
                />
              </div> */}
            </div>
          </section>
        </div>
      </SlideOverPanel>

      {/* Nested panels */}
      <CreatePaymentTermPanel
        open={showCreatePaymentTerm}
        onClose={() => setShowCreatePaymentTerm(false)}
        onCreated={(id, name, term) => {
          setPreselectedPaymentTermLabel(name);
          setSelectedPaymentTerm(term);
          setField("payment_term", Number(id));
          setShowCreatePaymentTerm(false);
        }}
      />
      {/* <CreateSalesPersonPanel
        open={showCreateSalesPerson}
        onClose={() => setShowCreateSalesPerson(false)}
        onCreated={(id, name, person) => {
          setPreselectedSalesPersonLabel(name);
          setSelectedSalesPerson(person);
          setField("salesperson", id);
          setShowCreateSalesPerson(false);
        }}
      /> */}
    </>
  );
}
