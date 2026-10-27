import {defineEndpoint} from "./_base";

import {IIndustry, IPaginatedResponse} from "#/_types/api.types";
import apiRequest from "../api-request";
import {toParams} from "#/_lib/utils";

export interface IMobileMoneyVerificationPayload {
  account_number: string;
  account_type: "mobile_money";
  country_code: string;
}

export interface IAccountVerificationPayload {
  account_number: string;
  account_type: "bank" | "digital_wallet";
  country_code: string;
  operator_code: string;
}

export interface IAccountVerificationOperator {
  code: string;
  symbol_url?: string;
  name: string;
}

export interface IVerifiedMobileMoneyAccount {
  account_name?: string;
  account_number?: string;
  country?: string;
  currency?: string;
}

export interface IAccountVerificationResponse {
  success?: boolean;
  data?: IVerifiedMobileMoneyAccount;
  [key: string]: unknown;
}

export const ACCOUNT_VERIFICATION_API = {
  verifyMobileMoney: async (payload: IMobileMoneyVerificationPayload) => {
    const response = await apiRequest.post("system/accounts/verify/", payload);

    return response.data as IAccountVerificationResponse;
  },
  getOperators: async ({
    accountType,
    countryCode,
  }: {
    accountType: "bank" | "digital_wallet";
    countryCode: string;
  }) => {
    const params = new URLSearchParams({
      account_type: accountType,
      country_code: countryCode,
    });
    const response = await apiRequest.get(`system/accounts/verify/operators/?${params.toString()}`);

    return response.data as {results: IAccountVerificationOperator[]};
  },
  verifyAccount: async (payload: IAccountVerificationPayload) => {
    const response = await apiRequest.post("system/accounts/verify/", payload);

    return response.data as IAccountVerificationResponse;
  },
};

export interface IBaisoftPayTransactionTarget {
  beneficiary_base_uuid: string;
  payment_method_base_uuid: string;
  amount: string;
  description: string;
  to_charge_merchant?: boolean;
}

export interface IBaisoftPayTransactionInitiationPayload {
  pay_in_different_currency?: boolean;
  payment_exchange_rate?: IExchangeRateInput | null;
  settlement_exchange_rate?: IExchangeRateInput | null;
  payment_source: "requisition";
  payment_source_base_uuid: string;
  digital_wallet_base_uuid: string;
  description: string;
  transactions: IBaisoftPayTransactionTarget[];
}

export interface IBaisoftPayTransactionInitiationResponse {
  success: boolean;
  transactions: unknown[];
}

export const BAISOFTPAY_TRANSACTION_API = {
  initiate: async (payload: IBaisoftPayTransactionInitiationPayload) => {
    const response = await apiRequest.post(
      "system/baisoftpay/transactions/initiate/payout/",
      payload,
    );

    return response.data as IBaisoftPayTransactionInitiationResponse;
  },

  initiateCollection: async (payload: IBaisoftPayCollectionInitiationPayload) => {
    const response = await apiRequest.post(
      "system/baisoftpay/transactions/initiate/collection/",
      payload,
    );

    return response.data as IBaisoftPayTransactionInitiationResponse;
  },
};

export type BaisoftPayCollectionPaymentMethod = "mobile_money" | "bank" | "digital_wallet";

export interface IBaisoftPayCollectionTarget {
  customer_base_uuid?: string | null;
  invoice_base_uuid?: string | null;
  amount: string;
  description: string;
  identifier: string;
  payment_method: BaisoftPayCollectionPaymentMethod;
  operator_country_code?: string;
  operator_code?: string;
  to_charge_merchant: boolean;
}

export interface IBaisoftPayCollectionInitiationPayload {
  digital_wallet_base_uuid: string;
  description: string;
  transactions: IBaisoftPayCollectionTarget[];
}

export interface IRecycleBinEntry {
  id: number;
  object_uuid: string;
  model_name: string;
  deleted_by: string | null;
  deleted_by_name: string;
  deleted_at: string;
  data: string;
  reference_code: string | null;
  base_uuid: string;
}

export interface IRecycleBinEntryFormData {}

export interface IDraft<TData = Record<string, unknown>> {
  id: number;
  base_uuid: string;
  content_type: {
    id: number;
    app_label: string;
    model: string;
  };
  object_uuid: string;
  reference_code: string | null;
  data: TData;
  created_at: string;
  updated_at: string;
  expires_at: string;
}

export interface IDraftPayload<TData> {
  content_type: string;
  data: TData;
}

