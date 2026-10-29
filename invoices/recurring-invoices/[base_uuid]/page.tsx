"use client";

import {Icon} from "@iconify/react";
import {useParams, useRouter} from "next/navigation";
import {useEffect, useState} from "react";
import {useSelector} from "react-redux";

import {RECURRING_INVOICES_API} from "#/_api/api.helpers";
import Approvals from "#/_components/common/approvals/approvals";
import {DeleteConfirmationDialog} from "#/_components/common/dialogs/delete-confirmation-dialog";
import PageLayout from "#/_components/common/layouts/page-layout";
import {Badge} from "#/_components/custom/badge";
import {useToast} from "#/_hooks/use-toast";
import {formatCurrency} from "#/_lib/utils";
import {IRecurringInvoice} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {format} from "date-fns";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";
import {RecordSwitcher} from "#/_components/common/record-switcher";

export default function RecurringInvoiceDetailPage() {
  const router = useRouter();
  const params = useParams();
  const {toast} = useToast();

  const [recurringInvoice, setRecurringInvoice] = useState<IRecurringInvoice | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [approvalToggleContainer, setApprovalToggleContainer] = useState<HTMLDivElement | null>(
    null,
  );

  const currentInstitution = useSelector(selectSelectedInstitution);
  const base_uuid = params.base_uuid as string;

  const fetchRecurringInvoice = async () => {
    if (!base_uuid) return;
    setIsLoading(true);
    try {
      const response = await RECURRING_INVOICES_API.fetchRecurringInvoiceById({base_uuid});
      const normalized: IRecurringInvoice = {
        ...response,
        total_amount: response.total_amount ?? "0",
        currency: response.currency ?? "UGX",
        customer: {
          ...response.customer,
          email: response.customer?.email ?? "",
          phone_number: response.customer?.phone_number ?? "",
        },
      };

      setRecurringInvoice(normalized);
    } catch {
      toast({
        title: "Error",
        description: "Failed to fetch recurring invoice details",
        variant: "destructive",
      });
      router.push("/invoices/recurring-invoices");
    } finally {
      setIsLoading(false);
    }
  };

  const confirmDelete = async () => {
    if (!recurringInvoice) return;

    setIsDeleting(true);
    try {
      await RECURRING_INVOICES_API.deleteRecurringInvoice({
        base_uuid: recurringInvoice.base_uuid,
      });
      toast({
        title: "Success",
        description: "Recurring template deleted successfully",
      });
      router.push("/invoices/recurring-invoices");
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to delete template",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
    }
  };

  useEffect(() => {
    fetchRecurringInvoice();
  }, [base_uuid]);

  const getStatusBadge = (status: string) => {
    const map = {
      active: "bg-green-100 text-green-800",
      paused: "bg-amber-100 text-amber-800",
      completed: "bg-blue-100 text-blue-800",
      canceled: "bg-gray-200 text-gray-600",
    };

    return map[status as keyof typeof map] ?? "bg-gray-100 text-gray-600";
  };

  const getFrequencyLabel = (frequency: string) => {
    const map = {
      daily: "Daily",
      weekly: "Weekly",
      monthly: "Monthly",
      biannual: "Biannually",
      annual: "Annually",
    };
    return map[frequency as keyof typeof map] ?? frequency;
  };

  // Loading skeleton
  if (isLoading) {
    return (
      <PageLayout>
        <div className="space-y-6">
          <div className="h-8 bg-gray-200 animate-pulse rounded w-1/4" />
          <div className="h-64 bg-gray-200 animate-pulse rounded" />
        </div>
      </PageLayout>
    );
  }

  if (!recurringInvoice) {
    return (
      <PageLayout>
        <div className="text-center py-8">
          <p className="text-muted-foreground">Recurring invoice not found</p>
          <Button onClick={() => router.push("/invoices/recurring-invoices")} className="mt-4">
            Back to Recurring Invoices
          </Button>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <Approvals
        entity="RecurringInvoice"
        toggleContainer={approvalToggleContainer}
        data={{
          base_uuid: recurringInvoice.base_uuid,
          model_content_type_id: recurringInvoice.model_content_type_id,
          approval_status: recurringInvoice.approval_status,
        }}
        onRefresh={fetchRecurringInvoice}
      >
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="sm"
              className="border rounded-full h-10 w-10"
              onClick={() => router.push("/invoices?tab=recurring")}
            >
              <Icon icon="hugeicons:arrow-left-02" className="w-4 h-4" />
            </Button>
            <div className="flex gap-4 items-center">
              <div className="flex items-center gap-3">
                <RecordSwitcher<IRecurringInvoice>
                  currentId={recurringInvoice.base_uuid}
                  currentLabel={recurringInvoice.reference_code}
                  currentDescription={recurringInvoice.customer?.customer_name}
                  basePath="/invoices/recurring-invoices"
                  label="Recurring Invoices"
                  fetchFirstPage={(query) =>
                    RECURRING_INVOICES_API.fetchRecurringInvoices(query ?? {})
                  }
                  fetchFromUrl={RECURRING_INVOICES_API.fetchRecurringInvoicesFromUrl}
                  idKey="base_uuid"
                  labelKey="reference_code"
                  descriptionKeyFn={(item) => `Amount due: ${formatCurrency(item.total_amount)}`}
                />
              </div>
              <Badge
                className={`rounded-full border-transparent ${getStatusBadge(recurringInvoice.approval_status)}`}
              >
                {recurringInvoice.approval_status
                  ? recurringInvoice.approval_status.charAt(0).toUpperCase() +
                    recurringInvoice.approval_status.slice(1)
                  : "Unknown"}
              </Badge>
            </div>
          </div>
          <div className="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-2">
            <div ref={setApprovalToggleContainer} />
            <div className="hidden lg:flex lg:flex-wrap gap-4">
              <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_EDIT_RECURRING_INVOICES}>
                <Button
                  variant="outline"
                  onClick={() => router.push(`/invoices/recurring-invoices/${base_uuid}/edit`)}
                >
                  <Icon icon="hugeicons:edit-01" className="mr-2 h-4 w-4" /> Edit
                </Button>
              </ProtectedComponent>
              <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_DELETE_RECURRING_INVOICES}>
                <Button
                  className="text-red-600 hover:bg-red-50 hover:text-red-700"
                  variant="outline"
                  onClick={() => setIsDeleteDialogOpen(true)}
                >
                  <Icon icon="hugeicons:delete-02" className="mr-2 h-4 w-4" />
                  Delete
                </Button>
              </ProtectedComponent>
            </div>
            {/* Mobile dropdown */}
            <div className="flex lg:hidden">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="h-8 w-8 p-0 rounded-full">
                    <Icon icon="hugeicons:more-vertical-circle-01" className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>

                <DropdownMenuContent align="end">
                  <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_EDIT_RECURRING_INVOICES}>
                    <DropdownMenuItem
                      onClick={() => router.push(`/invoices/recurring-invoices/${base_uuid}/edit`)}
                    >
                      <Icon icon="hugeicons:edit-01" className="mr-2 h-4 w-4" /> Edit
                    </DropdownMenuItem>
                  </ProtectedComponent>
                  <ProtectedComponent
                    permissionCode={PERMISSION_CODES.CAN_DELETE_RECURRING_INVOICES}
                  >
                    <DropdownMenuItem
                      onClick={() => setIsDeleteDialogOpen(true)}
                      className="text-red-600"
                    >
                      <Icon icon="hugeicons:delete-02" className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  </ProtectedComponent>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>

        {/* Recurring Invoice Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border rounded-lg p-6 bg-white">
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-500">Customer</h3>
              <p className="text-lg font-semibold">{recurringInvoice.customer?.customer_name}</p>
              <p className="text-sm text-gray-600">{recurringInvoice.customer?.email}</p>
              <p className="text-sm text-gray-600">{recurringInvoice.customer?.phone_number}</p>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-500">Frequency</h3>
              <p className="text-base font-medium">
                {getFrequencyLabel(recurringInvoice.recurring_frequency)}
              </p>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-500">Total Amount</h3>
              <p className="text-2xl font-bold">
                {recurringInvoice.currency} {formatCurrency(recurringInvoice.total_amount)}
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm font-medium text-gray-500">Start Date</h3>
                <p className="text-base font-medium">
                  {format(new Date(recurringInvoice.start_date), "PPP")}
                </p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-500">End Date</h3>
                <p className="text-base font-medium">
                  {recurringInvoice.end_date
                    ? format(new Date(recurringInvoice.end_date), "PPP")
                    : "Indefinite"}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm font-medium text-gray-500">Next Run Date</h3>
                <p className="text-base font-medium text-blue-600">
                  {format(new Date(recurringInvoice.next_recurring_date), "PPP")}
                </p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-500">Last Generated</h3>
                <p className="text-base font-medium">
                  {recurringInvoice.last_generated_date
                    ? format(new Date(recurringInvoice.last_generated_date), "PPP")
                    : "Not yet generated"}
                </p>
              </div>
            </div>

            {recurringInvoice.notes && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Notes</h3>
                <p className="text-sm text-gray-600">{recurringInvoice.notes}</p>
              </div>
            )}
          </div>
        </div>

        {/* Line Items Section */}
        <div className="pt-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              Recurring Line Items ({recurringInvoice.recurring_items.length})
            </h3>
          </div>

          {recurringInvoice.recurring_items.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No line items found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-gray-800">
                  <TableRow className="hover:bg-gray-800">
                    <TableHead className="!text-white">#</TableHead>
                    <TableHead className="!text-white">Item</TableHead>
                    <TableHead className="!text-white">Item Code</TableHead>
                    <TableHead className="!text-white">Quantity</TableHead>
                    <TableHead className="!text-white">Unit Price</TableHead>
                    {recurringInvoice.recurring_items.some((item) => item.unit_of_measure) && (
                      <TableHead className="!text-white">Unit</TableHead>
                    )}
                    <TableHead className="!text-white text-right">Line Total</TableHead>
                  </TableRow>
                </TableHeader>

                <TableBody>
                  {recurringInvoice.recurring_items.map((item, index) => (
                    <TableRow key={item.base_uuid || index}>
                      <TableCell>{index + 1}</TableCell>
                      <TableCell className="font-normal">
                        {item.line_item?.item_name || "N/A"}
                      </TableCell>
                      <TableCell className="font-normal">
                        {item.line_item?.item_code || "-"}
                      </TableCell>
                      <TableCell className="">{formatCurrency(item.quantity)}</TableCell>
                      <TableCell className="">
                        {recurringInvoice.currency} {formatCurrency(item.unit_price)}
                      </TableCell>
                      {recurringInvoice.recurring_items.some((item) => item.unit_of_measure) && (
                        <TableCell>
                          {item.unit_of_measure?.unit_abbreviation ||
                            item.unit_of_measure?.unit_name ||
                            "-"}
                        </TableCell>
                      )}
                      <TableCell className="text-right font-medium">
                        {recurringInvoice.currency} {formatCurrency(item.line_total)}
                      </TableCell>
                    </TableRow>
                  ))}

                  {/* Total Row */}
                  <TableRow className="bg-gray-100 font-semibold">
                    <TableCell
                      colSpan={
                        recurringInvoice.recurring_items.some((item) => item.unit_of_measure)
                          ? 6
                          : 5
                      }
                      className="text-right"
                    >
                      Total Amount
                    </TableCell>
                    <TableCell className="text-right text-lg">
                      {recurringInvoice.currency} {formatCurrency(recurringInvoice.total_amount)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        {/* Tax Summary (if applicable) */}
        {recurringInvoice.tax_summary && (
          <div className="border-t pt-6 space-y-4">
            <h3 className="text-lg font-semibold">Tax Summary</h3>
            <div className="border rounded-lg p-4 bg-gray-50 space-y-2">
              {recurringInvoice.tax_summary.tax_details?.map((tax, index) => (
                <div key={index} className="flex justify-between text-sm">
                  <span className="font-medium">
                    {tax.tax_name} {tax.is_inclusive ? "(Inclusive)" : "(Exclusive)"}
                  </span>
                  <span>
                    {recurringInvoice.currency} {formatCurrency(tax.amount)}
                  </span>
                </div>
              ))}
              <div className="border-t pt-2 flex justify-between font-semibold">
                <span>Total Tax</span>
                <span>
                  {recurringInvoice.currency}{" "}
                  {formatCurrency(recurringInvoice.tax_summary.total_tax)}
                </span>
              </div>
            </div>
          </div>
        )}

        <DeleteConfirmationDialog
          isOpen={isDeleteDialogOpen}
          onClose={() => setIsDeleteDialogOpen(false)}
          onConfirm={confirmDelete}
          title="Delete Recurring Template"
          description={`Are you sure you want to delete this recurring invoice template for ${recurringInvoice.customer?.customer_name}? This action cannot be undone.`}
          isDeleting={isDeleting}
        />
      </Approvals>
    </PageLayout>
  );
}
