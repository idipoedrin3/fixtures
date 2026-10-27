import {formatCurrency} from "#/_lib/utils";
import {TableCell, TableRow} from "@/components/ui/table";

interface SalesDocumentTotalRowsProps {
  currency: string;
  netTotal: string | number;
  taxTotal: string | number;
  grossTotal: string | number;
  totalDiscount?: string | number;
  labelColSpan: number;
}

export function SalesDocumentTotalRows({
  currency,
  netTotal,
  taxTotal,
  grossTotal,
  totalDiscount,
  labelColSpan,
}: SalesDocumentTotalRowsProps) {
  return (
    <>
      <TableRow className="bg-muted/40">
        <TableCell className="px-4 py-3 text-right" colSpan={labelColSpan}>
          Subtotal
        </TableCell>
        <TableCell className="px-4 py-3 text-right tabular-nums">
          {currency} {formatCurrency(netTotal)}
        </TableCell>
      </TableRow>

      {totalDiscount && Number(totalDiscount) > 0 && (
        <TableRow className="bg-muted/40">
          <TableCell className="px-4 py-3 text-right" colSpan={labelColSpan}>
            Total Discount
          </TableCell>
          <TableCell className="px-4 py-3 text-right tabular-nums text-destructive">
            -{currency} {formatCurrency(totalDiscount)}
          </TableCell>
        </TableRow>
      )}

      {Number(taxTotal || 0) > 0 && (
        <TableRow className="bg-muted/40">
          <TableCell className="px-4 py-3 text-right" colSpan={labelColSpan}>
            Tax
          </TableCell>
          <TableCell className="px-4 py-3 text-right tabular-nums">
            {currency} {formatCurrency(taxTotal)}
          </TableCell>
        </TableRow>
      )}

      <TableRow className="bg-gray-100 font-semibold">
        <TableCell className="px-4 py-3 text-right" colSpan={labelColSpan}>
          Total
        </TableCell>
        <TableCell className="px-4 py-3 text-right tabular-nums">
          {currency} {formatCurrency(grossTotal)}
        </TableCell>
      </TableRow>
    </>
  );
}
