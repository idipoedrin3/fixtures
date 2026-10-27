"use client";

import {useEffect, useRef, useState} from "react";
import {CURRENCY_CONVERSION_API, IExchangeRateInput} from "#/_api/services/system.service";
import {Currency} from "#/_types/api.types";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import {Label} from "@/components/ui/label";
import SwitchSetting from "#/_components/common/inputs/switch-setting";
import {formatCurrency} from "#/_lib/utils";

type ExchangeRateCurrency = Pick<Currency, "id" | "code" | "name" | "symbol">;

const normalizeExchangeRateValue = (value: string) => {
  const [integerPart, fractionalPart] = value.split(".");

  if (!fractionalPart || fractionalPart.length <= 20) return value;

  return `${integerPart}.${fractionalPart.slice(0, 20)}`;
};

const getConversionErrorMessage = (error: any) => {
  const data = error?.response?.data;

  if (typeof data?.detail === "string") return data.detail;
  if (typeof data?.message === "string") return data.message;

  if (data && typeof data === "object") {
    const firstError = Object.values(data)
      .flat()
      .find((item) => typeof item === "string");
    if (typeof firstError === "string") return firstError;
  }

  return "No configured exchange rate was found.";
};

interface Props {
  baseCurrency: ExchangeRateCurrency;
  transactionCurrency: ExchangeRateCurrency;
  value?: IExchangeRateInput;
  onChange: (value: IExchangeRateInput | undefined) => void;
  conversionAmount?: string | number;
  onConvertedAmount?: (amount: string) => void;
}

