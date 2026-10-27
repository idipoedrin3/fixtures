"use client";

import {useRef, useState} from "react";
import {Icon} from "@iconify/react";
import {LOANS_API} from "#/_api/loans.helpers";
import type {
  ILoanCreateData,
  ILoanSchedulePreviewResponse,
} from "#/_types/loans.types";
import {formatCurrency, formatDate, showErrorToast} from "#/_lib/utils";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";

function formatScheduleAmount(amount: string) {
  return formatCurrency(amount, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function LoanSchedulePreviewDialog({
  data,
  onClose,
}: {
  data: ILoanCreateData;
  onClose: () => void;
}) {
  const [failed, setFailed] = useState(false);
  const [count, setCount] = useState(0);
  const [firstPayment, setFirstPayment] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const downloadLock = useRef(false);
  const [summary, setSummary] = useState<Pick<
    ILoanSchedulePreviewResponse,
    "currency" | "totals"
  > | null>(null);

  const frequency = data.repayment_structure === "single"
    ? "Single Repayment"
    : ({
        daily: "Daily",
        weekly: "Weekly",
        biweekly: "Every Two Weeks",
        monthly: "Monthly",
        quarterly: "Quarterly",
        semiannually: "Every Six Months",
        annually: "Annually",
      }[data.repayment_frequency || ""] || "Periodic");

  function amount(value: string | null) {
    return summary && value !== null
      ? `${summary.currency} ${formatScheduleAmount(value)}`
      : "—";
  }

  async function downloadSchedule() {
    if (downloadLock.current) return;
    downloadLock.current = true;
    setDownloading(true);
    try {
      const file = await LOANS_API.downloadSchedule(data);
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = "loan-repayment-schedule.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      showErrorToast({error, defaultMessage: "Unable to download repayment schedule"});
    } finally {
      downloadLock.current = false;
      setDownloading(false);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="flex h-[94vh] max-h-[94vh] w-[90vw] max-w-[90vw] flex-col overflow-hidden">
        <DialogHeader className="shrink-0 text-left">
          <div className="flex items-start gap-4 pr-10">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-primary/15 bg-primary/10 text-primary">
              <Icon icon="hugeicons:calendar-03" className="size-6" />
            </span>
            <div className="space-y-1">
              <DialogTitle className="text-2xl">Repayment Schedule</DialogTitle>
              <DialogDescription className="flex flex-wrap gap-x-3 gap-y-1">
                <span>{data.reference_code ? `Loan No. ${data.reference_code}` : "New Loan"}</span>
                <span aria-hidden>·</span>
                <span>{frequency}</span>
                <span aria-hidden>·</span>
                <span>Preview</span>
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <div className="grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            {
              label: "Principal",
              value: summary?.totals.principal ?? null,
              icon: "hugeicons:coins-01",
              tone: "border-border bg-muted/20",
            },
            {
              label: "Total Interest",
              value: summary?.totals.interest ?? null,
              icon: "hugeicons:percent",
              tone: "border-border bg-muted/20",
            },
            {
              label: "Total Repayment",
              value: summary?.totals.payment ?? null,
              icon: "hugeicons:wallet-01",
              tone: "border-primary/20 bg-primary/5",
            },
            {
              label: "First Installment",
              value: firstPayment,
              icon: "hugeicons:calendar-03",
              tone: "border-emerald-500/20 bg-emerald-500/5",
            },
          ].map((card) => (
            <div key={card.label} className={`flex min-w-0 items-start gap-3 rounded-xl border p-4 ${card.tone}`}>
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-background/80 text-primary">
                <Icon icon={card.icon} className="size-5" />
              </span>
              <div className="min-w-0">
                <p className="text-sm text-muted-foreground">{card.label}</p>
                <p className="mt-1 break-words text-lg font-semibold tabular-nums">
                  {amount(card.value)}
                </p>
              </div>
            </div>
          ))}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Installment Breakdown</h2>
            <p className="text-sm text-muted-foreground">
              {summary ? `${count} installments · ${frequency}` : "Calculating installments..."}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={!summary || downloading}
            onClick={() => void downloadSchedule()}
          >
            <Icon icon="hugeicons:download-01" className="mr-2 size-4" />
            {downloading ? "Downloading..." : "Download Schedule"}
          </Button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col">
          <PaginatedTableWrapper
            paginationMode="infinite"
            className="flex-1 min-h-0 overflow-auto rounded-lg border border-primary/15"
            fetchFirstPage={async () => {
              const result = await LOANS_API.previewSchedule(data);
              setSummary({currency: result.currency, totals: result.totals});
              setCount(result.count);
              setFirstPayment(result.results[0]?.payment ?? null);
              setFailed(false);
              return result;
            }}
            fetchFromUrl={async (query) => {
              const result = await LOANS_API.previewScheduleFromUrl(query, data);
              setSummary({currency: result.currency, totals: result.totals});
              setFailed(false);
              return result;
            }}
            deps={[data]}
            onError={(error) => {
              setFailed(true);
              showErrorToast({
                error,
                defaultMessage: "Unable to preview repayment schedule",
              });
            }}
          >
            {({data: page, loading, refreshing, refresh}) =>
              loading || refreshing ? (
                <p role="status">Calculating repayment schedule...</p>
              ) : failed ? (
                <div role="alert" className="space-y-2">
                  <p>Unable to load the schedule. Review the loan details or retry.</p>
                  <Button type="button" variant="outline" onClick={() => void refresh()}>
                    Retry
                  </Button>
                </div>
              ) : (
                <Table containerClassName="shrink-0 overflow-visible" className="text-sm">
                  <TableHeader className="sticky top-0 z-10 bg-muted">
                    <TableRow>
                      <TableHead>Installment</TableHead>
                      <TableHead>Due Date</TableHead>
                      {[
                        "Opening Principal",
                        "Principal",
                        "Interest",
                        "Payment",
                        "Closing Principal",
                      ].map((label) => (
                        <TableHead key={label} className="text-right">
                          {label}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {page?.results.map((row) => (
                      <TableRow key={row.number} className="border-primary/10">
                        <TableCell>{row.number}</TableCell>
                        <TableCell className="whitespace-nowrap">
                          {formatDate(row.due_date)}
                        </TableCell>
                        {[
                          row.opening_principal,
                          row.principal,
                          row.interest,
                          row.payment,
                          row.closing_principal,
                        ].map((amount, index) => (
                          <TableCell
                            key={index}
                            className="whitespace-nowrap text-right tabular-nums"
                          >
                            {summary?.currency} {formatScheduleAmount(amount)}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )
            }
          </PaginatedTableWrapper>
        </div>
        <p className="flex shrink-0 items-center gap-2 border-t pt-3 text-xs text-muted-foreground">
          <Icon icon="hugeicons:information-circle" className="size-4 shrink-0" />
          Amounts shown in {summary?.currency || "the loan currency"}, rounded to two decimal places for display.
        </p>
      </DialogContent>
    </Dialog>
  );
}
