export type SalesLineDiscountType = "percentage" | "fixed";

export interface SalesLineDiscountLike {
  discount_type: SalesLineDiscountType;
  discount_value: string;
  position?: number;
  description?: string;
}

export interface SalesLineDiscountBreakdown {
  discount: SalesLineDiscountLike;
  amount: number;
}

export interface SalesLineDiscountResult {
  totalDiscount: number;
  discountedTotal: number;
  breakdown: SalesLineDiscountBreakdown[];
}

export const roundSalesDiscountAmount = (value: number) =>
  Math.round((value + Number.EPSILON) * 100) / 100;

export function convertSalesLineDiscounts<T extends SalesLineDiscountLike>(
  discounts: T[] | undefined,
  multiplier: number,
): T[] {
  return sortSalesLineDiscounts(discounts ?? []).map((discount) => ({
    ...discount,
    discount_value:
      discount.discount_type === "fixed"
        ? roundSalesDiscountAmount(Number(discount.discount_value) * multiplier).toFixed(2)
        : discount.discount_value,
  }));
}

export function sortSalesLineDiscounts<T extends SalesLineDiscountLike>(discounts: T[]): T[] {
  return [...discounts].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
}

export function calculateSalesLineDiscounts(
  discounts: SalesLineDiscountLike[] | undefined,
  lineTotal: number,
): SalesLineDiscountResult {
  const breakdown: SalesLineDiscountBreakdown[] = [];
  const originalTotal = roundSalesDiscountAmount(lineTotal);

  if (!discounts?.length) {
    return {totalDiscount: 0, discountedTotal: originalTotal, breakdown};
  }

  let remaining = originalTotal;
  let totalDiscount = 0;

  for (const discount of sortSalesLineDiscounts(discounts)) {
    const value = Number.parseFloat(discount.discount_value);
    const rawValue = Number.isFinite(value) ? roundSalesDiscountAmount(value) : 0;

    let amount = 0;

    if (discount.discount_type === "percentage") {
      amount = (remaining * Math.min(Math.max(rawValue, 0), 100)) / 100;
    } else {
      amount = Math.min(Math.max(rawValue, 0), remaining);
    }

    amount = Math.min(roundSalesDiscountAmount(amount), remaining);
    remaining = roundSalesDiscountAmount(Math.max(0, remaining - amount));
    totalDiscount = roundSalesDiscountAmount(totalDiscount + amount);

    breakdown.push({discount, amount});
  }

  return {totalDiscount, discountedTotal: Math.max(0, remaining), breakdown};
}

export function validateSalesLineDiscounts(
  discounts: SalesLineDiscountLike[] | undefined,
  lineTotal: number,
): Record<number, string> {
  const errors: Record<number, string> = {};

  if (!discounts?.length) return errors;

  let remaining = roundSalesDiscountAmount(lineTotal);

  sortSalesLineDiscounts(discounts).forEach((discount, index) => {
    const trimmed = (discount.discount_value ?? "").trim();

    if (!trimmed) {
      errors[index] = "Enter a discount value";
      return;
    }

    if (!/^\d+(\.\d+)?$/.test(trimmed)) {
      errors[index] = "Enter a valid number";
      return;
    }

    const value = Number.parseFloat(trimmed);

    if (!Number.isFinite(value)) {
      errors[index] = "Enter a valid number";
      return;
    }

    if (value < 0) {
      errors[index] = "Discount value cannot be negative";
      return;
    }

    if (discount.discount_type === "percentage") {
      if (value > 100) {
        errors[index] = "Percentage discount cannot exceed 100%";
        return;
      }

      remaining = calculateSalesLineDiscounts([discount], remaining).discountedTotal;

      return;
    }

    if (value > remaining) {
      errors[index] = "Fixed discount cannot be greater than the remaining line amount";
      return;
    }

    remaining = calculateSalesLineDiscounts([discount], remaining).discountedTotal;
  });

  return errors;
}
