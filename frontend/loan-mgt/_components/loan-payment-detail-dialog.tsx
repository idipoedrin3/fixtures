"use client";

import type {ILoanRepayment} from "#/_types/loans.types";
import {formatCurrency, formatDate} from "#/_lib/utils";
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

const displayChoice = (value: string | null | undefined) =>
  value ? value.replaceAll("_", " ").replace(/\b[a-z]/g, (letter) => letter.toUpperCase()) : "—";

export function LoanPaymentDetailDialog({
  payment,
  currencyCode,
  onClose,
  onEdit,
}: {
  payment: ILoanRepayment;
  currencyCode: string;
  onClose: () => void;
  onEdit?: () => void;
}) {
  const fields: [string, string | null | undefined][] = [
    ["Reference", payment.reference_code],
    ["Payment Date", formatDate(payment.date)],
    ["Amount", `${currencyCode} ${money(payment.amount)}`],
    ["Accounting Treatment", displayChoice(payment.accounting_treatment)],
    ["Supporting Reference", payment.accounting_reference],
    ["Recorded On", formatDate(payment.created_at)],
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
              <DialogTitle className="text-2xl">Repayment Details</DialogTitle>
              <Badge status={payment.status} />
            </div>
            {onEdit && (
              <Button variant="outline" onClick={onEdit}>
                Edit
              </Button>
            )}
          </div>
          <DialogDescription>{payment.reference_code ?? "Loan repayment"}</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-4">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {fields.map(([label, value]) => (
              <div key={label}>
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="mt-1 break-words font-medium">{value || "—"}</dd>
              </div>
            ))}
          </dl>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">Installments Paid</h2>
            <div className="w-full max-w-full overflow-x-auto bg-white shadow-sm">
              <Table className="w-full border-collapse">
                <TableHeader className="bg-gray-800">
                  <TableRow className="border-none">
                    <TableHead className="!text-white">Installment</TableHead>
                    <TableHead className="!text-white">Due Date</TableHead>
                    {["Principal", "Interest", "Fees", "Total"].map((label) => (
                      <TableHead key={label} className="!text-white text-right">
                        {label}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payment.allocations.map((allocation) => (
                    <TableRow key={allocation.repayment_schedule}>
                      <TableCell className="font-medium">
                        {allocation.installation_number}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {allocation.due_date ? formatDate(allocation.due_date) : "—"}
                      </TableCell>
                      {[
                        allocation.principal_amount,
                        allocation.interest_amount,
                        allocation.fee_amount,
                        allocation.amount,
                      ].map((value, index) => (
                        <TableCell
                          key={index}
                          className={`whitespace-nowrap text-right tabular-nums ${
                            index === 3 ? "font-semibold" : ""
                          }`}
                        >
                          {money(value)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                  <TableRow className="bg-gray-100 font-semibold">
                    <TableCell colSpan={5} className="text-right">
                      Total Paid
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-right tabular-nums text-green-600">
                      {currencyCode} {money(payment.amount)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
