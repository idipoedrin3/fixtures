"use client";

import {useState} from "react";
import {Icon} from "@iconify/react";
import {useRouter} from "next/navigation";
import {useToast} from "#/_hooks/use-toast";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {Badge} from "#/_components/custom/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {EmptyState} from "../../../_components/common/nodata";
import {RECURRING_INVOICES_API} from "#/_api/api.helpers";
import {IRecurringInvoice} from "#/_types/api.types";
import {capitalize, formatDate} from "#/_lib/utils";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {Button} from "@/components/ui/button";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";

interface RecurringInvoicesTableProps {
  templates: IRecurringInvoice[];
  isLoading: boolean;
  refresh: () => void;
}

export function RecurringInvoicesTable({
  templates,
  isLoading,
  refresh,
}: RecurringInvoicesTableProps) {
  const router = useRouter();
  const {toast} = useToast();

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [templateToDelete, setTemplateToDelete] = useState<IRecurringInvoice | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const seeCustomerDetails = (base_uuid: string) => {
    router.push(`/customers/${base_uuid}`);
  };

  const handleView = (template: IRecurringInvoice) => {
    router.push(`/invoices/recurring-invoices/${template.base_uuid}`);
  };

  const handleEdit = (template: IRecurringInvoice) => {
    router.push(`/invoices/recurring-invoices/${template.base_uuid}/edit`);
  };

  const handleDeleteClick = (template: IRecurringInvoice) => {
    setTemplateToDelete(template);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!templateToDelete) return;

    setIsDeleting(true);
    try {
      await RECURRING_INVOICES_API.deleteRecurringInvoice({
        base_uuid: templateToDelete.base_uuid,
      });

      toast({
        title: "Success",
        description: "Recurring template deleted successfully",
      });

      refresh();
      setDeleteDialogOpen(false);
      setTemplateToDelete(null);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to delete template",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-10 bg-gray-100 animate-pulse rounded-md" />
        ))}
      </div>
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Reference Code</TableHead>
            <TableHead>Customer</TableHead>
            <TableHead>Frequency</TableHead>
            <TableHead>Next Run Date</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-[60px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          {templates.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={6} className="h-64">
                <EmptyState />
              </TableCell>
            </TableRow>
          ) : (
            templates.map((template) => (
              <TableRow key={template.id} className="group">
                <TableCell className="font-medium">
                  {template.reference_code || template.name || "Unnamed"}
                </TableCell>
                <TableCell
                  className="cursor-pointer hover:text-primary"
                  onClick={() => seeCustomerDetails(template?.customer?.base_uuid || "")}
                >
                  {template.customer?.customer_name || "—"}
                </TableCell>
                <TableCell className="capitalize">{template.recurring_frequency}</TableCell>
                <TableCell>{formatDate(template?.next_recurring_date) || "—"}</TableCell>
                <TableCell>
                  <Badge status={template.approval_status ?? "unknown"}>
                    {capitalize(template.approval_status ?? "Unknown")}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Icon icon="hugeicons:more-vertical-circle-01" className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <ProtectedComponent
                        permissionCode={PERMISSION_CODES.CAN_VIEW_RECURRING_INVOICES}
                      >
                        <DropdownMenuItem onClick={() => handleView(template)}>
                          <Icon icon="hugeicons:eye" className="mr-2 h-4 w-4" />
                          View Details
                        </DropdownMenuItem>
                      </ProtectedComponent>
                      <ProtectedComponent
                        permissionCode={PERMISSION_CODES.CAN_EDIT_RECURRING_INVOICES}
                      >
                        <DropdownMenuItem onClick={() => handleEdit(template)}>
                          <Icon icon="hugeicons:edit-01" className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                      </ProtectedComponent>
                      <ProtectedComponent
                        permissionCode={PERMISSION_CODES.CAN_DELETE_RECURRING_INVOICES}
                      >
                        <DropdownMenuItem
                          onClick={() => handleDeleteClick(template)}
                          className="text-red-600 focus:text-red-600 focus:bg-red-50"
                        >
                          <Icon icon="hugeicons:delete-02" className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </ProtectedComponent>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Recurring Template?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the recurring invoice template{" "}
              <span className="font-medium">
                {templateToDelete?.reference_code || templateToDelete?.name || "—"}
              </span>
              ?
              <br />
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Icon icon="svg-spinners:180-ring" className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
