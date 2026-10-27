import apiRequest from "./api-request";

import {IAccount, IPaginatedResponse, IRequisition, IUser} from "#/_types/api.types";
import {getAllSelectedBranchUUIDs} from "#/_api/helpers";
import {IBaseApprovable} from "#/_types/approvals.types";

export interface ICashbookForm {
  auto_create_ledger_account?: boolean;
  branch?: string | string;
  issue_date: string;
  custodian: string | null;
  account_name: string;
  purpose?: string;
  description?: string;
  cashbook_capacity_amount: string | number;
  charts_of_accounts_reference?: string;
  currency?: string;
  confirm_financial_mapping_change?: boolean;
  reference_code?: string;
  account_balance?: string | number;
}
export interface ICashbook extends IBaseApprovable {
  base_uuid: string;
  id: number;
  created_at: string;
  account_name: string;
  description: string;
  custodian: {id: string; base_uuid: string; fullname: string};
  purpose: string;
  issue_date: string;
  branch: {id: number; branch_name: string; base_uuid?: string};
  is_active: boolean;
  account_balance: string;
  reference_code: string;
  charts_of_accounts_reference?: IAccount | null;
  currency?: {
    id: number;
    name: string;
    code: string;
  } | null;
  custodian_name: string;
  cashbook_capacity_amount: string;
}

export interface ICashbookEntry {
  receipt: number;
  payment: number;
  account: string;
  date: string;
  id: string;
}

export const CASHBOOK_API = {
  fetch: async (query: any = {}) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    Object.keys(query).forEach((key) => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        params.append(key, query[key].toString());
      }
    });

    const response = await apiRequest.get(`accounts/cash-books/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICashbook>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICashbook>;
  },

  create: async ({data}: {data: ICashbookForm}) => {
    const response = await apiRequest.post(`accounts/cash-books/`, data);

    return response.data as ICashbook;
  },

  update: async ({base_uuid, data}: {base_uuid: string; data: Partial<ICashbookForm>}) => {
    const response = await apiRequest.patch(`accounts/cash-books/${base_uuid}/`, data);

    return response.data as ICashbook;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`accounts/cash-books/${base_uuid}/`);

    return response.data;
  },

  fetchOne: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`accounts/cash-books/${base_uuid}/`);

    return response.data as ICashbook;
  },

  // download: async ({base_uuid, filters}: {base_uuid: string; filters: Record<string, string>}) => {
  //   const params = new URLSearchParams(filters);
  //   const response = await apiRequest.get(
  //     `accounts/cash-books/${base_uuid}/download/?${params.toString()}`,
  //   );
  //   return response.data as string;
  // },
};

export interface ICashbookTransactionForm {
  cb_transaction_type: "PAYMENT" | "RECEIPT";
  amount: string;
  cashbook: string;
  requisition_responded_to: string;
  reference_code?: string;
  description?: string;
}

export interface ICashbookTransaction extends IBaseApprovable {
  cb_transaction_type: "PAYMENT" | "RECEIPT";
  amount: string;
  additional_notes: string;
  cashbook: ICashbook;
  id: number;
  base_uuid: string;
  is_active: boolean;
  balance_before: string;
  balance_after: string;
  created_at: string;
  updated_at: string;
  requisition_responded_to: IRequisition;
  description?: string;
  reference_code?: string;
}

export const CASHBOOK_TRANSACTIONS_API = {
  fetch: async (query: {cashbook_base_uuid: string}) => {
    const params = new URLSearchParams({...query});
    const response = await apiRequest.get(`accounts/cash-book-transactions/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICashbookTransaction>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICashbookTransaction>;
  },

  create: async ({data}: {data: ICashbookTransactionForm}) => {
    const response = await apiRequest.post(`accounts/cash-book-payments/`, data);

    return response.data as ICashbookTransaction;
  },

  update: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<ICashbookTransactionForm>;
  }) => {
    const response = await apiRequest.patch(`accounts/cash-book-transactions/${base_uuid}/`, data);

    return response.data as ICashbookTransaction;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`accounts/cash-book-transactions/${base_uuid}/`);

    return response.data;
  },

  fetchOne: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`accounts/cash-book-transactions/${base_uuid}/`);

    return response.data as ICashbookTransaction;
  },
};
