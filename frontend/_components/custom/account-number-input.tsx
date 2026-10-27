"use client";

import type {ICountry} from "#/_types/types.utils";

import {useEffect, useRef, useState} from "react";
import {CheckCircle2, Loader2} from "lucide-react";

import {countryAPI} from "#/_api/helpers";
import {
  ACCOUNT_VERIFICATION_API,
  IAccountVerificationOperator,
  IAccountVerificationResponse,
} from "#/_api/services/system.service";
import CountrySelect from "#/_components/custom/country-select";
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

export type AccountNumberType = "mobile_money" | "bank" | "digital_wallet";

interface AccountNumberInputProps {
  label?: string;
  value: string;
  country: ICountry | null;
  accountType?: AccountNumberType;
  onChange: (value: string) => void;
  onAccountTypeChange?: (accountType: AccountNumberType) => void;
  onCountryChange?: (country: ICountry | null) => void;
  onOperatorCodeChange?: (operatorCode: string) => void;
  defaultOperatorCode?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string | null;
  enableVerification?: boolean;
  showAccountTypeSelector?: boolean;
  notifyDefaultCountryOnLoad?: boolean;
}

export function AccountNumberInput({
  label = "Account Number",
  value,
  country,
  accountType = "bank",
  onChange,
  onAccountTypeChange,
  onCountryChange,
  onOperatorCodeChange,
  defaultOperatorCode = "",
  required = false,
  disabled = false,
  error,
  enableVerification = false,
  showAccountTypeSelector = true,
  notifyDefaultCountryOnLoad = true,
}: AccountNumberInputProps) {
  const [isVerifying, setIsVerifying] = useState(false);
  const [verification, setVerification] = useState<IAccountVerificationResponse | null>(null);
  const [verificationError, setVerificationError] = useState("");
  const [countries, setCountries] = useState<ICountry[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<ICountry | null>(country);
  const [isLoadingCountries, setIsLoadingCountries] = useState(true);
  const [nextCountriesUrl, setNextCountriesUrl] = useState<string | null>(null);
  const [operators, setOperators] = useState<IAccountVerificationOperator[]>([]);
  const [operatorCode, setOperatorCode] = useState(defaultOperatorCode);
  const onCountryChangeRef = useRef(onCountryChange);
  const onOperatorCodeChangeRef = useRef(onOperatorCodeChange);
  const [isLoadingOperators, setIsLoadingOperators] = useState(false);
  const countryCode = selectedCountry?.iso2 || "UG";

  useEffect(() => {
    if (country && country.iso2 !== selectedCountry?.iso2) {
      setSelectedCountry(country);
    }
  }, [country, selectedCountry]);

  useEffect(() => {
    onOperatorCodeChangeRef.current = onOperatorCodeChange;
  }, [onOperatorCodeChange]);

  useEffect(() => {
    setIsLoadingCountries(true);

    countryAPI
      .fetchPage()
      .then((data) => {
        setCountries(data.results);
        setNextCountriesUrl(data.next);

        if (!selectedCountry) {
          const defaultCountry = data.results.find((item) => item.iso2 === "UG") ?? null;
          if (defaultCountry) setSelectedCountry(defaultCountry);
        }
      })
      .finally(() => setIsLoadingCountries(false));
  }, [notifyDefaultCountryOnLoad]);

  const hasNotifiedDefaultRef = useRef(false);

  useEffect(() => {
    if (
      selectedCountry &&
      notifyDefaultCountryOnLoad &&
      !country &&
      !hasNotifiedDefaultRef.current
    ) {
      hasNotifiedDefaultRef.current = true;
      onCountryChangeRef.current?.(selectedCountry);
    }
  }, [selectedCountry, notifyDefaultCountryOnLoad, country]);

  const handleCountryChange = (country: ICountry | null) => {
    if (country?.iso2 === selectedCountry?.iso2) return;
    setSelectedCountry(country);
    onCountryChangeRef.current?.(country);
  };

  const handleCountrySearch = async (search: string) => {
    setIsLoadingCountries(true);

    try {
      const data = await countryAPI.fetchPage({search});

      setCountries(data.results);
      setNextCountriesUrl(data.next);
    } finally {
      setIsLoadingCountries(false);
    }
  };

  const loadMoreCountries = async () => {
    if (!nextCountriesUrl || isLoadingCountries) return;

    setIsLoadingCountries(true);

    try {
      const data = await countryAPI.fetchPage({url: nextCountriesUrl});

      setCountries((current) => [...current, ...data.results]);
      setNextCountriesUrl(data.next);
    } finally {
      setIsLoadingCountries(false);
    }
  };

  useEffect(() => {
    setOperatorCode(defaultOperatorCode);

    setVerification(null);
    setVerificationError("");

    if (accountType === "mobile_money") {
      setOperators([]);
      setOperatorCode("");
      return;
    }

    if (!selectedCountry || !enableVerification) {
      setOperators([]);
      return;
    }

    let active = true;
    setIsLoadingOperators(true);

    ACCOUNT_VERIFICATION_API.getOperators({
      accountType,
      countryCode: selectedCountry.iso2,
    })
      .then(({results}) => {
        if (active) setOperators(results);
      })
      .catch(() => {
        if (active) {
          setOperators([]);
          setVerificationError("Unable to load operators.");
        }
      })
      .finally(() => {
        if (active) setIsLoadingOperators(false);
      });

    return () => {
      active = false;
    };
  }, [accountType, defaultOperatorCode, enableVerification, selectedCountry]);

  useEffect(() => {
    setVerification(null);
    setVerificationError("");
  }, [value]);

  const handleVerify = async () => {
    if (!value.trim() || (accountType !== "mobile_money" && !operatorCode)) {
      return;
    }

    setIsVerifying(true);
    setVerification(null);
    setVerificationError("");

    try {
      const result =
        accountType === "mobile_money"
          ? await ACCOUNT_VERIFICATION_API.verifyMobileMoney({
              account_number: value.trim(),
              account_type: "mobile_money",
              country_code: countryCode,
            })
          : await ACCOUNT_VERIFICATION_API.verifyAccount({
              account_number: value.trim(),
              account_type: accountType,
              country_code: countryCode,
              operator_code: operatorCode,
            });

      setVerification(result);
    } catch {
      setVerificationError("Unable to verify this account.");
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="space-y-1">
      {label && (
        <Label required={required} showOptional={!required}>
          {label}
        </Label>
      )}

      <div
        className={`grid gap-2 ${
          showAccountTypeSelector
            ? "grid-cols-[6.5rem_6.5rem_minmax(0,1fr)]"
            : "grid-cols-[6.5rem_minmax(0,1fr)]"
        }`}
      >
        {showAccountTypeSelector && (
          <Select
            value={accountType}
            disabled={disabled}
            onValueChange={(value) => onAccountTypeChange?.(value as AccountNumberType)}
          >
            <SelectTrigger className="h-11 min-w-0 rounded-xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="mobile_money">Mobile Money</SelectItem>
              <SelectItem value="bank">Bank</SelectItem>
              <SelectItem value="digital_wallet">Digital Wallet</SelectItem>
            </SelectContent>
          </Select>
        )}

        <div className="min-w-0 [&>button]:h-11 [&>button]:w-full">
          <CountrySelect
            countries={countries}
            selectedCountry={selectedCountry}
            onCountryChange={handleCountryChange}
            onSearchChange={handleCountrySearch}
            onLoadMore={loadMoreCountries}
            hasMore={Boolean(nextCountriesUrl)}
            isLoading={isLoadingCountries}
            disabled={disabled}
            compact
            compactValue="iso2"
          />
        </div>

        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={
            accountType === "mobile_money" ? "Enter telephone number" : "Enter account number"
          }
          required={required}
          disabled={disabled}
          className={`h-11 min-w-0 rounded-xl ${error ? "border-red-500" : ""}`}
        />
      </div>

      {error && <p className="text-xs text-red-500">{error}</p>}

      {enableVerification && (
        <div className="space-y-2 pt-1">
          {accountType !== "mobile_money" && (
            <Select
              value={operatorCode}
              disabled={disabled || isLoadingOperators || operators.length === 0}
              onValueChange={(value) => {
                setOperatorCode(value);
                onOperatorCodeChange?.(value);
              }}
            >
              <SelectTrigger className="h-11 rounded-xl">
                <SelectValue
                  placeholder={
                    isLoadingOperators
                      ? "Loading Operators..."
                      : operators.length
                        ? "Select Operator"
                        : "No operators available"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {operators.map((operator) => (
                  <SelectItem key={operator.code} value={operator.code}>
                    <span className="flex items-center gap-2">
                      {operator.symbol_url && (
                        <img
                          src={operator.symbol_url}
                          alt=""
                          className="size-5 rounded-full object-contain"
                        />
                      )}
                      {operator.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full rounded-xl"
            disabled={
              disabled ||
              isVerifying ||
              !value.trim() ||
              (accountType !== "mobile_money" && !operatorCode)
            }
            onClick={handleVerify}
          >
            {isVerifying && <Loader2 className="size-4 animate-spin" />}
            {isVerifying ? "Verifying..." : "Verify Account"}
          </Button>

          {verificationError && <p className="text-xs text-red-500">{verificationError}</p>}

          {verification && (
            <div className="rounded-xl border border-green-200 bg-green-50 p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-green-700">
                <CheckCircle2 className="size-4" />
                VERIFIED
              </div>

              <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 border-t border-green-200 pt-3 text-sm">
                <dt className="text-slate-500">Account name</dt>
                <dd className="min-w-0 break-words font-medium text-slate-900">
                  {verification.data?.account_name || "—"}
                </dd>

                <dt className="text-slate-500">Account number</dt>
                <dd className="min-w-0 break-words font-medium text-slate-900">
                  {verification.data?.account_number || "—"}
                </dd>

                <dt className="text-slate-500">Country</dt>
                <dd className="font-medium text-slate-900">{verification.data?.country || "—"}</dd>

                <dt className="text-slate-500">Currency</dt>
                <dd className="font-medium text-slate-900">{verification.data?.currency || "—"}</dd>
              </dl>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AccountNumberInput;
