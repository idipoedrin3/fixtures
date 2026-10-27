"use client";

import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {EmptyState} from "../nodata";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {IReversalEntry} from "#/_types/types.utils";
import {formatDate} from "#/_lib/utils";

interface Props {
  entries: IReversalEntry[];
  loading?: boolean;
}

export default function ReversalTransactionTable({entries, loading = false}: Props) {
  const router = useRouter();

  return (
    <div className="overflow-x-auto w-full max-w-full rounded-2xl bg-white shadow-sm">
      <Table className="w-full">
        <TableHeader>
          <TableRow>
            <TableHead>Reversal Transaction</TableHead>
            <TableHead>Reason</TableHead>
            <TableHead>Reversed By</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Reversed At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={4}>
                <div className="text-center p-8 opacity-50">Loading reversal entries...</div>
              </TableCell>
            </TableRow>
          ) : !entries.length ? (
            <TableRow>
              <TableCell colSpan={4}>
                <EmptyState />
              </TableCell>
            </TableRow>
          ) : (
            entries.map((entry, i) => (
              <TableRow key={i}>
                <TableCell>
                  {entry.reversal_transaction ? (
                    <button
                      onClick={() =>
                        router.push(`/transactions/${entry.reversal_transaction.base_uuid}`)
                      }
                      className="text-primary hover:underline font-mono text-sm"
                    >
                      {entry.reversal_transaction.reference_code}
                    </button>
                  ) : (
                    "-"
                  )}
                </TableCell>
                <TableCell>{entry.reason ?? "-"}</TableCell>
                <TableCell className="font-normal">{entry.reversed_by?.email ?? "-"}</TableCell>
                <TableCell>{entry.reversed_by?.fullname ?? "-"}</TableCell>
                <TableCell className="font-normal">
                  {entry.reversed_at ? formatDate(entry.reversed_at) : "-"}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
