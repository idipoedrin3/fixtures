"use client";

import {Icon} from "@iconify/react";
import {useCallback, useEffect, useMemo, useState} from "react";

import type {ICustomerPaymentRecord} from "#/_types/api.types";
import {CUSTOMER_PAYMENTS_API} from "#/_api/api.helpers";
import {formatCurrency, formatDate} from "#/_lib/utils";
import {useToast} from "#/_hooks/use-toast";

import {Badge} from "#/_components/custom/badge";
import {Button} from "@/components/ui/button";
import {Checkbox} from "@/components/ui/checkbox";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";

type AvailablePrepaymentsPanelProps = {
  customerUuid?: string;
  invoiceUuid: string;
  outstandingBalance: number | string;
  currencyCode?: string;
  onApplied?: () => void | Promise<void>;
  onAvailabilityChange?: (hasAvailablePrepayments: boolean) => void;
};

export function AvailablePrepaymentsPanel({
  customerUuid,
  invoiceUuid,
  outstandingBalance,
  currencyCode,
  onApplied,
  onAvailabilityChange,
}: AvailablePrepaymentsPanelProps) {
  const {toast} = useToast();

  const [prepayments, setPrepayments] = useState<ICustomerPaymentRecord[]>([]);

  const [selectedPrepayments, setSelectedPrepayments] = useState<Set<string>>(() => new Set());

  const [isLoading, setIsLoading] = useState(true);
  const [isApplying, setIsApplying] = useState(false);

  const amountDue = Number(outstandingBalance || 0);
  const formatInvoiceAmount = (amount: number | string) =>
    `${currencyCode ? `${currencyCode} ` : ""}${formatCurrency(amount)}`;

  const fetchPrepayments = useCallback(async () => {
    if (!customerUuid || amountDue <= 0) {
      setPrepayments([]);
      setSelectedPrepayments(new Set());

      onAvailabilityChange?.(false);

      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    try {
      const response = await CUSTOMER_PAYMENTS_API.fetchCustomerPayments({
        customer_base_uuid: customerUuid,
        payment_type: "prepayment",
        payment_status: "APPROVED",
      });

      const available = (response.results ?? []).filter(
        (payment) => Number(payment.remaining_balance || 0) > 0,
      );

      setPrepayments(available);

      // Tell the parent whether the side panel should
      // receive its own grid column.
      onAvailabilityChange?.(available.length > 0);

      // Keep only selections that still exist after refresh.
      setSelectedPrepayments((current) => {
        const availableIds = new Set(available.map((payment) => payment.base_uuid));

        return new Set([...current].filter((id) => availableIds.has(id)));
      });
    } catch (error) {
      console.error(error);

      setPrepayments([]);
      setSelectedPrepayments(new Set());

      onAvailabilityChange?.(false);

      toast({
        title: "Error",
        description: "Failed to load available prepayments",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [customerUuid, amountDue, onAvailabilityChange, toast]);

  useEffect(() => {
    void fetchPrepayments();
  }, [fetchPrepayments]);

  const selectedTotal = useMemo(() => {
    return prepayments.reduce((total, prepayment) => {
      if (!selectedPrepayments.has(prepayment.base_uuid)) {
        return total;
      }

      return total + Number(prepayment.remaining_balance || 0);
    }, 0);
  }, [prepayments, selectedPrepayments]);

  const remainingToCover = Math.max(amountDue - selectedTotal, 0);

  const isFullyCovered = amountDue > 0 && selectedTotal >= amountDue;

  const applicablePrepaymentIds = useMemo(() => {
    const ids: string[] = [];
    let total = 0;

    for (const prepayment of prepayments) {
      if (total >= amountDue) break;

      ids.push(prepayment.base_uuid);
      total += Number(prepayment.remaining_balance || 0);
    }

    return ids;
  }, [prepayments, amountDue]);

  const areAllApplicableSelected =
    applicablePrepaymentIds.length > 0 &&
    applicablePrepaymentIds.every((id) => selectedPrepayments.has(id));

  const toggleAllPrepayments = () => {
    setSelectedPrepayments(
      areAllApplicableSelected ? new Set() : new Set(applicablePrepaymentIds),
    );
  };

  const togglePrepayment = useCallback(
    (prepayment: ICustomerPaymentRecord) => {
      setSelectedPrepayments((current) => {
        const next = new Set(current);
        const id = prepayment.base_uuid;

        // Always allow deselecting.
        if (next.has(id)) {
          next.delete(id);
          return next;
        }

        // Calculate the selected amount from the
        // current state, not from potentially stale render state.
        const currentSelectedTotal = prepayments.reduce((total, item) => {
          if (!current.has(item.base_uuid)) {
            return total;
          }

          return total + Number(item.remaining_balance || 0);
        }, 0);

        // Once the invoice is covered, no more
        // prepayments may be selected.
        if (currentSelectedTotal >= amountDue) {
          return current;
        }

        next.add(id);

        return next;
      });
    },
    [prepayments, amountDue],
  );

  const handleApply = async () => {
    if (selectedPrepayments.size === 0 || amountDue <= 0 || isApplying) {
      return;
    }

    const appliedPrepaymentIds = new Set(selectedPrepayments);

    setIsApplying(true);

    try {
      await CUSTOMER_PAYMENTS_API.reconcilePrepayments({
        prepayment_uuids: Array.from(appliedPrepaymentIds),
        invoice_uuids: [invoiceUuid],
      });

      toast({
        title: "Success",
        description: "Prepayments applied successfully",
      });

      setSelectedPrepayments(new Set());
      setPrepayments((current) => {
        const remaining =
          selectedTotal >= amountDue
            ? []
            : current.filter((payment) => !appliedPrepaymentIds.has(payment.base_uuid));

        onAvailabilityChange?.(remaining.length > 0);

        return remaining;
      });

      await onApplied?.();
    } catch (error) {
      console.error(error);

      toast({
        title: "Error",
        description: "Failed to apply prepayments",
        variant: "destructive",
      });
    } finally {
      setIsApplying(false);
    }
  };

  /*
   * Fully paid invoice:
   * no panel should be rendered and the parent
   * should already have been notified with false.
   */
  if (amountDue <= 0) {
    return null;
  }

  /*
   * During the initial fetch, render the panel
   * skeleton. The parent may temporarily use its
   * previous availability state until fetch ends.
   */
  if (isLoading) {
    return (
      <aside className="min-w-0">
        <div className="overflow-hidden rounded-xl border bg-card">
          <div className="border-b px-4 py-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-foreground">Available Prepayments</h3>

              <Icon
                icon="hugeicons:loading-03"
                className="size-4 animate-spin text-muted-foreground"
              />
            </div>

            <p className="mt-0.5 text-xs text-muted-foreground">
              Checking available customer prepayments...
            </p>
          </div>

          <div className="space-y-2 p-4">
            {Array.from({length: 3}).map((_, index) => (
              <div key={index} className="h-11 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        </div>
      </aside>
    );
  }

  /*
   * Important:
   * once loading has finished and there are no
   * prepayments, render nothing.
   *
   * The parent has already received:
   * onAvailabilityChange(false)
   *
   * so the Tabs can expand to full width.
   */
  if (prepayments.length === 0) {
    return null;
  }

  return (
    <aside className="min-w-0">
      <div className="overflow-hidden rounded-xl border bg-card">
        {/* Header */}
        <div className="border-b px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-foreground">Available Prepayments</h3>

                <Badge className="shrink-0">{prepayments.length}</Badge>
              </div>

              <p className="mt-0.5 text-xs text-muted-foreground">
                Apply customer prepayments to this invoice.
              </p>
            </div>

            <Button
              type="button"
              size="sm"
              className="shrink-0"
              disabled={selectedPrepayments.size === 0 || isApplying}
              onClick={handleApply}
            >
              {isApplying ? (
                <>
                  <span className="mr-2 size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Applying...
                </>
              ) : (
                <>
                  <Icon icon="hugeicons:link-01" className="mr-2 size-4" />
                  Apply
                  {selectedPrepayments.size > 0 ? ` (${selectedPrepayments.size})` : ""}
                </>
              )}
            </Button>
          </div>

          {selectedPrepayments.size > 0 && (
            <div className="mt-3 grid w-full grid-cols-3 divide-x overflow-hidden rounded-lg border bg-muted/30">
            <div className="min-w-0 px-2 py-2 text-center">
              <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                Outstanding
              </span>
              <span className="mt-0.5 block truncate text-xs font-semibold text-foreground">
                {formatInvoiceAmount(amountDue)}
              </span>
            </div>

            <div className="min-w-0 px-2 py-2 text-center">
              <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                Selected
              </span>
              <span className="mt-0.5 block truncate text-xs font-semibold text-foreground">
                {formatInvoiceAmount(selectedTotal)}
              </span>
            </div>

            <div className="min-w-0 px-2 py-2 text-center">
              <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                Remaining
              </span>
              <span
                className={`mt-0.5 block truncate text-xs font-semibold ${
                  isFullyCovered ? "text-emerald-600" : "text-foreground"
                }`}
              >
                {formatInvoiceAmount(remainingToCover)}
              </span>
            </div>
            </div>
          )}
        </div>

        <div className="max-h-[280px] overflow-y-auto">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-background">
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={areAllApplicableSelected}
                    onCheckedChange={toggleAllPrepayments}
                    aria-label={
                      areAllApplicableSelected
                        ? "Deselect all prepayments"
                        : "Select available prepayments"
                    }
                  />
                </TableHead>

                <TableHead>Prepayment</TableHead>

                <TableHead className="text-right">Available</TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              {prepayments.map((prepayment) => {
                const selected = selectedPrepayments.has(prepayment.base_uuid);

                const disabled = !selected && isFullyCovered;

                return (
                  <TableRow
                    key={prepayment.base_uuid}
                    className={
                      selected
                        ? "cursor-pointer bg-primary/5"
                        : disabled
                          ? "cursor-not-allowed opacity-50"
                          : "cursor-pointer"
                    }
                    onClick={() => {
                      if (disabled) return;

                      togglePrepayment(prepayment);
                    }}
                  >
                    <TableCell onClick={(event) => event.stopPropagation()}>
                      <Checkbox
                        checked={selected}
                        disabled={disabled}
                        onCheckedChange={() => {
                          if (disabled) {
                            return;
                          }

                          togglePrepayment(prepayment);
                        }}
                        aria-label={`Select ${prepayment.reference_code || "prepayment"}`}
                      />
                    </TableCell>

                    <TableCell>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {prepayment.reference_code || "Prepayment"}
                        </p>

                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {formatDate(prepayment.payment_date)}
                        </p>
                      </div>
                    </TableCell>

                    <TableCell className="text-right font-semibold text-green-600">
                      {formatInvoiceAmount(prepayment.remaining_balance)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>
    </aside>
  );
}
