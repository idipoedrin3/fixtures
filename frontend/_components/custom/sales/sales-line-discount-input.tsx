"use client";

import {FormattedNumberInput} from "../../common/inputs/formatted-number-input";
import {formatCurrency} from "#/_lib/utils";

interface DiscountItemSummaryProps {
  itemName: string;
  currency?: string;
  unitPrice: string | number;
  quantity: number;
  unitOfMeasure?: string;
  originalTotal: number;
  totalDiscount: number;
  discountedTotal: number;
  taxInclusive?: boolean;
}

export function DiscountItemSummary({
  itemName,
  currency,
  unitPrice,
  quantity,
  unitOfMeasure,
  originalTotal,
  totalDiscount,
  discountedTotal,
  taxInclusive,
}: DiscountItemSummaryProps) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border bg-muted/30 px-3 py-2.5 sm:grid-cols-3">
      <div className="col-span-2 min-w-0 sm:col-span-1">
        <dt className="text-xs text-muted-foreground">Item</dt>
        <dd className="mt-1 break-words text-sm font-semibold">{itemName}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Unit price</dt>
        <dd className="mt-1 text-sm font-semibold tabular-nums">
          {currency} {formatCurrency(unitPrice)}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Quantity</dt>
        <dd className="mt-1 text-sm font-semibold tabular-nums">
          {formatCurrency(quantity)} {unitOfMeasure}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">
          Before discounts
          {taxInclusive !== undefined && ` (${taxInclusive ? "incl." : "excl."} tax)`}
        </dt>
        <dd className="mt-1 text-sm font-semibold tabular-nums">
          {currency} {formatCurrency(originalTotal)}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Total discounts</dt>
        <dd className="mt-1 text-sm font-semibold tabular-nums">
          {totalDiscount > 0 ? "− " : ""}
          {currency} {formatCurrency(totalDiscount)}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">
          After all discounts
          {taxInclusive !== undefined && ` (${taxInclusive ? "incl." : "excl."} tax)`}
        </dt>
        <dd className="mt-1 text-sm font-bold tabular-nums text-primary">
          {currency} {formatCurrency(discountedTotal)}
        </dd>
      </div>
    </dl>
  );
}

interface DiscountValueInputProps {
  value: string | number;
  discountType: "percentage" | "fixed";
  suffix?: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: string;
  placeholder?: string;
  max?: number;
  autoFocus?: boolean;
  ariaLabel?: string;
}

export function DiscountValueInput({
  value,
  discountType,
  suffix,
  onChange,
  disabled,
  error,
  placeholder,
  max,
  autoFocus,
  ariaLabel,
}: DiscountValueInputProps) {
  return (
    <div className="space-y-1">
      <div className="relative">
        <FormattedNumberInput
          aria-label={ariaLabel}
          autoFocus={autoFocus}
          value={value}
          onValueChange={(next) => onChange(next == null ? "" : String(next))}
          min={0}
          max={discountType === "percentage" ? 100 : max}
          disabled={disabled}
          placeholder={placeholder ?? (discountType === "percentage" ? "10" : "5,000")}
          aria-invalid={Boolean(error)}
          className={`text-right tabular-nums ${suffix ? "pr-8" : ""} ${
            error ? "border-destructive focus-visible:ring-destructive" : ""
          }`}
        />
        {suffix && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground"
          >
            {suffix}
          </span>
        )}
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

export default DiscountValueInput;