export default function ExchangeRateInput({
  baseCurrency,
  transactionCurrency,
  value,
  onChange,
  conversionAmount,
  onConvertedAmount,
}: Props) {
  const isBaseCurrency = baseCurrency.id === transactionCurrency.id;
  const [useCustomRate, setUseCustomRate] = useState(!!value);
  const [requiresCustomRate, setRequiresCustomRate] = useState(false);
  const [transactionValue, setTransactionValue] = useState(value?.one_side.value ?? "1");
  const [baseValue, setBaseValue] = useState(value?.other_side.value ?? "");
  const [preview, setPreview] = useState<string>();
  const [previewError, setPreviewError] = useState<string>();
  const [configuredRateError, setConfiguredRateError] = useState<string>();
  const [customRateTouched, setCustomRateTouched] = useState(false);
  const callbacks = useRef({onChange, onConvertedAmount});

  useEffect(() => {
    callbacks.current = {onChange, onConvertedAmount};
  }, [onChange, onConvertedAmount]);

  const emitCustomRate = (nextTransactionValue: string, nextBaseValue: string) => {
    const normalizedTransactionValue = normalizeExchangeRateValue(nextTransactionValue);
    const normalizedBaseValue = normalizeExchangeRateValue(nextBaseValue);

    if (Number(normalizedTransactionValue) <= 0 || Number(normalizedBaseValue) <= 0) {
      onChange(undefined);
      return;
    }

    onChange({
      one_side: {
        currency: transactionCurrency.id,
        value: normalizedTransactionValue,
      },
      other_side: {
        currency: baseCurrency.id,
        value: normalizedBaseValue,
      },
    });
  };

  useEffect(() => {
    if (isBaseCurrency) {
      setUseCustomRate(false);
      setTransactionValue("1");
      setBaseValue("1");
      setPreview(`1 ${baseCurrency.code} = 1 ${transactionCurrency.code}`);
      setPreviewError(undefined);
      setConfiguredRateError(undefined);
      setCustomRateTouched(false);
      return;
    }

    const transactionAmount = Number(transactionValue);
    const baseAmount = Number(baseValue);

    if (useCustomRate && (transactionAmount <= 0 || baseAmount <= 0)) {
      setPreview(undefined);
      setPreviewError(
        customRateTouched ? "Both exchange-rate values must be greater than zero." : undefined,
      );
      return;
    }

    const exchangeRate: IExchangeRateInput | undefined = useCustomRate
      ? {
          one_side: {
            currency: transactionCurrency.id,
            value: normalizeExchangeRateValue(transactionValue),
          },
          other_side: {
            currency: baseCurrency.id,
            value: normalizeExchangeRateValue(baseValue),
          },
        }
      : undefined;

    setPreviewError(undefined);

    let cancelled = false;

    const previewConversion = async () => {
      try {
        const requestedAmount = Number(conversionAmount);
        const amountToConvert =
          Number.isFinite(requestedAmount) && requestedAmount > 0
            ? conversionAmount!
            : useCustomRate && transactionAmount > 0
              ? transactionValue
              : "1";

        const result = await CURRENCY_CONVERSION_API.post({
          amount: amountToConvert,
          currency: transactionCurrency.id.toString(),
          target_currency: baseCurrency.id.toString(),
          ...(exchangeRate ? {exchange_rate: exchangeRate} : {}),
        });

        if (!cancelled) {
          setRequiresCustomRate(false);
          setConfiguredRateError(undefined);

          if (!useCustomRate) {
            setTransactionValue(normalizeExchangeRateValue(result.exchange_rate.one_side.value));
            setBaseValue(normalizeExchangeRateValue(result.exchange_rate.other_side.value));
          }

          setPreview(
            `${result.original_amount} ${result.from_currency} = ${
              result.converted_amount
            } ${result.to_currency}`,
          );
          callbacks.current.onConvertedAmount?.(result.converted_amount);
        }
      } catch (error: any) {
        if (!cancelled) {
          setPreview(undefined);
          if (!useCustomRate) {
            setRequiresCustomRate(true);
            setUseCustomRate(true);
            setBaseValue("");
            setCustomRateTouched(false);
            callbacks.current.onChange(undefined);
            setConfiguredRateError(getConversionErrorMessage(error));
            setPreviewError(undefined);
          } else {
            setPreviewError("Enter a valid exchange rate for these currencies.");
          }
        }
      }
    };

    const timeout = window.setTimeout(() => {
      void previewConversion();
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [
    baseCurrency.id,
    baseCurrency.code,
    transactionCurrency.id,
    transactionCurrency.code,
    transactionValue,
    baseValue,
    useCustomRate,
    isBaseCurrency,
    conversionAmount,
    customRateTouched,
  ]);

  if (isBaseCurrency) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-xl border bg-card p-3">
      <SwitchSetting
        id={`custom-exchange-rate-${transactionCurrency.id}-${baseCurrency.id}`}
        label="Custom Exchange Rate"
        className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"
        description={
          requiresCustomRate
            ? `${configuredRateError ?? "A configured rate is unavailable."} Enter a rate below.`
            : undefined
        }
        checked={useCustomRate}
        disabled={requiresCustomRate}
        onCheckedChange={(checked) => {
          setUseCustomRate(checked);
          setCustomRateTouched(false);
          if (checked) {
            emitCustomRate(transactionValue, baseValue);
          } else {
            onChange(undefined);
          }
        }}
      />

      {!useCustomRate && preview && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/50 px-3 py-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Configured rate:
          </span>
          <span className="text-sm font-semibold">
            {formatCurrency(transactionValue)} {transactionCurrency.code}
            <span className="mx-1.5 text-muted-foreground">=</span>
            {formatCurrency(baseValue)} {baseCurrency.code}
          </span>
        </div>
      )}

      {useCustomRate && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label className="text-xs">{transactionCurrency.code} amount</Label>
            <FormattedNumberInput
              min={0}
              value={Number(transactionValue)}
              onValueChange={(amount) => {
                const nextValue = (amount ?? 0).toString();
                setCustomRateTouched(true);
                setTransactionValue(nextValue);
                emitCustomRate(nextValue, baseValue);
              }}
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">{baseCurrency.code} equivalent</Label>
            <FormattedNumberInput
              min={0}
              value={baseValue ? Number(baseValue) : ""}
              onValueChange={(amount) => {
                const nextValue = amount === null ? "" : amount.toString();
                setCustomRateTouched(true);
                setBaseValue(nextValue);
                emitCustomRate(transactionValue, nextValue);
              }}
            />
          </div>
        </div>
      )}

      {useCustomRate && preview && (
        <p className="text-xs text-muted-foreground">Conversion preview: {preview}</p>
      )}

      {previewError && <p className="text-xs text-destructive">{previewError}</p>}
    </div>
  );
}
