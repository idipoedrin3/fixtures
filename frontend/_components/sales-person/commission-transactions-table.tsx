"use client";

import type {ICommissionTransaction} from "#/_types/api.types";

import {EmptyState} from "../common/nodata";

import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {formatCurrency, formatDate} from "#/_lib/utils";

interface Props {
  transactions: ICommissionTransaction[];
}

export default function CommissionTransactionsTable({transactions}: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Transaction Code</TableHead>
          <TableHead>Type</TableHead>
          {/* <TableHead>Commission %</TableHead> */}
          <TableHead>Amount</TableHead>
          <TableHead>Date</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {!transactions?.length ? (
          <TableRow className="hover:bg-transparent">
            <TableCell colSpan={4}>
              <EmptyState />
            </TableCell>
          </TableRow>
        ) : (
          transactions.map((tx, idx) => (
            <TableRow key={tx.id}>
              <TableCell className="font-mono">{idx + 1}</TableCell>
              <TableCell className="capitalize">{tx.commission_type}</TableCell>
              {/* <TableCell>{tx.commission_percentage}%</TableCell> */}
              <TableCell>{formatCurrency(tx.amount)}</TableCell>
              <TableCell>{formatDate(tx.created_at)}</TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
