"use client";

import {useEffect, useMemo, useState} from "react";
import {useSelector} from "react-redux";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import ExchangeRateInput from "#/_components/custom/exchange-rate-input";
import type {IExchangeRateInput} from "#/_api/services/system.service";
import {useBaisoftPayPayoutConversion} from "#/_hooks/use-baisoftpay-payout-conversion";
import {Icon} from "@iconify/react";
import {Button} from "@/components/ui/button";
import FormattedNumberInput from "#/_components/common/inputs/formatted-number-input";
import {Textarea} from "#/_components/common/inputs/text-area";
import SwitchSetting from "#/_components/common/inputs/switch-setting";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {DIGITAL_WALLET_API} from "#/_api/approvals.helpers";
import {CURRENCIES_API, REQUISITIONS_API} from "#/_api/api.helpers";
import {REQUISITION_BENEFICIARIES_API} from "#/_api/notifications.utils";
import type {Currency, IDigitalWallet} from "#/_types/approvals.types";
import type {IBeneficiaryPaymentMethod, IRequisitionBeneficiary} from "#/_types/types.utils";
import {BAISOFTPAY_TRANSACTION_API} from "#/_api/services/system.service";
import {useToast} from "#/_hooks/use-toast";
import {BaisoftPayPaymentMethodVerification} from "./baisoftpay-payment-method-verification";
import {BaisoftPayPaymentMethodSelect} from "./baisoftpay-payment-method-select";
import PaginatedSearchableSelect from "../custom/paginated-searchable-select";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {formatCurrency} from "#/_lib/utils";
import {BAISOFTPAY_CONFIGURATION_API} from "#/_api/services/baisoftpay-configuration.service";
import {hasPermission} from "#/_api/helpers";
import {PERMISSION_CODES} from "#/_constants/enums";
import {ResponsiveActions} from "./responsive-actions";
import BaisoftPaySettings from "#/(dashboard)/admin/_components/baisoftpay-settings";

type Allocation = {
  id: string;
  beneficiaryId: string;
  accountId: string;
  amount: string;
  description: string;
  beneficiary?: IRequisitionBeneficiary | null;
  paymentMethods?: IBeneficiaryPaymentMethod[];
  selectedPaymentMethod?: IBeneficiaryPaymentMethod | null;
  isLoadingPaymentMethods?: boolean;
  paymentMethodsError?: string;
  toChargeMerchant: boolean;
};

type PayoutOrigin = {
  type: "requisition";
  objectBaseUuid: string;
};

type DocumentCurrency = Pick<Currency, "id" | "code" | "name" | "symbol">;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  contextLabel: string;
  currency?: DocumentCurrency | null;
  sourceCurrencyIsBase?: boolean;
  payoutOrigin: PayoutOrigin;
  totalPayableAmount?: number | null;
};

type RequisitionLineItem = {
  id?: number;
  base_uuid?: string;
  quantity?: number | string;
  unit_price?: number | string;
  gross_amount?: number | string;
  payable_amount?: number | string;
  is_removed?: boolean;
  beneficiary?: IRequisitionBeneficiary | null;
};

function currencyCodesMatch(first?: string, second?: string) {
  return Boolean(first && second && first.trim().toUpperCase() === second.trim().toUpperCase());
}

function createEmptyAllocation(index: number): Allocation {
  return {
    id: `${Date.now()}-${index}`,
    beneficiaryId: "",
    accountId: "",
    amount: "",
    description: "",
    beneficiary: null,
    toChargeMerchant: false,
  };
}

function getLineItemPayableAmount(lineItem: RequisitionLineItem) {
  if (lineItem.payable_amount !== undefined && lineItem.payable_amount !== null) {
    return Number(lineItem.payable_amount);
  }

  if (lineItem.gross_amount !== undefined && lineItem.gross_amount !== null) {
    return Number(lineItem.gross_amount);
  }

  return Number(lineItem.quantity ?? 0) * Number(lineItem.unit_price ?? 0);
}

