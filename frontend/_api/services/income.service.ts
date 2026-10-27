import {defineEndpoint} from "./_base";

import {IAccount, ITax} from "#/_types/api.types";
import {IInstitutionSupportedCurrency} from "#/_types/email";
import {IJournalEntriesData} from "#/_components/common/tables/journal-entries-table";
import apiRequest from "../api-request";
import {toFileEntry} from "#/_lib/file-utils";
import {toParams} from "#/_lib/utils";
import type {IExchangeRateInput, IExchangeRateRepresentation} from "#/_api/services/system.service";

export interface IOtherIncome {
  id: number;
  base_uuid: string;
  model_content_type_id?: number;
  reference_code: string;
  approval_status: "approved" | "rejected" | "pending" | "under_creation" | "active";
  is_other_income_recurring: boolean;
  recurring_frequency?: string;
  transaction_date: string;
  amount: string;
  tax_amount: string;
  net_amount: string;
  description?: string;
  is_project_based: boolean;
  can_be_automated: boolean;
  start_date?: string;
  end_date?: string;
  next_recurring_date?: string;
  additional_document?: string | null;
  object_uuid?: string;
  content_type?: number;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  external_base_uuid?: string | null;
  original_data?: any;
  category: {
    category_name: string;
    base_uuid: string;
    reference_code: string;
  };
  financial_account: {
    base_uuid: string;
    reference_code: string;
    account_name: string;
    account_balance: string;
    currency: any | null;
    description: string;
    model: {id: number; model_name: string};
    bank_name: string;
  };
  branch?: any | null;
  currency?: any | null;
  exchange_rate?: IExchangeRateRepresentation | null;
  exchange_rate_status?: "base_currency" | "document_snapshot" | "missing";
  project?: any | null;
  created_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  };
  updated_by?: any | null;
  general_journal_items?: IJournalEntriesData;
  approvals?: any[];
}

export interface IOtherIncomeForm {
  cash_account: {
    content_type: number;
    content_object_uuid: string;
  };
  description?: string;
  external_base_uuid?: string;
  is_other_income_recurring: boolean;
  recurring_frequency?: "DAILY" | "WEEKLY" | "MONTHLY" | "QUARTERLY" | "ANNUALLY";
  transaction_date: string;
  object_uuid?: string;
  amount: string;
  is_project_based?: boolean;
  can_be_automated?: boolean;
  start_date?: string;
  end_date?: string;
  additional_document?: File | string;
  category: number | string;
  branch?: number;
  content_type?: number;
  project?: number;
  currency: number | string;
  exchange_rate?: IExchangeRateInput;
  reference_code?: string;
  recieved_from?: string;
  financial_account?: string;
}

export const buildOtherIncomePayload = async (input: {
  attachments: {name: string; document: File}[];
  formData: IOtherIncomeForm;
  referenceCode?: string;
  cashAccount?: {content_type: number; content_object_uuid: string};
}) => {
  const {attachments, formData, referenceCode, cashAccount} = input;

  const convertedAttachments =
    attachments.length > 0
      ? await Promise.all(
          attachments.map(async ({name, document}) => ({
            name,
            document: await toFileEntry(document),
          })),
        )
      : undefined;

  return {
    category: formData.category,
    amount: formData.amount,
    is_other_income_recurring: formData.is_other_income_recurring,
    ...(referenceCode && {reference_code: referenceCode}),
    ...(formData.description && {description: formData.description}),
    ...(formData.recieved_from && {recieved_from: formData.recieved_from}),
    ...(formData.branch && {branch: formData.branch}),
    ...(formData.currency && {currency: formData.currency}),
    ...(formData.exchange_rate && {exchange_rate: formData.exchange_rate}),
    ...(formData.is_project_based &&
      formData.project && {
        is_project_based: true,
        project: formData.project,
      }),
    ...(formData.is_other_income_recurring && formData.recurring_frequency
      ? {
          recurring_frequency: formData.recurring_frequency,
          ...(formData.can_be_automated && {can_be_automated: formData.can_be_automated}),
        }
      : {transaction_date: formData.transaction_date}),
    ...(cashAccount && {cash_account: cashAccount}),
    ...(formData.is_other_income_recurring && formData.recurring_frequency
      ? {
          recurring_frequency: formData.recurring_frequency,
          ...(formData.can_be_automated && {can_be_automated: formData.can_be_automated}),
          ...(formData.start_date && {start_date: formData.start_date}),
          ...(formData.end_date && {end_date: formData.end_date}),
        }
      : {transaction_date: formData.transaction_date}),
    ...(convertedAttachments && {additional_attachments: convertedAttachments}),
  };
};

