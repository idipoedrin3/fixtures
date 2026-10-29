"use client";

import {useEffect, useMemo, useState} from "react";
import GenericModal from "../../../_components/common/modals/custom-modal";
import FormattedDatePicker from "#/_components/common/inputs/formatted-date-picker";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import PaginatedSearchableSelect from "../../../_components/custom/paginated-searchable-select";
import ExchangeRateInput from "#/_components/custom/exchange-rate-input";
import SwitchSetting from "#/_components/common/inputs/switch-setting";
import ReferenceCodeInput from "#/_components/custom/reference-code-input";
import {Label} from "@/components/ui/label";
import {Textarea} from "@/components/ui/textarea";
import {
  Currency,
  IAccount,
  ICustomerPaymentRecordFormData,
  IPaginatedResponse,
} from "#/_types/api.types";
import {IExchangeRateInput} from "#/_api/services/system.service";
import {CURRENCIES_API} from "#/_api/api.helpers";

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (data: ICustomerPaymentRecordFormData) => void | Promise<void>;
  isLoading?: boolean;
  invoice?: {
    base_uuid?: string;
    amount_due?: string;
    currency?: Currency;
  };
  institutionCurrency?: Currency;
  fetchAccounts: (args: {
    search?: string;
    system_group_account_type_choice?: string[];
    linked_to_cash_account?: boolean;
    currency?: number;
    exclude_currency?: number;
  }) => Promise<IPaginatedResponse<IAccount>>;
  fetchAccountsFromUrl: (args: {url: string}) => Promise<IPaginatedResponse<IAccount>>;
}

