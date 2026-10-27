import {useState} from "react";
import {Icon} from "@iconify/react";
import {Textarea} from "#/_components/common/inputs/text-area";
import {Button} from "@/components/ui/button";
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

interface ConfirmationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason?: string) => void;
  title: string;
  description: string;
  contentClassName?: string;
  footerClassName?: string;
  disabled?: boolean;
  confirmText?: string;
  cancelText?: string;
  singleAction?: boolean;
  requireReason?: boolean;
  reasonLabel?: string;
  secondaryActionText?: string;
  onSecondaryAction?: () => void;
}

export function ConfirmationDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  contentClassName,
  footerClassName,
  disabled,
  confirmText = "Confirm",
  cancelText = "Cancel",
  singleAction = false,
  requireReason = false,
  reasonLabel = "Reason",
  secondaryActionText,
  onSecondaryAction,
}: ConfirmationDialogProps) {
  const [reason, setReason] = useState("");

  return (
    <AlertDialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) {
          setReason("");
          onClose();
        }
      }}
    >
      <AlertDialogContent className={contentClassName}>
        {singleAction && (
          <AlertDialogCancel asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Close dialog"
              disabled={disabled}
              onClick={() => setReason("")}
              className="absolute right-3 top-3 mt-0 border-0 bg-transparent shadow-none"
            >
              <Icon icon="hugeicons:cancel-01" className="size-5" />
            </Button>
          </AlertDialogCancel>
        )}
        <AlertDialogHeader>
          <AlertDialogTitle className={singleAction ? "pr-8" : undefined}>
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>

        {requireReason && (
          <div className="space-y-2 py-2">
            <Textarea
              label={reasonLabel}
              required
              placeholder="Enter reason..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              autoResize
              minRows={3}
              maxRows={6}
              maxLength={500}
              showCount
              resize="none"
            />
          </div>
        )}

        <AlertDialogFooter className={footerClassName}>
          {!singleAction && (
            <AlertDialogCancel disabled={disabled} onClick={() => setReason("")}>
              {cancelText}
            </AlertDialogCancel>
          )}
          {secondaryActionText && onSecondaryAction && (
            <Button
              type="button"
              variant="destructive"
              disabled={disabled}
              onClick={onSecondaryAction}
            >
              {secondaryActionText}
            </Button>
          )}
          <AlertDialogAction
            className={singleAction ? "w-full" : undefined}
            disabled={disabled || (requireReason && !reason.trim())}
            onClick={() => {
              onConfirm(reason);
              setReason("");
            }}
          >
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
