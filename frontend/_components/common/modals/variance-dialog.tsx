import {Icon} from "@iconify/react";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {useEffect, useState} from "react";

type VarianceItem = {
  item_name: string;
  quantity_pending: number;
  quantity_to_issue: number;
};

type Props = {
  open: boolean;
  isSubmitting?: boolean;
  variances: VarianceItem[];
  onConfirm: (createBackOrder: boolean) => void;
  onCancel: () => void;
};

export default function VarianceDialog({
  open,
  isSubmitting,
  variances,
  onConfirm,
  onCancel,
}: Props) {
  const [confirmingBackOrder, setConfirmingBackOrder] = useState<boolean | null>(null);

  const handleConfirm = (createBackOrder: boolean) => {
    setConfirmingBackOrder(createBackOrder);
    onConfirm(createBackOrder);
  };

  useEffect(() => {
    if (!open) setConfirmingBackOrder(null);
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onCancel}>
      <DialogContent className="w-[90vw] rounded-2xl max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-100">
              <Icon icon="hugeicons:alert-02" className="h-4 w-4 text-amber-600" />
            </span>
            Quantity variance detected
          </DialogTitle>
          <DialogDescription>
            The quantity being processed does not match the remaining quantity.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 space-y-3 text-sm">
          <p className="font-medium text-gray-700">The following items have a quantity variance:</p>
          <div className="space-y-2">
            {variances.map((v, i) => (
              <div key={i} className="flex items-center justify-between text-gray-600">
                <span className="font-medium text-gray-800">{v.item_name}</span>
                <span>
                  Issuing <span className="font-semibold text-gray-900">{v.quantity_to_issue}</span>
                  {" of "}
                  <span className="font-semibold text-gray-900">{v.quantity_pending}</span>{" "}
                  remaining
                </span>
              </div>
            ))}
          </div>
          <div className="border-t border-gray-200 pt-3 space-y-1 text-gray-500">
            <p className="flex items-start gap-2">
              <span className="font-semibold text-gray-700 shrink-0">Yes →</span>A back-order will
              be created for the remaining quantity.
            </p>
            <p className="flex items-start gap-2">
              <span className="font-semibold text-gray-700 shrink-0">No →</span>
              No back-order will be created, and the remaining quantity will be ignored.
            </p>
          </div>
        </div>

        <DialogFooter className="flex gap-3 sm:gap-3">
          <Button
            variant="outline"
            className="flex-1 rounded-full h-12"
            onClick={() => handleConfirm(false)}
            disabled={isSubmitting}
          >
            {isSubmitting && confirmingBackOrder === false && (
              <Icon icon="svg-spinners:180-ring" className="w-4 h-4 mr-2" />
            )}
            No
          </Button>
          <Button
            className="flex-1 rounded-full h-12"
            onClick={() => handleConfirm(true)}
            disabled={isSubmitting}
          >
            {isSubmitting && confirmingBackOrder === true && (
              <Icon icon="svg-spinners:180-ring" className="w-4 h-4 mr-2" />
            )}
            Yes, create back-order
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
