"use client";

import type {ILoanScheduleRow} from "#/_types/loans.types";
import {formatCurrency, formatDate} from "#/_lib/utils";
import {EmptyState} from "#/_components/common/nodata";
import {Badge} from "#/_components/custom/badge";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";

const money = (value: number | string) =>
  formatCurrency(value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export function LoanInstallmentDetailDialog({
  row,
  currencyCode,
  onClose,
  onRecord,
}: {
  row: ILoanScheduleRow;
  currencyCode: string;
  onClose: () => void;
  onRecord?: () => void;
}) {
  const fields: [string, string | null, string?][] = [
    ["Due Date", formatDate(row.due_date), "text-red-600"],
    ["Opening Principal", `${currencyCode} ${money(row.opening_principal)}`],
    ["Principal Due", `${currencyCode} ${money(row.principal_due)}`],
    ["Interest Due", `${currencyCode} ${money(row.interest_due)}`, "text-orange-600"],
    ["Total Due", `${currencyCode} ${money(row.total_due)}`],
    ["Paid", `${currencyCode} ${money(row.total_paid)}`, "text-green-600"],
    ["Outstanding", `${currencyCode} ${money(row.outstanding)}`, "font-semibold"],
  ];

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="z-[70] flex h-[76vh] min-h-0 max-h-[76vh] w-[76vw] max-w-[76vw] flex-col gap-0 overflow-hidden p-0"
        onPointerDownOutside={(event) => event.preventDefault()}
      >
        <DialogHeader className="shrink-0 border-b px-6 py-4 text-left">
          <div className="flex items-center justify-between gap-4 pr-8">
            <div className="flex items-center gap-3">
              <DialogTitle className="text-2xl">Installment {row.installation_number}</DialogTitle>
              <Badge status={row.status ?? "pending"} />
            </div>
            {onRecord && <Button onClick={onRecord}>Record Payment</Button>}
          </div>
          <DialogDescription>
            Amounts due and the payments made against this installment.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-4">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {fields.map(([label, value, tone]) => (
              <div key={label}>
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className={`mt-1 break-words font-medium ${tone ?? ""}`}>{value || "—"}</dd>
              </div>
            ))}
          </dl>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">Payments</h2>
            <div className="w-full max-w-full overflow-x-auto bg-white shadow-sm">
              <Table className="w-full border-collapse">
                <TableHeader className="bg-gray-800">
                  <TableRow className="border-none">
                    <TableHead className="!text-white">Reference</TableHead>
                    <TableHead className="!text-white">Date</TableHead>
                    <TableHead className="!text-white">Status</TableHead>
                    {["Principal", "Interest", "Amount"].map((label) => (
                      <TableHead key={label} className="!text-white text-right">
                        {label}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {row.payments.length === 0 ? (
                    <TableRow className="border-none hover:bg-transparent">
                      <TableCell colSpan={6}>
                        <EmptyState />
                      </TableCell>
                    </TableRow>
                  ) : (
                    row.payments.map((payment) => (
                      <TableRow key={payment.base_uuid}>
                        <TableCell className="font-medium">
                          {payment.reference_code || "—"}
                        </TableCell>
                        <TableCell className="whitespace-nowrap">
                          {formatDate(payment.date)}
                        </TableCell>
                        <TableCell>
                          <Badge status={payment.status} />
                        </TableCell>
                        {[payment.principal_amount, payment.interest_amount, payment.amount].map(
                          (value, index) => (
                            <TableCell
                              key={index}
                              className={`whitespace-nowrap text-right tabular-nums ${
                                index === 2 ? "font-semibold text-green-600" : ""
                              }`}
                            >
                              {money(value)}
                            </TableCell>
                          ),
                        )}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
