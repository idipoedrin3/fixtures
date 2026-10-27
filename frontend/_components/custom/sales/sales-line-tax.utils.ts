import {IInvoiceLineItemTaxBreakdown} from "#/_types/api.types";

interface SalesLineTaxInput {
  quantity: number;
  line_total: string | number;
  line_item_tax_breakdowns?: IInvoiceLineItemTaxBreakdown[];
}

export function getSalesLineTaxPreview(line: SalesLineTaxInput) {
  const breakdowns = line.line_item_tax_breakdowns ?? [];
  const quantity = Number(line.quantity || 0);
  const lineTotal = Number(line.line_total || 0);
  const taxTotal = breakdowns.reduce(
    (total, breakdown) => total + Number(breakdown.tax_amount || 0),
    0,
  );
  const inclusiveTax = breakdowns.reduce(
    (total, breakdown) => total + (breakdown.is_inclusive ? Number(breakdown.tax_amount || 0) : 0),
    0,
  );
  const exclusiveTax = taxTotal - inclusiveTax;
  const divisor = quantity || 1;

  return {
    net_unit_price: ((lineTotal - inclusiveTax) / divisor).toString(),
    tax_unit_price: (taxTotal / divisor).toString(),
    display_unit_price: ((lineTotal + exclusiveTax) / divisor).toString(),
  };
}
