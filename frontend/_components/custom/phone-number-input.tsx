import type {ICountry} from "#/_types/types.utils";

import {useState, useEffect, useRef} from "react";
import {CountryCode, isValidPhoneNumber} from "libphonenumber-js";
import {toast} from "sonner";
import {CheckCircle2, Loader2} from "lucide-react";

import {countryAPI} from "#/_api/helpers";
import {
  ACCOUNT_VERIFICATION_API,
  IAccountVerificationResponse,
} from "#/_api/services/system.service";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import CountrySelect from "#/_components/custom/country-select";

interface PhoneNumberInputProps {
  label?: string;
  required?: boolean;
  value: string;
  country: ICountry | null;
  onChange: (data: {
    country: ICountry | null;
    countryCode: string;
    phoneNumber: string;
    isValid: boolean;
  }) => void;
  error?: string | null;
  defaultCountry?: ICountry | null;
  showOptional?: boolean;
  disabled?: boolean;
  enableMobileMoneyVerification?: boolean;
  onVerificationChange?: (verification: IAccountVerificationResponse | null) => void;
  loadCountriesOnMount?: boolean;
}

export function PhoneNumberInput({
  label = "Phone Number",
  required = false,
  value,
  country,
  onChange,
  error,
  defaultCountry = null,
  disabled = false,
  showOptional,
  enableMobileMoneyVerification = false,
  onVerificationChange,
  loadCountriesOnMount = true,
}: PhoneNumberInputProps) {
  const initialCountry = country || defaultCountry;
  const [countries, setCountries] = useState<ICountry[]>(initialCountry ? [initialCountry] : []);
  const [selectedCountry, setSelectedCountry] = useState<ICountry | null>(initialCountry);
  const [phoneNumber, setPhoneNumber] = useState<string>(value || "");
  const [phoneError, setPhoneError] = useState<string | null>(error || null);
  const [isPhoneValid, setIsPhoneValid] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verification, setVerification] = useState<IAccountVerificationResponse | null>(null);
  const [isLoadingCountries, setIsLoadingCountries] = useState(loadCountriesOnMount);
  const [nextCountriesUrl, setNextCountriesUrl] = useState<string | null>(null);
  const countryRequestId = useRef(0);
  const verifiedAccount = verification?.data;

  useEffect(() => {
    if (!loadCountriesOnMount) {
      setIsLoadingCountries(false);
      return;
    }

    setIsLoadingCountries(true);
    countryAPI
      .fetchPage()
      .then((data) => {
        if (data.results.length > 0) {
          setCountries(data.results);
          setNextCountriesUrl(data.next);

          // Default to Uganda if not set
          if (!selectedCountry) {
            const ug = data.results.find((c) => c.iso2 === "UG");

            if (ug) setSelectedCountry(ug);
          }
        } else {
          toast.error("Failed to load countries data");
        }
      })
      .catch((error) => {
        toast.error("Failed to load countries");
      })
      .finally(() => setIsLoadingCountries(false));
  }, [loadCountriesOnMount]);

  const handleCountrySearch = async (search: string) => {
    const requestId = ++countryRequestId.current;

    setIsLoadingCountries(true);
    try {
      const data = await countryAPI.fetchPage({search});

      if (requestId !== countryRequestId.current) return;

      setCountries(data.results);
      setNextCountriesUrl(data.next);
    } catch {
      if (requestId === countryRequestId.current) {
        toast.error("Failed to search countries");
      }
    } finally {
      if (requestId === countryRequestId.current) {
        setIsLoadingCountries(false);
      }
    }
  };

  const loadMoreCountries = async () => {
    if (!nextCountriesUrl || isLoadingCountries) return;

    setIsLoadingCountries(true);
    try {
      const data = await countryAPI.fetchPage({url: nextCountriesUrl});

      setCountries((current) => [...current, ...data.results]);
      setNextCountriesUrl(data.next);
    } catch {
      toast.error("Failed to load more countries");
    } finally {
      setIsLoadingCountries(false);
    }
  };

  useEffect(() => {
    setSelectedCountry(country || defaultCountry || null);
  }, [country, defaultCountry]);

  useEffect(() => {
    setPhoneNumber(value);
  }, [value]);

  const getCountryCode = (country = selectedCountry) => country?.phone_code || "";

  const clearVerification = () => {
    setVerification(null);
    onVerificationChange?.(null);
  };

  const handleCountryChange = (country: ICountry | null) => {
    setSelectedCountry(country);
    setPhoneError(null);
    setIsPhoneValid(false);
    setPhoneNumber("");
    clearVerification();
    onChange({
      country,
      countryCode: getCountryCode(country),
      phoneNumber: "",
      isValid: false,
    });
  };

  const handlePhoneChange = (value: string) => {
    clearVerification();

    // Remove all non-digit characters and any country code if present
    let sanitizedValue = value.replace(/\D/g, "");
    const countryCode = getCountryCode().replace(/\D/g, "");

    // If the input starts with the country code, remove it
    if (sanitizedValue.startsWith(countryCode)) {
      sanitizedValue = sanitizedValue.slice(countryCode.length);
    }

    setPhoneNumber(sanitizedValue);

    if (selectedCountry && sanitizedValue) {
      const code = selectedCountry.iso2 as CountryCode;
      const fullNumber = `${getCountryCode()}${sanitizedValue}`;

      try {
        const isValid = isValidPhoneNumber(fullNumber, code);

        setIsPhoneValid(isValid);
        setPhoneError(isValid ? null : "Invalid phone number for selected country");
        onChange({
          country: selectedCountry,
          countryCode: getCountryCode(),
          phoneNumber: sanitizedValue.startsWith(getCountryCode())
            ? sanitizedValue.slice(0, getCountryCode().length)
            : sanitizedValue,
          isValid: isValid,
        });
      } catch (error) {
        setIsPhoneValid(false);
        setPhoneError("Invalid phone number format");
        onChange({
          country: selectedCountry,
          countryCode: getCountryCode(),
          phoneNumber: sanitizedValue,
          isValid: false,
        });
      }
    } else {
      setIsPhoneValid(false);
      setPhoneError(null);
      onChange({
        country: selectedCountry,
        countryCode: getCountryCode(),
        phoneNumber: sanitizedValue,
        isValid: false,
      });
    }
  };

  const verifyMobileMoneyNumber = async () => {
    if (!selectedCountry || !phoneNumber || !isPhoneValid) return;

    setIsVerifying(true);

    try {
      const internationalNumber = `${getCountryCode()}${phoneNumber.replace(/^0+/, "")}`;

      const result = await ACCOUNT_VERIFICATION_API.verifyMobileMoney({
        account_number: internationalNumber,
        account_type: "mobile_money",
        country_code: selectedCountry.iso2,
      });

      setVerification(result);
      onVerificationChange?.(result);
    } catch {
      setVerification(null);
      onVerificationChange?.(null);
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="space-y-2">
      {label && (
        <Label
          htmlFor="phone-number-input"
          required={required}
          showOptional={showOptional ?? !required}
        >
          {label}
        </Label>
      )}
      <div className="grid w-full grid-cols-[max-content_minmax(0,1fr)] items-center gap-2">
        <div className="min-w-0">
          <CountrySelect
            countries={countries}
            selectedCountry={selectedCountry}
            onCountryChange={handleCountryChange}
            onSearchChange={handleCountrySearch}
            onLoadMore={loadMoreCountries}
            hasMore={Boolean(nextCountriesUrl)}
            isLoading={isLoadingCountries}
            disabled={disabled}
            compact={true}
          />
        </div>
        <Input
          id="phone-number-input"
          value={phoneNumber}
          onChange={(e) => handlePhoneChange(e.target.value)}
          placeholder="Enter phone number"
          required={required}
          type="tel"
          disabled={disabled}
          className="min-w-0 w-full rounded-xl"
        />
      </div>
      {phoneError && <span className="text-red-500 text-xs">{phoneError}</span>}

      {enableMobileMoneyVerification && (
        <div className="space-y-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full rounded-xl"
            disabled={disabled || isVerifying || !isPhoneValid}
            onClick={verifyMobileMoneyNumber}
          >
            {isVerifying && <Loader2 className="size-4 animate-spin" />}
            {isVerifying ? "Verifying..." : "Verify Mobile Money Number"}
          </Button>

          {verification && (
            <div
              className={`rounded-xl border border-green-200 bg-green-50 p-3 transition-opacity ${
                isVerifying ? "opacity-50" : "opacity-100"
              }`}
            >
              <div className="flex items-center gap-2 text-sm font-medium text-green-700">
                <CheckCircle2 className="size-4" />
                VERIFICATION DETAILS
              </div>

              <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 border-t border-green-200 pt-3 text-sm">
                <dt className="text-slate-500">Account name</dt>
                <dd className="min-w-0 break-words font-medium text-slate-900">
                  {verifiedAccount?.account_name || "—"}
                </dd>

                <dt className="text-slate-500">Phone number</dt>
                <dd className="min-w-0 break-words font-medium text-slate-900">
                  {verifiedAccount?.account_number || "—"}
                </dd>

                <dt className="text-slate-500">Country</dt>
                <dd className="font-medium text-slate-900">{verifiedAccount?.country || "—"}</dd>

                <dt className="text-slate-500">Currency</dt>
                <dd className="font-medium text-slate-900">{verifiedAccount?.currency || "—"}</dd>
              </dl>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default PhoneNumberInput;