export const DRAFTS_API = {
  fetch: async <TData>(contentType: string) => {
    const response = await apiRequest.get(
      `system/drafts/?content_type=${encodeURIComponent(contentType)}`,
    );
    return response.data as IPaginatedResponse<IDraft<TData>>;
  },

  fetchFromUrl: async <TData>(url: string) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IDraft<TData>>;
  },

  create: async <TData>(payload: IDraftPayload<TData>) => {
    const response = await apiRequest.post("system/drafts/", payload);
    return response.data as IDraft<TData>;
  },

  update: async <TData>(baseUuid: string, payload: IDraftPayload<TData>) => {
    const response = await apiRequest.patch(`system/drafts/${baseUuid}/`, payload);
    return response.data as IDraft<TData>;
  },

  discard: async (baseUuid: string) => {
    await apiRequest.delete(`system/drafts/${baseUuid}/`);
  },

  discardAll: async (contentType: string) => {
    await apiRequest.delete(`system/drafts/?content_type=${encodeURIComponent(contentType)}`);
  },
};

export const RECYCLE_BIN_API = {
  fetch: async ({
    query,
    page,
    ...queryParams
  }: {query?: Record<string, unknown>; page?: number; [key: string]: unknown} = {}) => {
    const params = toParams({...query, ...queryParams, page});
    const res = await apiRequest.get(`institution/recycle-bin/?${params.toString()}`);
    return res.data as IPaginatedResponse<IRecycleBinEntry>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const res = await apiRequest.get(url);
    return res.data as IPaginatedResponse<IRecycleBinEntry>;
  },

  restore: async ({object_uuid}: {object_uuid: string}) => {
    const res = await apiRequest.post(`institution/recycle-bin/${object_uuid}/restore/`, {});
    return res.data;
  },

  deleteByUUID: async (object_uuid: string) => {
    await apiRequest.delete(`institution/recycle-bin/${object_uuid}/permanent-delete/`);
  },

  bulkRestore: async (base_uuids: string[]) => {
    const res = await apiRequest.post("institution/recycle-bin/bulk-restore/", {base_uuids});
    return res.data as {detail?: string; restored?: string[]; errors?: unknown[]};
  },

  bulkDelete: async (base_uuids: string[]) => {
    const res = await apiRequest.post("institution/recycle-bin/bulk-permanent-delete/", {
      base_uuids,
    });
    return res.data as {detail?: string};
  },

  empty: async () => {
    const res = await apiRequest.delete("institution/recycle-bin/empty/");
    return res.data as {detail?: string};
  },
};

export interface IFeature {
  id: number;
  base_uuid: string;
  institution: number;
  system_feature: {
    id: number;
    feature_name: string;
    feature_code: string;
    description: string;
    is_mandatory: boolean;
    is_active: boolean;
  };
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export const FEATURE_CONFIG_API = defineEndpoint<IFeature, {}>("institution/system/features/");

export const SYSTEM_INDUSTRIES_API = defineEndpoint<IIndustry, {}>("institution/system-industries");

export interface IExchangeRateSideInput {
  currency: number;
  value: string;
}

export interface IExchangeRateInput {
  one_side: IExchangeRateSideInput;
  other_side: IExchangeRateSideInput;
}

export interface IExchangeRateCurrency {
  id: number;
  code: string;
  name: string;
  symbol: string;
}

export interface IExchangeRateRepresentation {
  one_side: {
    currency: IExchangeRateCurrency;
    value: string;
  };
  other_side: {
    currency: IExchangeRateCurrency;
    value: string;
  };
}

export interface ICurrencyConversion {
  model_name?:
    | "customer"
    | "quotation"
    | "invoice"
    | "customer_purchase_order"
    | "vendors"
    | "vendor_purchase_order";
  object_uuid?: string;
  amount: string | number;
  exchange_rate?: IExchangeRateInput;
  /** Kept temporarily for callers using the legacy endpoint contract. */
  override_rate?: string;
  currency?: string;
  target_currency?: string;
}

export interface ICurrencyConversionResult {
  original_amount: string;
  converted_amount: string;
  canonical_rate: string;
  exchange_rate: IExchangeRateRepresentation;
  from_currency: string;
  to_currency: string;
}

const base_api = defineEndpoint<ICurrencyConversionResult, ICurrencyConversion>(
  "institution/currency-conversion/",
);

export const CURRENCY_CONVERSION_API = {
  post: (payload: ICurrencyConversion) => base_api.create(payload, false),
};

export interface IStockValuationMethod {
  id: number;
  base_uuid: string;
  code: string;
  name: string;
  description: string;
  is_deleted?: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  external_base_uuid?: string | null;
  reference_code?: string | null;
  created_by?: number | null;
  updated_by?: number | null;
}

export type AuditAction = "CREATE" | "UPDATE" | "DELETE";

export interface IInstitutionAuditLog {
  id: number;
  content_type: string;
  object_id: number;
  content_object: string | null;
  action: AuditAction;
  user: string | null;
  timestamp: string;
  changes: unknown;
  description: string;
}

const stock_valuation_api = defineEndpoint<IStockValuationMethod, {}>(
  "system/stock-valuation-methods/",
);

export const STOCK_VALUATION_METHODS_API = {
  fetch: stock_valuation_api.fetch.bind(stock_valuation_api),
  fetchFromUrl: stock_valuation_api.fetchFromUrl.bind(stock_valuation_api),
};

export interface IStockMovementStrategy extends IStockValuationMethod {}

const stock_movement_api = defineEndpoint<IStockMovementStrategy, {}>(
  "system/stock-movement-strategies/",
);

export const STOCK_MOVEMENT_STRATEGY_API = {
  fetch: stock_movement_api.fetch.bind(stock_movement_api),
  fetchFromUrl: stock_movement_api.fetchFromUrl.bind(stock_movement_api),
};

export const AUDIT_LOGS_API = {
  fetchFirstPage: async (q: {
    search?: string;
    page?: number;
    page_size?: number;
    content_type?: string;
    object_id?: number;
  }) => {
    const params = new URLSearchParams();

    Object.entries(q).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v).trim() !== "") {
        params.append(k, String(v));
      }
    });

    const response = await apiRequest.get(`/audit/logs/?${params.toString()}`);

    return response.data as IPaginatedResponse<IInstitutionAuditLog>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IInstitutionAuditLog>;
  },

  fetchById: async ({id}: {id: number | string}) => {
    const response = await apiRequest.get(`/audit/logs/${id}/`);

    return response.data as IInstitutionAuditLog;
  },
};

