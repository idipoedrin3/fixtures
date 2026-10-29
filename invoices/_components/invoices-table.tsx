"use client";

import {useState} from "react";
import {Icon} from "@iconify/react";
import {EmptyState} from "../../../_components/common/nodata";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {Button} from "@/components/ui/button";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {Badge} from "#/_components/custom/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {ICustomer, IInvoice} from "#/_types/api.types";
import {formatCurrency, formatDate} from "#/_lib/utils";
import {DeleteConfirmationDialog} from "#/_components/common/dialogs/delete-confirmation-dialog";
import {INVOICES_API} from "#/_api/api.helpers";
import {useToast} from "#/_hooks/use-toast";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";
import {SortableHeader} from "#/_components/common/tables/sortable-header";
import {RelatedReferences} from "#/_components/common/related-references";

interface InvoicesTableProps {
  invoices: IInvoice[];
  isLoading: boolean;
  onInvoiceUpdated: () => void;
  onInvoiceDeleted: () => void;
  ordering: string;
  onSort: (field: string) => void;
  onRemoveSort: (field: string) => void;
  isAsc: (field: string) => boolean;
  isDesc: (field: string) => boolean;
  paymentStatus: "all" | "unpaid" | "partially_paid" | "paid";
  onPaymentStatusChange: (value: "all" | "unpaid" | "partially_paid" | "paid") => void;
  ginStatus: "all" | "full_issued" | "not_issued" | "partially_issued" | "not_required";
  onGinStatusChange: (
    value: "all" | "full_issued" | "not_issued" | "partially_issued" | "not_required",
  ) => void;
  customerFilter: string;
  onCustomerFilterChange: (value: string) => void;
  customerOptions: ICustomer[];
  customerSearch: string;
  onCustomerSearchChange: (value: string) => void;
  customersLoading: boolean;
  customerHasMore: boolean;
  onLoadMoreCustomers: () => void;
  onCustomerFilterOpen: () => void;
}

