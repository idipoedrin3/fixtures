"use client";

import ProtectedComponent from "../../custom/protected-component";

import {PERMISSION_CODES} from "#/_constants/enums";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface DeleteConfirmationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: string;
  isDeleting: boolean;
  permissions?: PERMISSION_CODES | PERMISSION_CODES[];
  confirmLabel?: string;
  processingLabel?: string;
}

export function DeleteConfirmationDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  isDeleting,
  permissions = [],
  confirmLabel = "Delete",
  processingLabel = "Deleting...",
}: DeleteConfirmationDialogProps) {
  function deleteDialog() {
    return (
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="w-[90vw] max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex flex-row justify-end gap-2 sm:justify-end">
            <Button disabled={isDeleting} type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={isDeleting} type="button" variant="destructive" onClick={onConfirm}>
              {isDeleting ? (
                <>
                  <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  {processingLabel}
                </>
              ) : (
                confirmLabel
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return permissions && !Array.isArray(permissions) ? (
    <ProtectedComponent permissionCode={permissions || []}>{deleteDialog()}</ProtectedComponent>
  ) : (
    deleteDialog()
  );
}
