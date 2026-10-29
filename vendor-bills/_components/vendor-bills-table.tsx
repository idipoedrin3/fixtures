"use client";

import {useState} from "react";
import {Icon} from "@iconify/react";

import {EmptyState} from "../../../_components/common/nodata";

import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {Button} from "@/components/ui/button";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {IVendor, IVendorBill} from "#/_types/api.types";
import {capitalize, formatCurrency, formatDate} from "#/_lib/utils";
import {DeleteConfirmationDialog} from "#/_components/common/dialogs/delete-confirmation-dialog";
import {VENDOR_BILLS_API} from "#/_api/api.helpers";
import {useToast} from "#/_hooks/use-toast";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";
import {Badge} from "#/_components/custom/badge";
import {SortableHeader} from "#/_components/common/tables/sortable-header";

interface VendorBillsTableProps {
  bills: IVendorBill[];
  isLoading: boolean;
  onBillDeleted: () => void;
  showVendor?: boolean;
  onSort: (field: string) => void;
  onRemoveSort: (field: string) => void;
  isAsc: (field: string) => boolean;
  isDesc: (field: string) => boolean;
  status: string;
  onStatusChange: (value: string) => void;
  paymentStatus: string;
  onPaymentStatusChange: (value: string) => void;
  grnStatus: string;
  onGrnStatusChange: (value: string) => void;
  vendorFilter?: string;
  onVendorFilterChange?: (value: string) => void;
  vendorOptions?: IVendor[];
  vendorSearch?: string;
  onVendorSearchChange?: (value: string) => void;
  vendorsLoading?: boolean;
  vendorHasMore?: boolean;
  onLoadMoreVendors?: () => void;
  onVendorFilterOpen?: () => void;
}

