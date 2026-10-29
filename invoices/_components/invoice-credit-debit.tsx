"use client";

import {Icon} from "@iconify/react";
import {Button} from "@/components/ui/button";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {SALES_CREDIT_NOTES_API} from "#/_api/api.helpers";
import {formatCurrency, formatDate} from "#/_lib/utils";
import {CustomLink as Link} from "@/platform/v1/components/link";
import {EmptyState} from "#/_components/common/nodata";

interface InvoiceCreditDebitNotesProps {
  invoiceUuid: string;
}

export function InvoiceCreditDebitNotes({invoiceUuid}: InvoiceCreditDebitNotesProps) {
  return (
    <div className="w-full space-y-4">
      <PaginatedTableWrapper
        fetchFirstPage={() =>
          SALES_CREDIT_NOTES_API.fetchCreditNotes({
            invoice: invoiceUuid,
            type: "CREDIT",
            falls_under: "SALES",
          })
        }
        fetchFromUrl={SALES_CREDIT_NOTES_API.fetchFromUrl}
        deps={[invoiceUuid]}
      >
        {({data, loading}) => {
          const creditNotes = data?.results || [];

          return (
            <div className="overflow-x-auto w-full max-w-full bg-white shadow-sm">
              <div className="min-w-[40rem] md:min-w-[50rem] lg:min-w-full">
                <Table className="border-collapse w-full">
                  <TableHeader className="bg-gray-800">
                    <TableRow className="border-none">
                      <TableHead className="!text-white">Reference</TableHead>
                      <TableHead className="!text-white">Issue Date</TableHead>
                      <TableHead className="!text-white">Description</TableHead>
                      <TableHead className="!text-white text-right">Amount</TableHead>
                      <TableHead className="!text-white w-[50px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      Array.from({length: 3}).map((_, i) => (
                        <TableRow key={i} className="border-none">
                          <TableCell colSpan={5}>
                            <div className="h-4 bg-muted animate-pulse rounded" />
                          </TableCell>
                        </TableRow>
                      ))
                    ) : creditNotes.length === 0 ? (
                      <TableRow className="border-none hover:bg-transparent">
                        <TableCell colSpan={5}>
                          <EmptyState />
                        </TableCell>
                      </TableRow>
                    ) : (
                      creditNotes.map((note) => (
                        <TableRow key={note.id} className="">
                          <TableCell className="font-medium">
                            {note?.reference_code || "-"}
                          </TableCell>
                          <TableCell>{formatDate(note.issue_date)}</TableCell>
                          <TableCell className="max-w-xs truncate">{note.description}</TableCell>
                          <TableCell className="font-semibold text-right">
                            {formatCurrency(note.amount)}
                          </TableCell>
                          <TableCell>
                            <Link href={`/credit-notes/credit/${note.base_uuid}`}>
                              <Button variant="ghost" size="sm">
                                <Icon icon="hugeicons:view" className="h-4 w-4" />
                              </Button>
                            </Link>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>
          );
        }}
      </PaginatedTableWrapper>
    </div>
  );
}

export default InvoiceCreditDebitNotes;