export const OTHER_INCOME_API = {
  ...defineEndpoint<IOtherIncome, IOtherIncomeForm>("accounts/other-incomes/"),

  createOtherIncome: async (payload: Record<string, any>) => {
    const response = await apiRequest.post("accounts/other-incomes/", payload);
    return response.data as IOtherIncome;
  },
};

export interface IOtherIncomeStatistics {
  summary: {
    total_entries: number;
    gross_amount: string;
    total_tax: string;
    net_amount: string;
    currency_code: string;
  };
  other_income_intelligence: {
    recurring: number;
    one_time: number;
    received: number;
    pending: number;
    cancelled: number;
    recurring_setups: number;
  };
  top_categories: Array<{
    category_base_uuid: string;
    category_name: string;
    total_entries: number;
    gross_amount: string;
    total_tax: string;
    net_amount: string;
  }>;
}

export const OTHER_INCOME_STATISTICS_API = {
  fetchStatistics: async (params?: Record<string, any>) => {
    const query = toParams(params ?? {});
    const response = await apiRequest.get(
      `accounts/other-incomes/statistics/income-intelligence/?${query.toString()}`,
    );
    return response.data as IOtherIncomeStatistics;
  },
};

export interface IOtherIncomeCategoryForm {
  category_name: string;
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  category_taxes: {tax: string}[];
  credit_account?: string | null;
  allows_recurrence?: boolean;
  //category_taxes: {tax: number; is_inclusive: boolean; [key: string]: any}[];
}

export interface IOtherIncomeCategory {
  reference_code: string;
  id: string;
  base_uuid?: string;
  category_name: string;
  description?: string;
  category_description?: string;
  is_active: boolean;
  approval_status?: "under_creation" | "pending" | "approved" | "rejected" | "active";
  approvals?: string;
  credit_account?: IAccount | null;
  created_at?: string;
  updated_at?: string;
  created_by?: {
    base_uuid: string;
    fullname: string;
  };
  updated_by?: {
    base_uuid: string;
    fullname: string;
  };
  category_taxes: {
    id: number;
    tax_name: string;
    base_uuid: string;
    reference_code: string;
    is_inclusive?: boolean;
  }[];
}

export const OTHER_INCOME_CATEGORY_API = defineEndpoint<
  IOtherIncomeCategory,
  IOtherIncomeCategoryForm
>("accounts/other-income-categories/");

export interface IOtherIncomeRecurring {
  id: number;
  base_uuid: string;
  external_base_uuid?: string;
  model_content_type_id?: number;
  reference_code?: string;
  is_deleted: boolean;
  deleted_at?: string;
  is_active: boolean;
  approval_status:
    | "under_creation"
    | "under_update"
    | "under_deletion"
    | "pending"
    | "approved"
    | "rejected"
    | "active";
  amount: string;
  settlement_amount: string;
  tax_amount?: string;
  net_amount?: string;
  received_from?: string;
  received_date?: string;
  description?: string;
  additional_document?: string | null;
  created_at: string;
  updated_at?: string;
  created_by: {
    fullname: string;
  };
  updated_by?: number | null;
  other_income: number;
  currency?: IInstitutionSupportedCurrency | null;
  settlement_currency?: {
    id: number;
    code: string;
    name: string;
    symbol: string;
  } | null;
  payment_exchange_rate?: IExchangeRateRepresentation | null;
  payment_exchange_rate_status?: "base_currency" | "document_snapshot" | "missing";
  settlement_exchange_rate?: IExchangeRateRepresentation | null;
  category?: {id: number; category_name: string};
  approvals?: any[];
  general_journal_items?: IJournalEntriesData;
  financial_account?: IOtherIncome["financial_account"] | null;
  content_type?: number | null;
  object_uuid?: string | null;
  are_initial_journal_entries_made?: boolean;
}

export interface IOtherIncomeRecurringForm {
  other_income: number;
  amount: string;
  received_from?: string;
  received_date?: string;
  description?: string;
  additional_document?: File | string;
  currency: string;
  payment_exchange_rate?: IExchangeRateInput;
  settlement_exchange_rate?: IExchangeRateInput;
  cash_account: {
    content_type: number;
    content_object_uuid: string;
  };
  external_base_uuid?: string;
}

export const OTHER_INCOME_RECURRING_API = {
  ...defineEndpoint<IOtherIncomeRecurring, IOtherIncomeRecurringForm>(
    "accounts/recurring-other-income-records/",
  ),

  createRecord: async (payload: IOtherIncomeRecurringForm) => {
    const response = await apiRequest.post("accounts/recurring-other-income-records/", payload);
    return response.data as IOtherIncomeRecurring;
  },
};