export function InvoicesTable({
  invoices,
  isLoading,
  onInvoiceDeleted,
  onSort,
  onRemoveSort,
  isAsc,
  isDesc,
  paymentStatus,
  ginStatus,
  onGinStatusChange,
  onPaymentStatusChange,
  customerFilter,
  onCustomerFilterChange,
  customerOptions,
  customerSearch,
  onCustomerSearchChange,
  customersLoading,
  customerHasMore,
  onLoadMoreCustomers,
  onCustomerFilterOpen,
}: InvoicesTableProps) {
  const router = useRouter();
  const {toast} = useToast();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<IInvoice | null>(null);

  const seeCustomerDetails = (base_uuid: string) => {
    router.push(`/customers/${base_uuid}`);
  };

  const handleViewDetails = (invoice: IInvoice) => {
    router.push(`/invoices/${invoice.base_uuid}`);
  };

  const handleDelete = (invoice: IInvoice) => {
    setSelectedInvoice(invoice);
    setIsDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!selectedInvoice) return;

    try {
      await INVOICES_API.deleteInvoice({invoiceUuid: selectedInvoice.base_uuid});
      toast({
        title: "Success",
        description: "Invoice deleted successfully",
      });
      onInvoiceDeleted();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to delete invoice",
        variant: "destructive",
      });
    } finally {
      setIsDeleteDialogOpen(false);
      setSelectedInvoice(null);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-4 bg-gray-200 animate-pulse rounded" />
        ))}
      </div>
    );
  }

  return (
    <>
      <div className="">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="whitespace-nowrap">
                <div className="flex items-center gap-1">
                  <SortableHeader
                    label="Invoice Code"
                    field="reference_code"
                    onSort={onSort}
                    onRemove={onRemoveSort}
                    isAsc={isAsc}
                    isDesc={isDesc}
                  />
                </div>
              </TableHead>
              <TableHead className="whitespace-nowrap">
                <div className="flex items-center gap-1">
                  <SortableHeader
                    label="Customer"
                    field="customer__customer_name"
                    onSort={onSort}
                    onRemove={onRemoveSort}
                    isAsc={isAsc}
                    isDesc={isDesc}
                    filterValue={customerFilter}
                    onFilterChange={(value) => onCustomerFilterChange(value as string)}
                    filterSearchValue={customerSearch}
                    onFilterSearchChange={onCustomerSearchChange}
                    filterLoading={customersLoading}
                    filterHasMore={customerHasMore}
                    onFilterLoadMore={onLoadMoreCustomers}
                    showFilterSearch
                    filterSearchPlaceholder="Search customers..."
                    onFilterOpen={onCustomerFilterOpen}
                    filterOptions={customerOptions.map((customer) => ({
                      label: customer.customer_name,
                      value: customer.base_uuid,
                      description: customer.email,
                    }))}
                  />
                </div>
              </TableHead>
              <TableHead className="whitespace-nowrap">
                <div className="flex items-center gap-1">
                  <SortableHeader
                    label="Issue Date"
                    field="issue_date"
                    onSort={onSort}
                    onRemove={onRemoveSort}
                    isAsc={isAsc}
                    isDesc={isDesc}
                  />
                </div>
              </TableHead>
              <TableHead className="whitespace-nowrap">
                <div className="flex items-center gap-1">
                  <SortableHeader
                    label="Due Date"
                    field="due_date"
                    onSort={onSort}
                    onRemove={onRemoveSort}
                    isAsc={isAsc}
                    isDesc={isDesc}
                  />
                </div>
              </TableHead>
              <TableHead className="whitespace-nowrap">
                <div className="flex items-center gap-1">
                  <SortableHeader
                    label="Amount Due"
                    field="amount_due"
                    onSort={onSort}
                    onRemove={onRemoveSort}
                    isAsc={isAsc}
                    isDesc={isDesc}
                  />
                </div>
              </TableHead>
              <TableHead className="whitespace-nowrap">Invoice Stage</TableHead>
              <TableHead className="whitespace-nowrap">
                <SortableHeader
                  label="Payment Status"
                  field="invoice_payment_status"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                  filterValue={paymentStatus}
                  onFilterChange={(value) =>
                    onPaymentStatusChange(value as "all" | "unpaid" | "partially_paid" | "paid")
                  }
                  filterOptions={[
                    {label: "Unpaid", value: "unpaid"},
                    {label: "Partially Paid", value: "partially_paid"},
                    {label: "Fully Paid", value: "paid"},
                  ]}
                />
              </TableHead>
              <TableHead className="whitespace-nowrap">
                <SortableHeader
                  label="GIN Status"
                  field="goods_issued_note_status"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                  filterValue={ginStatus}
                  onFilterChange={(value) =>
                    onGinStatusChange(
                      value as
                        | "all"
                        | "full_issued"
                        | "not_issued"
                        | "partially_issued"
                        | "not_required",
                    )
                  }
                  filterOptions={[
                    {label: "Full Issued", value: "full_issued"},
                    {label: "Not Issued", value: "not_issued"},
                    {label: "Partially Issued", value: "partially_issued"},
                    {label: "Not Required", value: "not_required"},
                  ]}
                />
              </TableHead>
              <TableHead className="w-[50px] whitespace-nowrap">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!invoices.length ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={9}>
                  <EmptyState />
                </TableCell>
              </TableRow>
            ) : (
              invoices.map((invoice) => (
                <TableRow key={invoice.base_uuid}>
                  <TableCell className="font-normal">{invoice?.reference_code || "—"}</TableCell>
                  <TableCell
                    className="cursor-pointer hover:text-primary"
                    onClick={() => seeCustomerDetails(invoice?.customer?.base_uuid || "")}
                  >
                    {invoice?.customer?.customer_name || "-"}
                  </TableCell>
                  <TableCell>{formatDate(invoice.issue_date)}</TableCell>
                  <TableCell>{formatDate(invoice.due_date)}</TableCell>
                  <TableCell className="">
                    {invoice.currency?.code ?? ""} {formatCurrency(invoice?.amount_due) || "0"}
                  </TableCell>
                  <TableCell>
                    <Badge status={invoice.invoice_status} />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col items-start gap-1.5">
                      <RelatedReferences
                        items={invoice.related_invoice_payments?.map((payment) => ({
                          id: payment.uuid_value,
                          reference: payment.ref_code,
                          href: `/customer-payments/${payment.uuid_value}`,
                        }))}
                      />

                      <Badge status={invoice.invoice_payment_status} />
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col items-start gap-1.5">
                      <RelatedReferences
                        items={invoice.related_goods_issued_notes?.map((gin) => ({
                          id: gin.base_uuid,
                          reference: gin.reference_code,
                          href: `/goods-issued-note/${gin.base_uuid}`,
                        }))}
                      />

                      <Badge status={invoice.goods_issued_note_status} />
                    </div>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0 rounded-full">
                          <Icon icon="hugeicons:more-vertical-circle-01" className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_VIEW_INVOICES}>
                          <DropdownMenuItem onClick={() => handleViewDetails(invoice)}>
                            <Icon icon="hugeicons:view" className="mr-2 h-4 w-4" />
                            View Details
                          </DropdownMenuItem>
                        </ProtectedComponent>
                        {invoice.allow_changes === true && (
                          <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_DELETE_INVOICES}>
                            <DropdownMenuItem
                              onClick={() => handleDelete(invoice)}
                              className="text-red-600"
                            >
                              <Icon icon="hugeicons:delete-02" className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </ProtectedComponent>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <DeleteConfirmationDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => {
          setIsDeleteDialogOpen(false);
          setSelectedInvoice(null);
        }}
        onConfirm={confirmDelete}
        title="Delete Invoice"
        description={`Are you sure you want to delete invoice ${selectedInvoice?.reference_code}? This action cannot be undone.`}
        isDeleting={false}
      />
    </>
  );
}