export default function PaymentModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading = false,
  invoice,
  institutionCurrency,
  fetchAccounts,
  fetchAccountsFromUrl,
}: PaymentModalProps) {
  const [receiveDifferentCurrency, setReceiveDifferentCurrency] = useState(false);
  const [selectedReceivingCurrency, setSelectedReceivingCurrency] = useState<Currency | null>(null);
  const [selectedAccount, setSelectedAccount] = useState<IAccount | null>(null);
  const [settlementRate, setSettlementRate] = useState<IExchangeRateInput>();
  const [paymentRate, setPaymentRate] = useState<IExchangeRateInput>();

  useEffect(() => {
    if (!isOpen) return;
    setReceiveDifferentCurrency(false);
    setSelectedReceivingCurrency(null);
    setSelectedAccount(null);
    setSettlementRate(undefined);
    setPaymentRate(undefined);
  }, [isOpen]);

  const paymentCurrency = receiveDifferentCurrency ? selectedReceivingCurrency : invoice?.currency;

  const initialData = useMemo<ICustomerPaymentRecordFormData>(
    () => ({
      invoice: invoice?.base_uuid ?? null,
      amount: invoice?.amount_due ?? "0",
      payment_date: new Date().toISOString().split("T")[0],
      coa_cash_account: null,
      description: "",
    }),
    [invoice?.base_uuid, invoice?.amount_due],
  );

  return (
    <GenericModal<ICustomerPaymentRecordFormData>
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Receive Payment"
      description="Enter payment details for this invoice"
      confirmText="Submit Payment"
      contentClassName="max-w-[1500px] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      bodyClassName="[scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      isLoading={isLoading}
      onValidate={(data) => {
        const errors = {} as Record<keyof ICustomerPaymentRecordFormData, string>;

        if (!data.amount || Number(data.amount) <= 0) {
          errors.amount = "Amount must be greater than zero";
        }
        if (!data.payment_date) {
          errors.payment_date = "Payment date is required";
        }
        if (!data.coa_cash_account || !selectedAccount) {
          errors.coa_cash_account = "Deposit to account is required";
        }

        return errors;
      }}
      disabled={receiveDifferentCurrency && !selectedReceivingCurrency}
      initialData={initialData}
    >
      {({formData, setFormData, errors}) => (
        <div className="space-y-6">
          <div className="rounded-xl border bg-muted/20 p-4">
            <SwitchSetting
              id="receive-in-different-currency"
              label="Receive in a different currency"
              description={`The invoice remains in ${
                invoice?.currency?.code ?? "its original currency"
              }. Enable this when the receiving account uses another currency.`}
              checked={receiveDifferentCurrency}
              onCheckedChange={(checked) => {
                setReceiveDifferentCurrency(checked);
                setSelectedReceivingCurrency(null);
                setSelectedAccount(null);
                setSettlementRate(undefined);
                setPaymentRate(undefined);
                setFormData({
                  ...formData!,
                  amount: checked ? "" : (invoice?.amount_due ?? "0"),
                  coa_cash_account: null,
                  settlement_exchange_rate: null,
                });
              }}
              className="border-0 bg-transparent p-0"
            />
          </div>

          <div className="grid items-start gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <FormattedDatePicker
                id="payment_date"
                label="Payment Date"
                showAsterisk
                limitMaxWidth={false}
                inputClassName="w-full bg-card border-border/50 h-10"
                value={formData.payment_date}
                onChange={(value) => setFormData({...formData, payment_date: value || ""})}
              />
              {errors.payment_date && (
                <p className="text-sm text-destructive">{errors.payment_date}</p>
              )}
            </div>

            <ReferenceCodeInput
              label="Reference"
              prefix="CR"
              value={formData.reference_code ?? ""}
              onChange={(value) => setFormData({...formData, reference_code: value})}
            />
          </div>

          {receiveDifferentCurrency && (
            <div className="space-y-2">
              <Label required>Receiving Currency</Label>
              <PaginatedSearchableSelect<Currency>
                id="receiving_currency"
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
                value={selectedReceivingCurrency?.id ?? null}
                excludeIds={invoice?.currency?.id ? [String(invoice.currency.id)] : []}
                onValueChange={() => {}}
                onItemSelected={(currency) => {
                  setSelectedReceivingCurrency(currency);
                  setSelectedAccount(null);
                  setSettlementRate(undefined);
                  setPaymentRate(undefined);
                  setFormData({
                    ...formData!,
                    amount: "",
                    coa_cash_account: null,
                    settlement_exchange_rate: null,
                  });
                }}
                placeholder="Select receiving currency"
                searchPlaceholder="Search supported currencies..."
                emptyMessage="No other supported currencies found"
              />
              {!selectedReceivingCurrency && (
                <p className="text-xs text-muted-foreground">
                  Select a currency before choosing the receiving account.
                </p>
              )}
            </div>
          )}

          {receiveDifferentCurrency &&
            invoice?.currency &&
            paymentCurrency &&
            paymentCurrency.id !== invoice.currency.id && (
              <ExchangeRateInput
                transactionCurrency={invoice.currency}
                baseCurrency={paymentCurrency}
                value={settlementRate}
                onChange={(rate) => {
                  setSettlementRate(rate);
                  setFormData({
                    ...formData!,
                    settlement_exchange_rate: rate ?? null,
                  });
                }}
                conversionAmount={invoice.amount_due}
                onConvertedAmount={(amount) => setFormData({...formData, amount})}
              />
            )}

          {paymentCurrency &&
            institutionCurrency &&
            paymentCurrency.id !== institutionCurrency.id && (
              <div className="space-y-2">
                <div>
                  <p className="text-sm font-medium">Base Currency Rate</p>
                  <p className="text-xs text-muted-foreground">
                    This receipt is recorded in {paymentCurrency.code}. The configured rate to{" "}
                    {institutionCurrency.code} will be used unless you provide a custom rate.
                  </p>
                </div>
                <ExchangeRateInput
                  transactionCurrency={paymentCurrency}
                  baseCurrency={institutionCurrency}
                  value={paymentRate}
                  onChange={(rate) => {
                    setPaymentRate(rate);
                    setFormData({
                      ...formData,
                      payment_exchange_rate: rate ?? null,
                    });
                  }}
                />
              </div>
            )}

          <div className="grid items-start gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label required>
                Amount Received{paymentCurrency ? ` (${paymentCurrency.code})` : ""}
              </Label>
              <FormattedNumberInput
                value={formData.amount ? Number(formData.amount) : 0}
                onValueChange={(value) =>
                  setFormData({...formData, amount: value?.toString() ?? ""})
                }
                min={0}
                placeholder="0.00"
                description="The outstanding invoice amount is filled automatically."
              />
              {errors.amount && <p className="text-sm text-destructive">{errors.amount}</p>}
            </div>

            <div className="space-y-2">
              <Label required>Deposit To Account</Label>
              <PaginatedSearchableSelect<IAccount>
                key={`cash-account-${paymentCurrency?.id ?? "none"}`}
                id="cash_account"
                idKey="base_uuid"
                valueKey="base_uuid"
                labelKey="account_name"
                labelDescKey="reference_code"
                placeholder="Select an account to deposit to"
                searchPlaceholder="Search accounts..."
                emptyMessage="No accounts found"
                fetchFirstPage={({search}) =>
                  paymentCurrency
                    ? fetchAccounts({
                        search,
                        system_group_account_type_choice: ["asset"],
                        linked_to_cash_account: true,
                        currency: paymentCurrency.id,
                      })
                    : Promise.resolve({
                        count: 0,
                        next: null,
                        previous: null,
                        results: [],
                      })
                }
                fetchFromUrl={fetchAccountsFromUrl}
                onValueChange={(values) => {
                  setFormData({
                    ...formData,
                    coa_cash_account: values[0] ? String(values[0]) : null,
                  });
                }}
                onItemSelected={setSelectedAccount}
                initialData={[]}
                value={formData.coa_cash_account}
                disabled={!paymentCurrency}
                refreshOnOpen
                description="Only cash and bank accounts in the receiving currency are shown."
              />
              {errors.coa_cash_account && (
                <p className="text-sm text-destructive">{errors.coa_cash_account}</p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes" showOptional>
              Notes
            </Label>
            <Textarea
              id="notes"
              value={formData?.description || ""}
              onChange={(e) =>
                setFormData({
                  ...formData!,
                  description: e.target.value,
                })
              }
              placeholder="Enter any additional notes..."
              rows={4}
              description="Optional context or remarks for this receipt."
            />
          </div>
        </div>
      )}
    </GenericModal>
  );
}
