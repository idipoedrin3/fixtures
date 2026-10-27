"use client";

import {Icon} from "@iconify/react";
import {useState} from "react";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {Button} from "@/components/ui/button";
import {ITransactionEntry} from "#/_types/api.types";
import {EmptyState} from "../nodata";
import {ResponsiveAmountDisplay} from "../responsive-amount-display";
import {TruncatedText} from "../truncated-text";
import {cn} from "@/lib/utils";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {formatCurrency, formatDateTime} from "#/_lib/utils";
import {formatNumbersInText} from "#/(dashboard)/reconciliations/_components/match-column";
import {
  ReportFilterPanel,
  EMPTY_REPORT_FILTERS,
  ReportFilterState,
} from "#/(dashboard)/reports/_components/filter-panel";

interface TransactionsTableProps {
  entries: ITransactionEntry[];
  compact?: boolean;
  useParentScroll?: boolean;
  stickyHeader?: boolean;
  loading?: boolean;
  showDebitCreditColumns?: boolean;
  showReportFilters?: boolean;
  showAccountColumn?: boolean;
  showJournalReferenceColumn?: boolean;
  onFilterChange?: (filters: ReportFilterState) => void | Promise<void>;
}

export default function GeneralTransactionEntriesTable({
  entries,
  compact = false,
  useParentScroll = false,
  stickyHeader = false,
  loading = false,
  showDebitCreditColumns = false,
  showReportFilters = false,
  showAccountColumn = true,
  showJournalReferenceColumn = false,
  onFilterChange,
}: TransactionsTableProps) {
  const router = useRouter();
  const [filters, setFilters] = useState<ReportFilterState>(EMPTY_REPORT_FILTERS);
  const [areReportFiltersOpen, setAreReportFiltersOpen] = useState(false);

  const seeAccountDetails = (base_uuid: string) => {
    router.push(`/accounts/${base_uuid}`);
  };

  const compactAmount = (
    value: string | number,
    currency?: string,
    baseValue?: string | number,
    baseCurrency?: string,
  ) => (
    <div className="w-24 max-w-full">
      <ResponsiveAmountDisplay value={value} currency={currency} />
      {baseValue !== undefined && (
        <div className="w-full text-muted-foreground">
          <ResponsiveAmountDisplay value={baseValue} currency={baseCurrency} />
        </div>
      )}
    </div>
  );

  const formatEntryAmount = (entry: ITransactionEntry) => {
    const transactionCurrency = entry.transaction_currency?.code;
    const baseCurrency = entry.base_currency?.code ?? entry.transaction?.base_currency?.code;
    const foreignAmount = entry.entry_amount_in_foreign_currency;
    const isForeign =
      !!transactionCurrency &&
      !!baseCurrency &&
      transactionCurrency !== baseCurrency &&
      foreignAmount !== null &&
      foreignAmount !== undefined;

    if (compact) {
      return isForeign
        ? compactAmount(foreignAmount, transactionCurrency, entry.entry_amount, baseCurrency)
        : compactAmount(entry.entry_amount, baseCurrency);
    }

    if (!isForeign) {
      return (
        <>
          {baseCurrency ? `${baseCurrency} ` : ""}
          {formatCurrency(entry.entry_amount)}
        </>
      );
    }

    return (
      <>
        {transactionCurrency} {formatCurrency(foreignAmount)}
        <span className="ml-1 text-xs text-muted-foreground">
          ({baseCurrency} {formatCurrency(entry.entry_amount)})
        </span>
      </>
    );
  };

  const formatEntryBalance = (
    entry: ITransactionEntry,
    baseBalance: string,
    foreignBalance?: string | null,
  ) => {
    const transactionCurrency = entry.transaction_currency?.code;
    const accountCurrency = entry.account?.currency?.code;
    const foreignCurrency = accountCurrency ?? transactionCurrency;
    const baseCurrency = entry.base_currency?.code ?? entry.transaction?.base_currency?.code;

    if (
      foreignBalance !== null &&
      foreignBalance !== undefined &&
      foreignCurrency &&
      baseCurrency &&
      foreignCurrency !== baseCurrency
    ) {
      if (compact) {
        return compactAmount(foreignBalance, foreignCurrency, baseBalance, baseCurrency);
      }

      return (
        <>
          {foreignCurrency} {formatCurrency(foreignBalance)}
          <span className="ml-1 text-xs text-muted-foreground">
            ({baseCurrency} {formatCurrency(baseBalance)})
          </span>
        </>
      );
    }

    if (compact) {
      return compactAmount(baseBalance, baseCurrency);
    }

    return (
      <>
        {baseCurrency ? `${baseCurrency} ` : ""}
        {formatCurrency(baseBalance)}
      </>
    );
  };

  const handleReset = () => {
    setFilters(EMPTY_REPORT_FILTERS);
    void onFilterChange?.(EMPTY_REPORT_FILTERS);
  };

  const handleApply = (f: ReportFilterState) => {
    setFilters(f);
    void onFilterChange?.(f);
  };

  return (
    <>
      {showReportFilters && (
        <div className="mb-3 flex justify-end md:absolute md:right-0 md:top-0 md:mb-0">
          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() => setAreReportFiltersOpen((open) => !open)}
          >
            <Icon icon="hugeicons:filter" className="size-4" />
            {areReportFiltersOpen ? "Hide Filters" : "Show Filters"}
          </Button>
        </div>
      )}

      {showReportFilters && areReportFiltersOpen && (
        <div className="mb-4 flex justify-center">
          <div className="w-full max-w-5xl">
            <ReportFilterPanel
              filters={filters}
              onChange={setFilters}
              onReset={handleReset}
              onApply={handleApply}
              loading={loading}
            />
          </div>
        </div>
      )}

      <div
        className={cn(
          "w-full max-w-full rounded-2xl bg-white shadow-sm",
          !useParentScroll && "overflow-x-auto",
        )}
      >
        <Table
          containerClassName={useParentScroll ? "overflow-visible" : undefined}
          className={cn(
            "w-full",
            compact && "text-xs [&_td]:text-xs [&_th]:text-xs",
            compact && "[&_td]:px-2 [&_td]:py-2 [&_th]:h-9 [&_th]:px-2",
          )}
        >
          <TableHeader
            className={stickyHeader ? "sticky top-0 z-10 bg-white shadow-sm" : undefined}
          >
            <TableRow>
              <TableHead>Date</TableHead>
              {!showDebitCreditColumns && <TableHead>Type</TableHead>}
              {showJournalReferenceColumn && <TableHead>Journal Reference</TableHead>}
              {showAccountColumn && <TableHead>Account</TableHead>}
              {!showDebitCreditColumns && <TableHead>Amount</TableHead>}
              <TableHead>Description</TableHead>
              <TableHead>Balance Before</TableHead>
              {showDebitCreditColumns && <TableHead>Debit</TableHead>}
              {showDebitCreditColumns && <TableHead>Credit</TableHead>}
              <TableHead>Balance After</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8}>
                  <div className="text-center p-8 opacity-50">Loading transactions...</div>
                </TableCell>
              </TableRow>
            ) : !entries.length ? (
              <TableRow>
                <TableCell colSpan={8}>
                  <EmptyState />
                </TableCell>
              </TableRow>
            ) : (
              entries.map((transaction_entry) => (
                <TableRow key={transaction_entry.id}>
                  <TableCell>{formatDateTime(transaction_entry.transaction_date)}</TableCell>
                  {!showDebitCreditColumns && <TableCell>{transaction_entry.entry_type}</TableCell>}
                  {showJournalReferenceColumn && (
                    <TableCell
                      className="cursor-pointer font-mono hover:text-primary"
                      onClick={() =>
                        transaction_entry.transaction?.base_uuid &&
                        router.push(`/transactions/${transaction_entry.transaction.base_uuid}`)
                      }
                    >
                      {transaction_entry.transaction?.reference_code || "-"}
                    </TableCell>
                  )}
                  {showAccountColumn && (
                    <TableCell
                      className="cursor-pointer hover:text-primary"
                      onClick={() => seeAccountDetails(transaction_entry?.account?.base_uuid || "")}
                    >
                      {transaction_entry.account?.account_name || "-"}
                    </TableCell>
                  )}
                  {!showDebitCreditColumns && (
                    <TableCell>{formatEntryAmount(transaction_entry)}</TableCell>
                  )}
                  <TableCell>
                    {compact ? (
                      <div className="w-40 whitespace-normal break-words">
                        <TruncatedText
                          text={formatNumbersInText(transaction_entry.description ?? "")}
                          maxLength={40}
                        />
                      </div>
                    ) : (
                      formatNumbersInText(transaction_entry.description ?? "")
                    )}
                  </TableCell>
                  <TableCell>
                    {transaction_entry.balance_before
                      ? formatEntryBalance(
                          transaction_entry,
                          transaction_entry.balance_before,
                          transaction_entry.foreign_balance_before,
                        )
                      : "-"}
                  </TableCell>
                  {showDebitCreditColumns && (
                    <TableCell>
                      {transaction_entry.entry_type === "debit"
                        ? formatEntryAmount(transaction_entry)
                        : "—"}
                    </TableCell>
                  )}
                  {showDebitCreditColumns && (
                    <TableCell>
                      {transaction_entry.entry_type === "credit"
                        ? formatEntryAmount(transaction_entry)
                        : "—"}
                    </TableCell>
                  )}
                  <TableCell>
                    {transaction_entry.balance_after
                      ? formatEntryBalance(
                          transaction_entry,
                          transaction_entry.balance_after,
                          transaction_entry.foreign_balance_after,
                        )
                      : "-"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