export type SequenceType = "numeric" | "alpha";

export interface IReferenceSequenceFormData {
  content_type: number;
  prefix: string;
  sequence_type: SequenceType;
  starting_value: number;
  padding_digits?: number | null;
  is_active: boolean;
}

export interface IReferenceSequence {
  base_uuid: string;
  institution: number;
  content_type: number;
  content_type_label: string;
  prefix: string;
  sequence_type: SequenceType;
  starting_value: number | null;
  padding_digits: number | null;
  last_value: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IReferenceSequenceStatus {
  exists: boolean;
  is_deleted: boolean;
  can_change_starting_value: boolean;
  sequence: IReferenceSequence | null;
}

export const REFERENCE_SEQUENCES_API = {
  fetchReferenceSequenceStatus: async ({contentType}: {contentType: number}) => {
    const response = await apiRequest.get(
      `institution/reference-sequences/status/?content_type=${contentType}`,
    );

    return response.data as IReferenceSequenceStatus;
  },

  fetchReferenceSequences: async ({
    page = 1,
    search = "",
    ordering = "",
  }: {
    page?: number;
    search?: string;
    ordering?: string;
  }) => {
    const params = new URLSearchParams();

    params.append("page", page.toString());
    if (search) {
      params.append("search", search);
    }
    if (ordering) {
      params.append("ordering", ordering);
    }

    const response = await apiRequest.get(`institution/reference-sequences/?${params.toString()}`);

    return response.data as IPaginatedResponse<IReferenceSequence>;
  },

  fetchReferenceSequencesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IReferenceSequence>;
  },

  createReferenceSequence: async ({sequenceData}: {sequenceData: IReferenceSequenceFormData}) => {
    const response = await apiRequest.post(`institution/reference-sequences/`, sequenceData);

    return response.data as IReferenceSequence;
  },

  updateReferenceSequence: async ({
    sequenceUuid,
    sequenceData,
  }: {
    sequenceUuid: string;
    sequenceData: IReferenceSequenceFormData;
  }) => {
    const response = await apiRequest.patch(
      `institution/reference-sequences/${sequenceUuid}/`,
      sequenceData,
    );

    return response.data as IReferenceSequence;
  },

  deleteReferenceSequence: async ({sequenceUuid}: {sequenceUuid: string}) => {
    await apiRequest.delete(`institution/reference-sequences/${sequenceUuid}/`);
  },

  fetchReferenceSequenceById: async ({sequenceUuid}: {sequenceUuid: string}) => {
    const response = await apiRequest.get(`institution/reference-sequences/${sequenceUuid}/`);

    return response.data as IReferenceSequence;
  },
};
