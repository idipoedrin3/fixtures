"use client";

import {useEffect, useRef, useState} from "react";
import {TRANSACTIONS_API} from "#/_api/api.helpers";
import {showSuccessToast} from "#/_api/helpers";
import {formatCurrency, formatDateTime, showErrorToast} from "#/_lib/utils";
import {Button} from "@/components/ui/button";
import {EmptyState} from "../nodata";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface IJournalEntry {
  base_uuid: string;
  date: string;
  description: string;
  journal_reference_code: string;
  transaction_entry_type: "debit" | "credit";
  amount: number;
  foreign_amount?: number | string | null;
  base_currency?: string | null;
  account: {
    id: number;
    base_uuid: string;
    name: string;
    reference_code: string | null;
    currency?: string | null;
  };
}

export interface IJournalEntriesData {
  journal_items: IJournalEntry[];
  total_credits: number;
  total_debits: number;
}

const EMPTY_JOURNAL_ENTRIES: IJournalEntriesData = {
  journal_items: [],
  total_credits: 0,
  total_debits: 0,
};

interface JournalEntriesTableProps {
  entries?: IJournalEntry[] | IJournalEntriesData;
  modelContentTypeId?: number | null;
  objectBaseUuid?: string | null;
  showProcessFinancialEvents?: boolean;
  loading?: boolean;
  startDate?: string;
  endDate?: string;
}

