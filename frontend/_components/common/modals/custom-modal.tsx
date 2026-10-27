"use client";

import {useState, useEffect, ReactNode, SetStateAction, Dispatch, useMemo} from "react";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {cn} from "@/lib/utils";

export interface GenericModalProps<T = any> {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (data: T) => void | Promise<void>;
  onValidate?: (data: T) => Record<keyof T, string>;
  title: string;
  description?: string;
  children:
    | ((props: {
        formData: T;
        setFormData: Dispatch<SetStateAction<T>>;
        setField(field: keyof T, value: any): void;
        errors: Record<keyof T, string>;
      }) => ReactNode)
    | ReactNode;
  confirmText?: string;
  cancelText?: string;
  isLoading?: boolean;
  disabled?: boolean;
  initialData?: T;
  contentClassName?: string;
  bodyClassName?: string;
}

export default function GenericModal<T = any>({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  children,
  confirmText = "Add",
  cancelText = "Cancel",
  isLoading = false,
  disabled = false,
  initialData,
  onValidate,
  contentClassName,
  bodyClassName,
}: GenericModalProps<T>) {
  const [formData, setFormData] = useState<T>(initialData || ({} as T));
  const [errors, setErrors] = useState<Record<keyof T, string>>({} as any);
  const [hasSubmitted, setHasSubmitted] = useState(false);

  const isValid = useMemo(
    () => !hasSubmitted || Object.keys(errors).length === 0,
    [errors, hasSubmitted],
  );

  const setField = (field: keyof T, value: any) => {
    setFormData((prev) => ({...prev, [field]: value}));
  };

  useEffect(() => {
    if (onValidate && hasSubmitted) {
      const errs = onValidate(formData);
      setErrors(errs);
    }
  }, [formData, hasSubmitted]);

  //Reinitialize formData whenever modal opens or initialData changes
  useEffect(() => {
    if (isOpen) {
      setFormData(initialData ?? ({} as T));
      setHasSubmitted(false);
      setErrors({} as any);
    }
  }, [isOpen, initialData]);

  const handleConfirm = async () => {
    setHasSubmitted(true);
    if (onValidate) {
      const errs = onValidate(formData);
      setErrors(errs);
      if (Object.keys(errs).length > 0) return;
    }
    try {
      if (formData) {
        await onConfirm(formData);
        onClose();
      }
    } catch (error) {}
  };

  const handleClose = () => {
    setFormData({} as any);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent
        className={cn(
          "w-[90vw] rounded-2xl max-w-[600px] max-h-[90dvh] overflow-y-auto",
          contentClassName,
        )}
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className={cn("space-y-4 max-h-[90dvh] overflow-y-auto p-1", bodyClassName)}>
          {typeof children === "function" ? (
            <div key="dynamic-modal-content">
              {children({formData, setFormData, setField, errors})}
            </div>
          ) : (
            children
          )}
        </div>
        <DialogFooter>
          <Button
            type="button"
            onClick={handleConfirm}
            disabled={disabled || isLoading || !formData || !isValid}
            className="w-full rounded-full h-[48px]"
          >
            {isLoading ? "Processing..." : confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
