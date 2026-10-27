"use client";

import {useState} from "react";

import {Input} from "@/components/ui/input";
import GenericModal from "#/_components/common/modals/custom-modal";
import {showErrorToast} from "#/_lib/utils";

interface RedeemCommissionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  salespersonName: string;
  availableBalance: number;
  onRedeem: (amount: number) => Promise<void> | void;
}

export function RedeemCommissionDialog({
  isOpen,
  onClose,
  salespersonName,
  availableBalance,
  onRedeem,
}: RedeemCommissionDialogProps) {
  const [isLoading, setIsLoading] = useState(false);

  const initialFormData = {amount: 0};

  const handleConfirm = async (data: {amount: number}) => {
    if (!data.amount || data.amount <= 0) {
      showErrorToast({defaultMessage: "Please enter a valid amount"});

      return;
    }

    if (data.amount > availableBalance) {
      showErrorToast({
        defaultMessage: `Amount cannot exceed available balance (${availableBalance})`,
      });

      return;
    }

    setIsLoading(true);
    try {
      await onRedeem(data.amount);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <GenericModal<{amount: number}>
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={handleConfirm}
      title={`Redeem Commission for ${salespersonName}`}
      confirmText="Redeem"
      isLoading={isLoading}
      initialData={initialFormData}
    >
      {({formData, setFormData}) => (
        <div className="space-y-4">
          <div>
            <label className="block mb-1 font-medium">Amount to Redeem</label>
            <Input
              type="number"
              value={formData?.amount || 0}
              min={0}
              max={availableBalance}
              onChange={(e) => setFormData({...formData!, amount: Number(e.target.value)})}
              placeholder={`Max: ${availableBalance}`}
            />
            <p className="text-xs text-gray-500 mt-1">Available balance: {availableBalance}</p>
          </div>
        </div>
      )}
    </GenericModal>
  );
}
