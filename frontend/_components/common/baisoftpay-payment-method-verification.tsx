"use client";

import {useEffect, useState} from "react";
import {CheckCircle2, Loader2} from "lucide-react";
import {Button} from "@/components/ui/button";
import {
  ACCOUNT_VERIFICATION_API,
  IAccountVerificationResponse,
} from "#/_api/services/system.service";
import type {IBeneficiaryPaymentMethod} from "#/_types/types.utils";

export function BaisoftPayPaymentMethodVerification({
  paymentMethod,
  disabled = false,
}: {
  paymentMethod: IBeneficiaryPaymentMethod;
  disabled?: boolean;
}) {
  const [isVerifying, setIsVerifying] = useState(false);
  const [verification, setVerification] =
    useState<IAccountVerificationResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setVerification(null);
    setError("");
  }, [paymentMethod.base_uuid]);

  if (paymentMethod.method_type === "digital_wallet") {
    return (
      <p className="text-xs text-muted-foreground">
        Digital wallet verification is handled during payout.
      </p>
    );
  }

  const verify = async () => {
    if (!paymentMethod.operator_country_code) return;

    setIsVerifying(true);
    setVerification(null);
    setError("");

    try {
      const result =
        paymentMethod.method_type === "mobile_money"
          ? await ACCOUNT_VERIFICATION_API.verifyMobileMoney({
              account_number: paymentMethod.identifier,
              account_type: "mobile_money",
              country_code: paymentMethod.operator_country_code,
            })
          : await ACCOUNT_VERIFICATION_API.verifyAccount({
              account_number: paymentMethod.identifier,
              account_type: "bank",
              country_code: paymentMethod.operator_country_code,
              operator_code: paymentMethod.operator_code || "",
            });
      setVerification(result);
    } catch {
      setError("Unable to verify this payment method.");
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 w-full"
        disabled={
          disabled ||
          isVerifying ||
          !paymentMethod.operator_country_code ||
          (paymentMethod.method_type === "bank" && !paymentMethod.operator_code)
        }
        onClick={verify}
      >
        {isVerifying && <Loader2 className="size-3.5 animate-spin" />}
        {isVerifying ? "Verifying..." : "Verify destination"}
      </Button>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {verification && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-2 text-xs text-green-700">
          <p className="flex items-center gap-1 font-medium">
            <CheckCircle2 className="size-3.5" />
            Verified
          </p>
          {verification.data?.account_name && (
            <p className="mt-1 text-green-800">
              {verification.data.account_name}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
