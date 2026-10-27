import {useRef, useState} from "react";
import {MoreHorizontal, Edit, Trash2} from "lucide-react";
import {useParams} from "next/navigation";

import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {formatCurrency, formatDate} from "#/_lib/utils";
import {IBankStatementTransaction} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {showErrorToast} from "#/_lib/utils";
import {showSuccessToast} from "#/_api/helpers";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {DeleteConfirmationDialog} from "#/_components/common/dialogs/delete-confirmation-dialog";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {BANK_STATEMENT_TRANSACTIONS_API} from "#/_api/api.helpers";
import {TransactionForm} from "#/(dashboard)/banks/[id]/statements/[sid]/transaction.form";
import {Dialog, DialogContent, DialogHeader, DialogTitle} from "@/components/ui/dialog";

export default function TransactionEntriesTable({bank_base_uuid}: {bank_base_uuid: string}) {
  const router = useRouter();
  const params = useParams();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<IBankStatementTransaction | null>(null);
  const [open, setOpen] = useState(false);
  const [editData, setEditData] = useState<IBankStatementTransaction | null>(null);
  const [statement, setStatement] = useState<string>("");

  const refreshTableRef = useRef<() => void>(() => {});

  const handleEdit = (entry: IBankStatementTransaction) => {
    setEditData(entry);
    setStatement(entry.statement.id.toString());
    setOpen(true);
    refreshTableRef.current();
  };

  const handleDelete = (entry: IBankStatementTransaction) => {
    setSelectedEntry(entry);
    setIsDeleteDialogOpen(true);
    refreshTableRef.current();
  };

  const confirmDelete = async (refresh: () => void) => {
    if (!selectedEntry) return;

    try {
      await BANK_STATEMENT_TRANSACTIONS_API.delete({base_uuid: selectedEntry.base_uuid});
      showSuccessToast("Transaction deleted successfully");
      setIsDeleteDialogOpen(false);
      setSelectedEntry(null);
      refresh();
    } catch (error) {
      showErrorToast({
        error,
        defaultMessage: "Failed to delete transaction",
      });
    }
  };

  return (
    <>
      <PaginatedTableWrapper<
        IBankStatementTransaction,
        {page?: number; search?: string; bank_base_uuid: string}
      >
        deps={[bank_base_uuid]}
        query={{bank_base_uuid}}
        fetchFirstPage={(query) => {
          const {page = 1, } = query || {bank_base_uuid: ""};

          return BANK_STATEMENT_TRANSACTIONS_API.fetch({
            page,
            bank_base_uuid,
          });
        }}
        fetchFromUrl={BANK_STATEMENT_TRANSACTIONS_API.fetchFromUrl}
        className="mt-5"
      >
        {({data, loading, refresh}) => {
          const entries = data?.results ?? [];

          if (refreshTableRef) {
            refreshTableRef.current = refresh;
          }

          return (
            <div className="overflow-x-auto w-full max-w-full rounded-2xl bg-white shadow-sm">
              <Table className="w-full">
                <TableHeader>
                  <TableRow>
                    <TableHead>Transaction Code</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <div className="text-center p-8 opacity-50">Loading transactions...</div>
                      </TableCell>
                    </TableRow>
                  ) : !entries.length ? (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <div className="text-center p-8 opacity-50">No transactions found.</div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    entries.map((transaction, i) => (
                      <TableRow key={transaction.id}>
                        <TableCell className="">{transaction.transaction_code}</TableCell>
                        <TableCell className="">{formatCurrency(transaction.amount)}</TableCell>
                        <TableCell className="">{transaction.notes}</TableCell>
                        <TableCell className="">{formatDate(transaction.date)}</TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" className="h-8 w-8 p-0">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleEdit(transaction)}>
                                <Edit className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => handleDelete(transaction)}
                                className="text-red-600"
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          );
        }}
      </PaginatedTableWrapper>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Bank Transaction</DialogTitle>
          </DialogHeader>
          <TransactionForm
            edit
            editData={editData}
            statement={statement}
            onComplete={() => {
              setOpen(false);
              setEditData(null);
            }}
          />
        </DialogContent>
      </Dialog>

      <DeleteConfirmationDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => {
          setIsDeleteDialogOpen(false);
          setSelectedEntry(null);
        }}
        onConfirm={() => confirmDelete(() => {})}
        title="Delete Transaction"
        description={`Are you sure you want to delete this transaction? This action cannot be undone.`}
        isDeleting={false}
      />
    </>
  );
}