export function BaisoftPayTransferDialog({
  open,
  onOpenChange,
  contextLabel,
  currency,
  sourceCurrencyIsBase = false,
  payoutOrigin,
  totalPayableAmount,
}: Props) {
  const {toast} = useToast();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [payDifferentCurrency, setPayDifferentCurrency] = useState(false);
  const [paymentCurrency, setPaymentCurrency] = useState<Currency | null>(null);
  const [settlementExchangeRate, setSettlementExchangeRate] = useState<IExchangeRateInput>();
  const [paymentExchangeRate, setPaymentExchangeRate] = useState<IExchangeRateInput>();
  const [fundingSource, setFundingSource] = useState<IDigitalWallet | null>(null);
  const [selectedCurrency, setSelectedCurrency] = useState<Currency | null>(null);
  const [allocations, setAllocations] = useState<Allocation[]>([createEmptyAllocation(0)]);
  const [isReviewing, setIsReviewing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [startWithCreate, setStartWithCreate] = useState(false);
  const [payoutContainer, setPayoutContainer] = useState<HTMLDivElement | null>(null);
  const [settingsContainer, setSettingsContainer] = useState<HTMLDivElement | null>(null);
  const [settingsHeaderActions, setSettingsHeaderActions] = useState<HTMLDivElement | null>(null);
  const [walletRefreshKey, setWalletRefreshKey] = useState(0);
  const canManageConfiguration = hasPermission(PERMISSION_CODES.CAN_VIEW_INSTITUTION_SETTINGS);
  const [configurationStatus, setConfigurationStatus] = useState<
    "loading" | "ready" | "empty" | "error"
  >("loading");

  useEffect(() => {
    if (!open || showSettings) return;
    let cancelled = false;
    setConfigurationStatus("loading");

    if (!canManageConfiguration) {
      setConfigurationStatus(
        currentInstitution?.has_baisoftpay_configuration === true ? "ready" : "empty",
      );
      return;
    }

    void BAISOFTPAY_CONFIGURATION_API.list()
      .then((response) => {
        if (!cancelled) {
          setConfigurationStatus(response.results.length > 0 ? "ready" : "empty");
        }
      })
      .catch(() => {
        if (!cancelled) setConfigurationStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [open, showSettings, walletRefreshKey, canManageConfiguration, currentInstitution]);

  const returnToPayout = () => {
    setStartWithCreate(false);
    setConfigurationStatus("loading");
    setShowSettings(false);
    setFundingSource(null);
    setWalletRefreshKey((value) => value + 1);
  };
  const [initiationDescription, setInitiationDescription] = useState(`Payment for ${contextLabel}`);

  const isRequisitionPayout = payoutOrigin.type === "requisition";
  const requisitionCurrency = currency ?? selectedCurrency;
  const effectiveCurrency =
    isRequisitionPayout && payDifferentCurrency ? paymentCurrency : requisitionCurrency;
  const currencyCode = requisitionCurrency?.code;
  const currenciesDiffer =
    !!effectiveCurrency &&
    !!requisitionCurrency &&
    !currencyCodesMatch(effectiveCurrency.code, requisitionCurrency.code);
  const requisitionMatchesBase =
    sourceCurrencyIsBase ||
    currencyCodesMatch(requisitionCurrency?.code, currentInstitution?.currency?.code);
  const conversion = useBaisoftPayPayoutConversion({
    enabled: open && isRequisitionPayout,
    sourceCurrencyId: requisitionCurrency?.id,
    paymentCurrencyId: effectiveCurrency?.id,
    baseCurrencyId: currentInstitution?.currency?.id,
    sourceCurrencyCode: requisitionCurrency?.code,
    paymentCurrencyCode: effectiveCurrency?.code,
    baseCurrencyCode: currentInstitution?.currency?.code,
    allocations,
    settlementExchangeRate,
    paymentExchangeRate,
  });
  const totalPayout = Object.values(conversion.amounts).reduce(
    (total, amount) => total + Number(amount),
    0,
  );

  useEffect(() => {
    setFundingSource(null);
    setIsReviewing(false);
    setSettlementExchangeRate(undefined);
    setPaymentExchangeRate(undefined);
    setAllocations((current) =>
      current.map((allocation) => ({
        ...allocation,
        selectedPaymentMethod: null,
        accountId: "",
      })),
    );
  }, [effectiveCurrency?.id]);

  const totalAllocated = useMemo(
    () =>
      allocations.reduce((total, allocation) => {
        return total + (Number(allocation.amount) || 0);
      }, 0),
    [allocations],
  );

  const exceedsBalance =
    fundingSource !== null && totalPayout > Number(fundingSource.account_balance);
  const exceedsPayableAmount =
    totalPayableAmount !== undefined &&
    totalPayableAmount !== null &&
    totalAllocated - totalPayableAmount > 0.000001;
  const payableAmountExceededBy =
    totalPayableAmount !== undefined && totalPayableAmount !== null
      ? Math.max(totalAllocated - totalPayableAmount, 0)
      : 0;
  const hasIncompleteAllocation = allocations.some((allocation) => {
    return (
      !allocation.beneficiaryId ||
      !allocation.selectedPaymentMethod ||
      (isRequisitionPayout &&
        allocation.selectedPaymentMethod.currency?.id !== effectiveCurrency?.id) ||
      !Number.isFinite(Number(allocation.amount)) ||
      Number(allocation.amount) <= 0 ||
      allocation.isLoadingPaymentMethods
    );
  });

  const canReview =
    fundingSource !== null &&
    !!effectiveCurrency &&
    (!isRequisitionPayout || conversion.ready) &&
    initiationDescription.trim().length > 0 &&
    totalAllocated > 0 &&
    !hasIncompleteAllocation &&
    !exceedsPayableAmount &&
    !exceedsBalance;

  useEffect(() => {
    if (open) {
      setPayDifferentCurrency(false);
      setPaymentCurrency(null);
      setSettlementExchangeRate(undefined);
      setPaymentExchangeRate(undefined);
      setSelectedCurrency(null);
      setInitiationDescription(`Payment for ${contextLabel}`);
    } else {
      setIsReviewing(false);
      setShowSettings(false);
    }
  }, [contextLabel, currency, open]);

  useEffect(() => {
    if (!open || payoutOrigin.type !== "requisition") return;

    let cancelled = false;

    const loadRequisitionAllocations = async () => {
      try {
        let response = await REQUISITIONS_API.fetchRequisitionLineItems({
          baseUuid: payoutOrigin.objectBaseUuid,
        });
        const lineItems: RequisitionLineItem[] = [...(response.results ?? [])];

        while (response.next) {
          response = await REQUISITIONS_API.fetchRequisitionLineItemsFromUrl({
            url: response.next,
          });
          lineItems.push(...(response.results ?? []));
        }

        if (cancelled) return;

        const allocationsByBeneficiary = new Map<string, Allocation>();

        lineItems
          .filter((lineItem) => !lineItem.is_removed && lineItem.beneficiary)
          .forEach((lineItem) => {
            const beneficiary = lineItem.beneficiary!;
            const existing = allocationsByBeneficiary.get(beneficiary.base_uuid);
            const payableAmount = getLineItemPayableAmount(lineItem);

            if (existing) {
              existing.amount = String(Number(existing.amount) + payableAmount);
              return;
            }

            allocationsByBeneficiary.set(beneficiary.base_uuid, {
              id: beneficiary.base_uuid,
              beneficiaryId: beneficiary.base_uuid,
              beneficiary,
              accountId: "",
              paymentMethods: [],
              selectedPaymentMethod: null,
              isLoadingPaymentMethods: true,
              amount: String(payableAmount),
              description: `Payment for ${contextLabel}`,
              toChargeMerchant: false,
            });
          });

        const seededAllocations = await Promise.all(
          [...allocationsByBeneficiary.values()].map(async (allocation) => {
            try {
              const methods = await REQUISITION_BENEFICIARIES_API.fetchPaymentMethods({
                beneficiaryBaseUuid: allocation.beneficiaryId,
              });
              return {
                ...allocation,
                paymentMethods: methods,
                selectedPaymentMethod: methods[0] ?? null,
                accountId: methods[0]?.base_uuid ?? "",
                isLoadingPaymentMethods: false,
                paymentMethodsError: methods.length === 0 ? "No payment methods configured." : "",
              };
            } catch {
              return {
                ...allocation,
                isLoadingPaymentMethods: false,
                paymentMethodsError: "Unable to load payment methods.",
              };
            }
          }),
        );
        setAllocations(
          seededAllocations.length > 0 ? seededAllocations : [createEmptyAllocation(0)],
        );
      } catch {
        if (!cancelled) setAllocations([createEmptyAllocation(0)]);
      }
    };

    void loadRequisitionAllocations();

    return () => {
      cancelled = true;
    };
  }, [contextLabel, open, payoutOrigin?.objectBaseUuid, payoutOrigin?.type]);

  const updateAllocation = (allocationId: string, changes: Partial<Allocation>) => {
    setAllocations((current) =>
      current.map((allocation) =>
        allocation.id === allocationId ? {...allocation, ...changes} : allocation,
      ),
    );
  };

  const selectRequisitionBeneficiary = async (
    allocationId: string,
    beneficiary: IRequisitionBeneficiary | null,
  ) => {
    updateAllocation(allocationId, {
      beneficiary,
      beneficiaryId: beneficiary?.base_uuid ?? "",
      accountId: "",
      paymentMethods: [],
      selectedPaymentMethod: null,
      isLoadingPaymentMethods: Boolean(beneficiary),
      paymentMethodsError: "",
    });

    if (!beneficiary) return;

    try {
      const methods = await REQUISITION_BENEFICIARIES_API.fetchPaymentMethods({
        beneficiaryBaseUuid: beneficiary.base_uuid,
      });
      updateAllocation(allocationId, {
        paymentMethods: methods,
        selectedPaymentMethod: methods[0] ?? null,
        accountId: methods[0]?.base_uuid ?? "",
        isLoadingPaymentMethods: false,
        paymentMethodsError: methods.length === 0 ? "No payment methods configured." : "",
      });
    } catch {
      updateAllocation(allocationId, {
        isLoadingPaymentMethods: false,
        paymentMethodsError: "Unable to load payment methods.",
      });
    }
  };

  const initiatePayout = async () => {
    if (!isRequisitionPayout || !payoutOrigin || !fundingSource || !canReview) {
      return;
    }

    setIsSubmitting(true);
    try {
      await BAISOFTPAY_TRANSACTION_API.initiate({
        pay_in_different_currency: payDifferentCurrency,
        payment_exchange_rate: conversion.paymentRate ?? null,
        settlement_exchange_rate: conversion.settlementRate ?? null,
        payment_source: "requisition",
        payment_source_base_uuid: payoutOrigin.objectBaseUuid,
        digital_wallet_base_uuid: fundingSource.base_uuid,
        description: initiationDescription.trim(),
        transactions: allocations.map((allocation) => ({
          beneficiary_base_uuid: allocation.beneficiaryId,
          payment_method_base_uuid: allocation.selectedPaymentMethod!.base_uuid,
          amount: conversion.amounts[allocation.id],
          description: allocation.description.trim() || `Payment for ${contextLabel}`,
          to_charge_merchant: allocation.toChargeMerchant,
        })),
      });
      toast({
        title: "Payout initiated",
        description: "The payout was submitted to BaisoftPay.",
      });
      onOpenChange(false);
    } catch (error: any) {
      toast({
        title: "Unable to initiate payout",
        description:
          error.response?.data?.detail ||
          error.response?.data?.error_summary ||
          "The payout could not be submitted.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Dialog open={open && !showSettings} onOpenChange={onOpenChange}>
        <DialogContent
          ref={setPayoutContainer}
          className="flex h-[94vh] !w-[90vw] !max-w-[90vw] flex-col overflow-hidden"
          showCloseButton={false}
          onPointerDownOutside={(event) => event.preventDefault()}
        >
          <DialogHeader className="border-b pb-4 text-left">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1.5">
                <DialogTitle className="text-xl font-semibold tracking-tight">
                  {isReviewing ? "Review" : "Initiate"} BaisoftPay Payout
                </DialogTitle>

                <DialogDescription className="flex flex-wrap items-center gap-2">
                  <span className="truncate">{contextLabel}</span>
                  {currencyCode && (
                    <>
                      <span aria-hidden="true" className="text-border">
                        |
                      </span>
                      <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-foreground">
                        {currencyCode}
                        {totalPayableAmount !== undefined && totalPayableAmount !== null
                          ? ` ${formatCurrency(totalPayableAmount)}`
                          : ""}
                      </span>
                    </>
                  )}
                </DialogDescription>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <ResponsiveActions
                  actions={[
                    {
                      key: "baisoftpay-setup",
                      label: "Configurations & Wallets",
                      icon: "hugeicons:wallet-02",
                      iconImageSrc: "/logo/baisoft-logo.png",
                      prominent: true,
                      visible: canManageConfiguration && configurationStatus === "ready",
                      disabled: isReviewing || isSubmitting,
                      onSelect: () => setShowSettings(true),
                    },
                  ]}
                />
                <DialogClose asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    className="size-8 shrink-0 rounded-full bg-muted p-0"
                    aria-label="Close"
                  >
                    <Icon icon="hugeicons:cancel-01" className="size-5" />
                  </Button>
                </DialogClose>
              </div>
            </div>
          </DialogHeader>

          {configurationStatus !== "ready" ? (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
              {configurationStatus === "loading" ? (
                <p role="status" className="text-sm text-muted-foreground">
                  Checking BaisoftPay setup…
                </p>
              ) : configurationStatus === "error" ? (
                <>
                  <h3 className="text-xl font-semibold">Unable to check BaisoftPay setup</h3>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setConfigurationStatus("loading");
                      setWalletRefreshKey((value) => value + 1);
                    }}
                  >
                    Try Again
                  </Button>
                </>
              ) : (
                <>
                  <h3 className="text-xl font-semibold">Setup BaisoftPay To Start Paying</h3>
                  <p className="max-w-md text-sm text-muted-foreground">
                    {canManageConfiguration
                      ? "Add your BaisoftPay credentials and wallets to get started. Then return here to complete your payout."
                      : "Ask an institution settings administrator to add BaisoftPay credentials and wallets before making a payout."}
                  </p>
                  <ResponsiveActions
                    actions={[
                      {
                        key: "set-up-baisoftpay",
                        label: "Set Up BaisoftPay",
                        icon: "hugeicons:wallet-02",
                        iconImageSrc: "/logo/baisoft-logo.png",
                        prominent: true,
                        visible: canManageConfiguration,
                        onSelect: () => {
                          setStartWithCreate(true);
                        },
                      },
                    ]}
                  />
                </>
              )}
            </div>
          ) : (
            <>
              <div className="min-h-0 flex-1 space-y-6 overflow-y-auto pr-2">
                {isRequisitionPayout && requisitionCurrency && (
                  <SwitchSetting
                    id="baisoftpay-pay-different-currency"
                    label="Pay in a different currency"
                    description={`The requisition is in ${requisitionCurrency.code}. Choose another currency for the payout.`}
                    checked={payDifferentCurrency}
                    disabled={isReviewing}
                    onCheckedChange={(checked) => {
                      setPayDifferentCurrency(checked);
                      setPaymentCurrency(null);
                      setFundingSource(null);
                      setSettlementExchangeRate(undefined);
                      setPaymentExchangeRate(undefined);
                    }}
                  />
                )}

                {isRequisitionPayout && payDifferentCurrency && requisitionCurrency && (
                  <section className="space-y-3">
                    <h3 className="font-semibold">Payment Currency</h3>
                    <PaginatedSearchableSelect<Currency>
                      fetchFirstPage={(query) =>
                        CURRENCIES_API.fetchFirstPage({
                          ...query,
                          is_institution_supported: true,
                        })
                      }
                      fetchFromUrl={CURRENCIES_API.fetchFromUrl}
                      idKey="id"
                      valueKey="id"
                      labelKey="name"
                      labelDescKey="code"
                      value={paymentCurrency?.id ?? null}
                      initialData={paymentCurrency ? [paymentCurrency] : []}
                      excludeIds={[String(requisitionCurrency.id)]}
                      onValueChange={() => {}}
                      onItemSelected={setPaymentCurrency}
                      disabled={isReviewing}
                      placeholder="Select payment currency"
                      searchPlaceholder="Search supported currencies..."
                      emptyMessage="No supported currencies found"
                      popoverModal
                      refreshOnOpen
                    />
                  </section>
                )}

                {isRequisitionPayout &&
                  currenciesDiffer &&
                  requisitionCurrency &&
                  effectiveCurrency &&
                  currentInstitution?.currency &&
                  !requisitionMatchesBase && (
                    <section className="space-y-3">
                      <h3 className="font-semibold">Requisition To Payment Rate</h3>
                      <p className="text-sm text-muted-foreground">
                        Enter allocations in {requisitionCurrency.code}. Each beneficiary will be
                        paid in {effectiveCurrency.code}.
                      </p>
                      <fieldset disabled={isReviewing} className="min-w-0">
                        <ExchangeRateInput
                          key={`${requisitionCurrency.id}-${effectiveCurrency.id}`}
                          transactionCurrency={requisitionCurrency}
                          baseCurrency={effectiveCurrency}
                          value={settlementExchangeRate}
                          onChange={setSettlementExchangeRate}
                          conversionAmount={totalAllocated}
                        />
                      </fieldset>
                    </section>
                  )}

                {isRequisitionPayout &&
                  effectiveCurrency &&
                  currentInstitution?.currency &&
                  !currencyCodesMatch(effectiveCurrency.code, currentInstitution.currency.code) && (
                    <section className="space-y-3">
                      <h3 className="font-semibold">Payment To Base-Currency Rate</h3>
                      <fieldset disabled={isReviewing} className="min-w-0">
                        <ExchangeRateInput
                          key={`${effectiveCurrency.id}-${currentInstitution.currency.id}`}
                          transactionCurrency={effectiveCurrency}
                          baseCurrency={currentInstitution.currency}
                          value={paymentExchangeRate}
                          onChange={setPaymentExchangeRate}
                        />
                      </fieldset>
                    </section>
                  )}

                {!currency && (
                  <section className="space-y-3">
                    <div>
                      <h3 className="font-semibold">Transaction Currency</h3>
                      <p className="text-sm text-muted-foreground">
                        Select one of your organisation’s supported currencies.
                      </p>
                    </div>

                    <PaginatedSearchableSelect<Currency>
                      fetchFirstPage={(query) =>
                        CURRENCIES_API.fetchFirstPage({
                          ...query,
                          is_institution_supported: true,
                        })
                      }
                      fetchFromUrl={CURRENCIES_API.fetchFromUrl}
                      idKey="id"
                      valueKey="id"
                      labelKey="name"
                      labelDescKey="code"
                      value={selectedCurrency?.id ?? null}
                      initialData={selectedCurrency ? [selectedCurrency] : []}
                      onValueChange={() => {}}
                      onItemSelected={setSelectedCurrency}
                      disabled={isReviewing}
                      popoverModal
                      placeholder="Select transaction currency"
                      searchPlaceholder="Search supported currencies..."
                      emptyMessage="No supported currencies found"
                      className="w-full"
                      triggerClassName="w-full"
                      refreshOnOpen
                    />
                  </section>
                )}

                <section className="space-y-3">
                  <div>
                    <h3 className="font-semibold">Funding Source</h3>
                    <p className="text-sm text-muted-foreground">
                      Select the cash account linked to the BaisoftPay wallet being debited.
                    </p>
                  </div>

                  <PaginatedSearchableSelect<IDigitalWallet>
                    key={`${effectiveCurrency?.id ?? "no-currency"}-${walletRefreshKey}`}
                    fetchFirstPage={DIGITAL_WALLET_API.fetchDigitalWallets}
                    fetchFromUrl={DIGITAL_WALLET_API.fetchDigitalWalletsFromUrl}
                    query={effectiveCurrency ? {currency: effectiveCurrency.id} : {}}
                    idKey="base_uuid"
                    valueKey="base_uuid"
                    labelKey="account_name"
                    labelDescKeyFn={(wallet) =>
                      [
                        wallet.platform_name,
                        wallet.wallet_id,
                        `Balance: ${formatCurrency(Number(wallet.account_balance))}`,
                      ]
                        .filter(Boolean)
                        .join(" | ")
                    }
                    value={fundingSource?.base_uuid ?? null}
                    initialData={fundingSource ? [fundingSource] : []}
                    onValueChange={() => {}}
                    onItemSelected={setFundingSource}
                    disabled={isReviewing || !effectiveCurrency}
                    popoverModal
                    placeholder="Select funding digital wallet"
                    searchPlaceholder="Search digital wallets..."
                    emptyMessage="No digital wallets found for the selected currency"
                    className="w-full"
                    triggerClassName="w-full"
                    refreshOnOpen
                  />
                </section>

                <section className="space-y-3">
                  <div>
                    <h3 className="font-semibold">Notes</h3>
                    <p className="text-sm text-muted-foreground">
                      Provide the overall payout description and select who pays the transaction
                      charges.
                    </p>
                  </div>

                  <Textarea
                    id="baisoftpay-initiation-description"
                    required
                    value={initiationDescription}
                    readOnly={isReviewing}
                    placeholder="Enter the purpose of this transaction"
                    minRows={3}
                    maxRows={5}
                    autoResize
                    resize="none"
                    maxLength={255}
                    showCount
                    onChange={(event) => setInitiationDescription(event.target.value)}
                  />
                </section>

                <section className="space-y-4">
                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <h3 className="font-semibold">Beneficiary Allocations</h3>
                      <p className="text-sm text-muted-foreground">
                        Add one or more beneficiaries and select the account each beneficiary will
                        receive through. The selected account determines whether BaisoftPay uses
                        Mobile Money, Bank, or InterWallet.
                      </p>
                    </div>
                  </div>

                  <div className="overflow-x-auto rounded-xl border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12">#</TableHead>
                          <TableHead>Beneficiary</TableHead>
                          <TableHead>Payment Destination</TableHead>
                          <TableHead className="w-40">
                            Amount{currencyCode ? ` (${currencyCode})` : ""}
                          </TableHead>
                          <TableHead>Description</TableHead>
                          {!isReviewing && <TableHead className="w-12" />}
                        </TableRow>
                      </TableHeader>

                      <TableBody>
                        {allocations.map((allocation, index) => (
                          <TableRow key={allocation.id} className="[&>td]:align-top">
                            <TableCell className="pt-4 font-medium text-muted-foreground">
                              {index + 1}
                            </TableCell>

                            <TableCell className="min-w-56">
                              <div className="space-y-2">
                                <div className="min-w-0">
                                  <PaginatedSearchableSelect<IRequisitionBeneficiary>
                                    fetchFirstPage={(query) =>
                                      REQUISITION_BENEFICIARIES_API.fetchRequisitionBeneficiaries({
                                        ...query,
                                        requisitionBaseUuid: payoutOrigin.objectBaseUuid,
                                      })
                                    }
                                    fetchFromUrl={
                                      REQUISITION_BENEFICIARIES_API.fetchRequisitionBeneficiariesFromUrl
                                    }
                                    idKey="base_uuid"
                                    valueKey="base_uuid"
                                    labelKey="name"
                                    labelDescKeyFn={(item) =>
                                      [item.contact_phone_number, item.email]
                                        .filter(Boolean)
                                        .join(" • ")
                                    }
                                    value={allocation.beneficiaryId || null}
                                    initialData={
                                      allocation.beneficiary ? [allocation.beneficiary] : []
                                    }
                                    onValueChange={() => {}}
                                    onItemSelected={(beneficiary) => {
                                      void selectRequisitionBeneficiary(allocation.id, beneficiary);
                                    }}
                                    disabled={isReviewing}
                                    popoverModal
                                    placeholder="Select Beneficiary"
                                    searchPlaceholder="Search Beneficiaries..."
                                    emptyMessage="No Beneficiaries Found"
                                    refreshOnOpen
                                  />
                                </div>
                                {allocation.beneficiary && (
                                  <SwitchSetting
                                    id={`charge-merchant-${allocation.id}`}
                                    label="Charge Wallet"
                                    infoMarkdown={
                                      allocation.toChargeMerchant
                                        ? "Transaction charges will be paid by your organisation’s BaisoftPay wallet."
                                        : "Transaction charges will be deducted from the amount received by this beneficiary."
                                    }
                                    infoPopoverSide="bottom"
                                    infoPopoverWidth="sm"
                                    checked={allocation.toChargeMerchant}
                                    disabled={isReviewing}
                                    onCheckedChange={(checked) =>
                                      updateAllocation(allocation.id, {
                                        toChargeMerchant: checked,
                                      })
                                    }
                                    className="w-fit"
                                    labelClassName="whitespace-nowrap text-xs"
                                  />
                                )}
                              </div>
                            </TableCell>

                            <TableCell className="min-w-72">
                              <BaisoftPayPaymentMethodSelect
                                key={`${allocation.id}-${effectiveCurrency?.id ?? "none"}`}
                                methods={(allocation.paymentMethods ?? []).filter(
                                  (method) => method.currency?.id === effectiveCurrency?.id,
                                )}
                                value={
                                  allocation.selectedPaymentMethod?.currency?.id ===
                                  effectiveCurrency?.id
                                    ? (allocation.selectedPaymentMethod ?? null)
                                    : null
                                }
                                disabled={
                                  isReviewing ||
                                  !effectiveCurrency ||
                                  !allocation.beneficiary ||
                                  allocation.isLoadingPaymentMethods
                                }
                                loading={allocation.isLoadingPaymentMethods}
                                onSearch={(search) =>
                                  REQUISITION_BENEFICIARIES_API.fetchPaymentMethods({
                                    beneficiaryBaseUuid: allocation.beneficiary!.base_uuid,
                                    search,
                                    currencyId: effectiveCurrency?.id,
                                  })
                                }
                                onChange={(selectedPaymentMethod) => {
                                  updateAllocation(allocation.id, {
                                    selectedPaymentMethod,
                                    accountId: selectedPaymentMethod.base_uuid,
                                  });
                                }}
                              />

                              {allocation.paymentMethodsError && (
                                <p className="mt-1 text-xs text-destructive">
                                  {allocation.paymentMethodsError}
                                </p>
                              )}

                              {allocation.selectedPaymentMethod &&
                                allocation.selectedPaymentMethod.currency?.id ===
                                  effectiveCurrency?.id && (
                                  <div className="mt-2">
                                    <BaisoftPayPaymentMethodVerification
                                      paymentMethod={allocation.selectedPaymentMethod}
                                      disabled={isReviewing}
                                    />
                                  </div>
                                )}
                            </TableCell>

                            <TableCell>
                              <FormattedNumberInput
                                min="0"
                                value={allocation.amount}
                                readOnly={isReviewing}
                                onValueChange={(value) =>
                                  updateAllocation(allocation.id, {
                                    amount: value === null ? "" : String(value),
                                  })
                                }
                                placeholder="0"
                              />
                              {isRequisitionPayout && currenciesDiffer && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {conversion.ready
                                    ? `Payout: ${effectiveCurrency?.code} ${formatCurrency(
                                        Number(conversion.amounts[allocation.id] ?? 0),
                                      )}`
                                    : "Awaiting currency conversion"}
                                </p>
                              )}
                            </TableCell>

                            <TableCell className="min-w-64">
                              <Textarea
                                value={allocation.description}
                                readOnly={isReviewing}
                                onChange={(event) =>
                                  updateAllocation(allocation.id, {description: event.target.value})
                                }
                                placeholder={`Payment for ${contextLabel}`}
                                minRows={2}
                                maxRows={4}
                                autoResize
                                resize="none"
                                maxLength={255}
                              />
                            </TableCell>

                            {!isReviewing && (
                              <TableCell>
                                {allocations.length > 1 && (
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    onClick={() =>
                                      setAllocations((current) =>
                                        current.filter((item) => item.id !== allocation.id),
                                      )
                                    }
                                    aria-label={`Remove allocation ${index + 1}`}
                                  >
                                    <Icon
                                      icon="hugeicons:delete-02"
                                      className="size-4 text-destructive"
                                    />
                                  </Button>
                                )}
                              </TableCell>
                            )}
                          </TableRow>
                        ))}
                        {!isReviewing && (
                          <TableRow>
                            <TableCell colSpan={6}>
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() =>
                                  setAllocations((current) => [
                                    ...current,
                                    createEmptyAllocation(current.length),
                                  ])
                                }
                              >
                                <Icon icon="hugeicons:user-add-01" className="mr-2 size-4" />
                                Add Beneficiary
                              </Button>
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>

                  {isRequisitionPayout && (
                    <div className="space-y-2 rounded-lg border p-3 text-sm">
                      <p>
                        Requisition allocation: {currencyCode} {formatCurrency(totalAllocated)}
                      </p>
                      <p>
                        Total payout: {effectiveCurrency?.code ?? "Select a currency"}{" "}
                        {conversion.ready ? formatCurrency(totalPayout) : "—"}
                      </p>
                      {conversion.error && <p className="text-destructive">{conversion.error}</p>}
                      {exceedsBalance && (
                        <p className="text-destructive">
                          The converted payout exceeds the selected wallet balance.
                        </p>
                      )}
                    </div>
                  )}

                  {exceedsPayableAmount && (
                    <div className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                      <Icon icon="hugeicons:alert-02" className="mt-0.5 size-4 shrink-0" />
                      <p>
                        Allocations cannot exceed the total payable amount of{" "}
                        {currencyCode ? `${currencyCode} ` : ""}
                        {formatCurrency(totalPayableAmount ?? 0)}. You allocated{" "}
                        {currencyCode ? `${currencyCode} ` : ""}
                        {formatCurrency(totalAllocated)}, which is{" "}
                        {currencyCode ? `${currencyCode} ` : ""}
                        {formatCurrency(payableAmountExceededBy)} over the limit.
                      </p>
                    </div>
                  )}
                </section>
              </div>

              <div className="flex gap-2 border-t pt-4">
                <div className="flex w-full gap-2">
                  {isReviewing ? (
                    <>
                      <Button
                        type="button"
                        variant="outline"
                        className="h-12 w-1/2"
                        onClick={() => setIsReviewing(false)}
                      >
                        Back
                      </Button>
                      <Button
                        type="button"
                        className="h-12 w-1/2"
                        disabled={!isRequisitionPayout || isSubmitting || !canReview}
                        onClick={initiatePayout}
                      >
                        {isSubmitting && (
                          <Icon icon="hugeicons:loading-03" className="size-4 animate-spin" />
                        )}
                        Initiate Payout
                      </Button>
                    </>
                  ) : (
                    <Button
                      type="button"
                      className="h-12 w-full"
                      disabled={!canReview}
                      onClick={() => setIsReviewing(true)}
                    >
                      Review Disbursement
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
          {open && startWithCreate && canManageConfiguration && (
            <BaisoftPaySettings
              portalContainer={payoutContainer}
              initialCreate
              hideHeader
              setupOnly
              onSetupClose={returnToPayout}
            />
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={open && showSettings}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) returnToPayout();
        }}
      >
        <DialogContent
          ref={setSettingsContainer}
          showCloseButton={false}
          className="flex h-[94vh] !w-[90vw] !max-w-[90vw] flex-col overflow-hidden"
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
        >
          <DialogHeader className="shrink-0  pb-4 text-left">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0 space-y-1.5">
                <DialogTitle>BaisoftPay Configurations & Wallets</DialogTitle>
                <DialogDescription>
                  Set up credentials, add wallets, or manage existing configurations.
                </DialogDescription>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div ref={setSettingsHeaderActions} />
                <DialogClose asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    className="size-8 shrink-0 rounded-full bg-muted p-0"
                    aria-label="Close"
                  >
                    <Icon icon="hugeicons:cancel-01" className="size-5" />
                  </Button>
                </DialogClose>
              </div>
            </div>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {open && showSettings && canManageConfiguration && (
              <BaisoftPaySettings
                portalContainer={settingsContainer}
                headerActionsContainer={settingsHeaderActions}
                hideHeader
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