export function VendorBillsTable({
  bills,
  isLoading,
  onBillDeleted,
  showVendor = true,
  onSort,
  onRemoveSort,
  isAsc,
  isDesc,
  status,
  onStatusChange,
  paymentStatus,
  onPaymentStatusChange,
  grnStatus,
  onGrnStatusChange,
  vendorFilter = "all",
  onVendorFilterChange = () => {},
  vendorOptions = [],
  vendorSearch = "",
  onVendorSearchChange = () => {},
  vendorsLoading = false,
  vendorHasMore = false,
  onLoadMoreVendors = () => {},
  onVendorFilterOpen = () => {},
}: VendorBillsTableProps) {
  const router = useRouter();
  const {toast} = useToast();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedBill, setSelectedBill] = useState<IVendorBill | null>(null);

  const handleViewDetails = (bill: IVendorBill) => {
    router.push(`/vendor-bills/${bill.base_uuid}`);
  };

  const handleEdit = (bill: IVendorBill) => {
    router.push(`/vendor-bills/${bill.base_uuid}/edit`);
  };

  const handleDelete = (bill: IVendorBill) => {
    setSelectedBill(bill);
    setIsDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!selectedBill) return;

    try {
      await VENDOR_BILLS_API.deleteVendorBill({billUuid: selectedBill.base_uuid});
      toast({
        title: "Success",
        description: "Vendor bill deleted successfully",
      });
      onBillDeleted();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to delete vendor bill",
        variant: "destructive",
      });
    } finally {
      setIsDeleteDialogOpen(false);
      setSelectedBill(null);
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

  function seeVendorDetails(base_uuid: string | undefined): void {
    router.push(`/vendors/${base_uuid}`);
  }

  return (
    <>
      <div className="">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <SortableHeader
                  label="Reference Code"
                  field="reference_code"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                />
              </TableHead>
              <TableHead>
                <SortableHeader
                  label="Branch"
                  field="branch__branch_name"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                />
              </TableHead>
              <TableHead>
                <SortableHeader
                  label="Received Date"
                  field="received_date"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                />
              </TableHead>
              <TableHead>
                <SortableHeader
                  label="Due Date"
                  field="due_date"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                />
              </TableHead>
              {showVendor && (
                <TableHead>
                  <SortableHeader
                    label="Vendor"
                    field="vendor"
                    allowSorting={false}
                    onSort={onSort}
                    onRemove={onRemoveSort}
                    isAsc={isAsc}
                    isDesc={isDesc}
                    filterValue={vendorFilter}
                    onFilterChange={(value) => onVendorFilterChange(value as string)}
                    filterSearchValue={vendorSearch}
                    onFilterSearchChange={onVendorSearchChange}
                    filterLoading={vendorsLoading}
                    filterHasMore={vendorHasMore}
                    onFilterLoadMore={onLoadMoreVendors}
                    showFilterSearch
                    filterSearchPlaceholder="Search vendors..."
                    onFilterOpen={onVendorFilterOpen}
                    filterOptions={vendorOptions.map((vendor) => ({
                      label: vendor.vendor_name,
                      value: vendor.base_uuid,
                      description: vendor.email,
                    }))}
                  />
                </TableHead>
              )}
              <TableHead>
                <SortableHeader
                  label="Total Amount"
                  field="total_amount"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                />
              </TableHead>
              <TableHead>
                <SortableHeader
                  label="Bill Stage"
                  field="status"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                  filterValue={status}
                  onFilterChange={(value) => onStatusChange(value as string)}
                  filterOptions={[
                    {label: "Draft", value: "draft"},
                    {label: "Approved", value: "approved"},
                    {label: "Cancelled", value: "cancelled"},
                  ]}
                />
              </TableHead>
              <TableHead>
                <SortableHeader
                  label="Payment Status"
                  field="payment_status"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                  filterValue={paymentStatus}
                  onFilterChange={(value) => onPaymentStatusChange(value as string)}
                  filterOptions={[
                    {label: "Unpaid", value: "unpaid"},
                    {label: "Partially Paid", value: "partially_paid"},
                    {label: "Paid", value: "paid"},
                  ]}
                />
              </TableHead>
              <TableHead>
                <SortableHeader
                  label="GRN Status"
                  field="goods_received_note_status"
                  onSort={onSort}
                  onRemove={onRemoveSort}
                  isAsc={isAsc}
                  isDesc={isDesc}
                  filterValue={grnStatus}
                  onFilterChange={(value) => onGrnStatusChange(value as string)}
                  filterOptions={[
                    {label: "Not Received", value: "not_received"},
                    {label: "Partially Received", value: "partially_received"},
                    {label: "Fully Received", value: "full_received"},
                  ]}
                />
              </TableHead>

              <TableHead className="w-[50px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!bills || !bills.length ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={showVendor ? 11 : 10}>
                  <EmptyState />
                </TableCell>
              </TableRow>
            ) : (
              bills.map((bill) => (
                <TableRow key={bill.id}>
                  <TableCell className="font-normal">{bill.reference_code || "-"}</TableCell>
                  <TableCell className="font-normal">{bill.branch?.branch_name || "-"}</TableCell>
                  <TableCell className="font-normal">
                    {formatDate(bill.received_date) || "-"}
                  </TableCell>
                  <TableCell className="font-normal">{formatDate(bill.due_date) || "-"}</TableCell>
                  {showVendor && (
                    <TableCell
                      onClick={() => seeVendorDetails(bill.purchase_order?.vendor?.base_uuid)}
                      className="cursor-pointer hover:text-primary"
                    >
                      {(bill.purchase_order?.vendor?.vendor_name || bill?.vendor?.vendor_name) ??
                        "-"}
                    </TableCell>
                  )}
                  <TableCell className="">
                    {bill.currency?.code} {formatCurrency(bill.total_amount)}
                  </TableCell>
                  <TableCell>
                    <Badge status={bill.status}>{capitalize(bill.status)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge status={bill.payment_status}>{capitalize(bill.payment_status)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge status={bill.goods_received_note_status}>
                      {capitalize(bill.goods_received_note_status)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0">
                          <Icon icon="hugeicons:more-vertical-circle-01" className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <ProtectedComponent
                          permissionCode={PERMISSION_CODES.CAN_CREATE_VENDOR_BILLS}
                        >
                          <DropdownMenuItem onClick={() => handleViewDetails(bill)}>
                            <Icon icon="hugeicons:view" className="mr-2 h-4 w-4" />
                            View Details
                          </DropdownMenuItem>
                        </ProtectedComponent>
                        {bill.allow_changes === true && (
                          <>
                            <ProtectedComponent
                              permissionCode={PERMISSION_CODES.CAN_EDIT_VENDOR_BILLS}
                            >
                              <DropdownMenuItem onClick={() => handleEdit(bill)}>
                                <Icon icon="hugeicons:edit-01" className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                            </ProtectedComponent>
                            <ProtectedComponent
                              permissionCode={PERMISSION_CODES.CAN_DELETE_VENDOR_BILLS}
                            >
                              <DropdownMenuItem
                                onClick={() => handleDelete(bill)}
                                className="text-red-600"
                              >
                                <Icon icon="hugeicons:delete-02" className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </ProtectedComponent>
                          </>
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

      <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_DELETE_VENDOR_BILLS}>
        <DeleteConfirmationDialog
          isOpen={isDeleteDialogOpen}
          onClose={() => {
            setIsDeleteDialogOpen(false);
            setSelectedBill(null);
          }}
          onConfirm={confirmDelete}
          title="Delete Vendor Bill"
          description={`Are you sure you want to delete this bill? This action cannot be undone.`}
          isDeleting={false}
        />
      </ProtectedComponent>
    </>
  );
}
