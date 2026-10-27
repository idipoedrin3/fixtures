"use client";

import {useCallback} from "react";
import {CASH_ACCOUNTS_API} from "#/_api/approvals.helpers";
import type {ICashAccount} from "#/_types/approvals.types";
import PaginatedSearchableSelect from "./paginated-searchable-select";

interface CashAccountSelectProps {
  value?: ICashAccount | null;
  onChange: (account: ICashAccount | null) => void;
  excludeCashbooks?: boolean;
  disabled?: boolean;
  popoverModal?: boolean;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  description?: string;
  className?: string;
  currencyId?: number;
}

export default function CashAccountSelect({
  value,
  onChange,
  excludeCashbooks = true,
  disabled = false,
  popoverModal = false,
  placeholder = "Select cash account",
  searchPlaceholder = "Search cash accounts...",
  emptyMessage = "No cash accounts found",
  description,
  className,
  currencyId,
}: CashAccountSelectProps) {
  const fetchFirstPage = useCallback(
    (query: {page?: number; search?: string}) =>
      CASH_ACCOUNTS_API.fetchCashAccounts({
        ...query,
        excludeCashbooks,
        currency: currencyId,
      }),
    [excludeCashbooks, currencyId],
  );

  return (
    <PaginatedSearchableSelect<ICashAccount>
      key={`cash-account-${currencyId ?? "all"}`}
      fetchFirstPage={fetchFirstPage}
      fetchFromUrl={CASH_ACCOUNTS_API.fetchCashAccountsFromUrl}
      idKey="base_uuid"
      valueKey="base_uuid"
      labelKey="account_name"
      labelDescKeyFn={(account) =>
        [account.reference_code, account.model.model_name, account.currency?.code]
          .filter(Boolean)
          .join(" • ")
      }
      value={value?.base_uuid ?? null}
      initialData={value ? [value] : []}
      onValueChange={() => {}}
      onItemSelected={onChange}
      disabled={disabled}
      popoverModal={popoverModal}
      placeholder={placeholder}
      searchPlaceholder={searchPlaceholder}
      emptyMessage={emptyMessage}
      description={description}
      className={className}
      refreshOnOpen
    />
  );
}