export default function JournalEntriesTable({
  entries,
  modelContentTypeId,
  objectBaseUuid,
  showProcessFinancialEvents = false,
  loading = false,
  startDate,
  endDate,
}: JournalEntriesTableProps) {
  const router = useRouter();

  const [fetchedEntries, setFetchedEntries] = useState<IJournalEntriesData>(EMPTY_JOURNAL_ENTRIES);
  const [isFetching, setIsFetching] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processedObjectKey, setProcessedObjectKey] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const processingRef = useRef(false);

  const shouldFetch = Boolean(modelContentTypeId && objectBaseUuid);
  const objectKey = `${modelContentTypeId}:${objectBaseUuid}`;
  const canProcessFinancialEvents =
    showProcessFinancialEvents === true && shouldFetch && processedObjectKey !== objectKey;

  const handleProcessFinancialEvents = async () => {
    if (
      !canProcessFinancialEvents ||
      !modelContentTypeId ||
      !objectBaseUuid ||
      processingRef.current
    ) {
      return;
    }

    processingRef.current = true;
    setIsProcessing(true);

    try {
      await TRANSACTIONS_API.processFinancialEvents({
        contentTypeId: modelContentTypeId,
        objectBaseUuid,
      });
      setProcessedObjectKey(objectKey);
      setRefreshVersion((version) => version + 1);
      showSuccessToast("Financial events processed successfully");
    } catch (error) {
      showErrorToast({
        error,
        defaultMessage: "Failed to process financial events",
      });
    } finally {
      processingRef.current = false;
      setIsProcessing(false);
    }
  };

  useEffect(() => {
    if (!modelContentTypeId || !objectBaseUuid) {
      setFetchedEntries(EMPTY_JOURNAL_ENTRIES);
      setIsFetching(false);
      return;
    }

    let isCurrentRequest = true;

    const fetchJournalEntries = async () => {
      setIsFetching(true);

      try {
        const response = await TRANSACTIONS_API.fetchObjectJournalEntries({
          contentTypeId: modelContentTypeId,
          objectBaseUuid,
          ...(startDate && {start_date: startDate}),
          ...(endDate && {end_date: endDate}),
        });

        if (isCurrentRequest) {
          setFetchedEntries(response);
        }
      } catch {
        if (isCurrentRequest) {
          setFetchedEntries(EMPTY_JOURNAL_ENTRIES);
        }
      } finally {
        if (isCurrentRequest) {
          setIsFetching(false);
        }
      }
    };

    fetchJournalEntries();

    return () => {
      isCurrentRequest = false;
    };
  }, [modelContentTypeId, objectBaseUuid, startDate, endDate, refreshVersion]);

  const resolvedEntries = shouldFetch ? fetchedEntries : (entries ?? EMPTY_JOURNAL_ENTRIES);

  const isNewShape = !Array.isArray(resolvedEntries) && "journal_items" in resolvedEntries;
  const items: IJournalEntry[] = isNewShape
    ? (resolvedEntries as IJournalEntriesData).journal_items
    : (resolvedEntries as IJournalEntry[]);
  const totalDebits = isNewShape ? (resolvedEntries as IJournalEntriesData).total_debits : null;
  const totalCredits = isNewShape ? (resolvedEntries as IJournalEntriesData).total_credits : null;
  const isLoading = loading || isFetching;

  const formatAmountsInText = (text: string) =>
    text.replace(/\d+\.\d+/g, (match) => formatCurrency(match));
  const seeAccountDetails = (base_uuid: string) => {
    router.push(`/accounts/${base_uuid}`);
  };

  const formatEntryAmount = (entry: IJournalEntry) => (
    <>
      {entry.foreign_amount !== null &&
      entry.foreign_amount !== undefined &&
      entry.account?.currency ? (
        <>
          {entry.account.currency} {formatCurrency(entry.foreign_amount)}
          <span className="ml-1 text-xs text-muted-foreground">
            ({entry.base_currency} {formatCurrency(entry.amount)})
          </span>
        </>
      ) : (
        formatCurrency(entry.amount)
      )}
    </>
  );

  return (
    <div className="border overflow-x-auto">
      {canProcessFinancialEvents && (
        <div className="flex justify-end border-b p-3">
          <Button
            type="button"
            size="sm"
            onClick={handleProcessFinancialEvents}
            disabled={isProcessing || isLoading}
          >
            {isProcessing ? "Processing..." : "Process Financial Events"}
          </Button>
        </div>
      )}
      <Table>
        <TableHeader>
          <TableRow className="bg-gray-800 hover:bg-gray-800">
            <TableHead className="!text-white">Date</TableHead>
            <TableHead className="!text-white">Journal Reference</TableHead>
            <TableHead className="!text-white">Account</TableHead>
            <TableHead className="!text-white">Description</TableHead>
            <TableHead className="!text-white">Debit</TableHead>
            <TableHead className="!text-white">Credit</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                Loading journal entries...
              </TableCell>
            </TableRow>
          ) : !items.length ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={6}>
                <EmptyState />
              </TableCell>
            </TableRow>
          ) : (
            items.map((entry, index) => (
              <TableRow key={index}>
                <TableCell>{formatDateTime(entry.date)}</TableCell>
                <TableCell
                  className="font-mono cursor-pointer hover:text-primary"
                  onClick={() => entry.base_uuid && router.push(`/transactions/${entry.base_uuid}`)}
                >
                  {entry.journal_reference_code}
                </TableCell>
                <TableCell
                  className="cursor-pointer hover:text-primary"
                  onClick={() => seeAccountDetails(entry.account?.base_uuid || "")}
                >
                  {entry.account?.name || "-"}
                </TableCell>
                <TableCell>
                  {entry.description ? formatAmountsInText(entry.description) : "-"}
                </TableCell>
                <TableCell className="font-medium">
                  {entry.transaction_entry_type === "debit" ? (
                    formatEntryAmount(entry)
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
                <TableCell className="font-medium">
                  {entry.transaction_entry_type === "credit" ? (
                    <span className="text-blue-600">{formatEntryAmount(entry)}</span>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
        {totalDebits !== null && totalCredits !== null && (
          <TableFooter>
            <TableRow className="bg-gray-50 font-semibold">
              <TableCell colSpan={4} className="text-right font-semibold">
                Totals
              </TableCell>
              <TableCell className="font-semibold">{formatCurrency(totalDebits)}</TableCell>
              <TableCell className="font-semibold text-blue-600">
                {formatCurrency(totalCredits)}
              </TableCell>
            </TableRow>
          </TableFooter>
        )}
      </Table>
    </div>
  );
}
