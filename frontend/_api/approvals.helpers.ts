import type {
  Action,
  Approval,
  ApprovalRiskAnalysis,
  ApprovalTask,
  ContentTypeLite,
  ApprovalDocument,
  ApprovalDocumentLevel,
  ApprovalDocumentFormData,
  ApprovalDocumentLevelFormData,
  ApproverGroup,
  ApproverGroupFormData,
  ICashAtHand,
  ICashAtHandFormData,
  IDigitalWallet,
  IDigitalWalletFormData,
  IDigitalWalletUpdateData,
  IMobileMoneyAccount,
  IMobileMoneyFormData,
  IMobileMoneyUpdateData,
  ICashAccount,
  IStockMovementBranchToBranch,
  IStockMovementFormData,
  IGoodsReceivedNote,
  IGoodsReceivedNoteFormData,
  IBackOrderFormData,
  IBackOrder,
  IWriteOffFormData,
  IWriteOff,
  IWriteOffLineItems,
  IWriteOffInstitutionLineItem,
  IWriteOffBranchLineItem,
  IPeriodLocking,
  IPeriodLockedFormData,
  IGIN,
  IGINFormData,
  IProduct,
  IProductsResponse,
  IStockMovementDownloadParams,
  IAssetRevaluation,
  IAssetRevaluationFormData,
  IRequisitionItem,
  IRequisitionItemFormData,
  IStockReportRow,
  IFixedAssetReportRow,
  IDisposedAssetReportRow,
  IActivityAssetReportRow,
  IBalanceAdjustmentsFormData,
  IBalanceAdjustmentsDownloadPayload,
  ICashAccountReport,
  ICashAccountReportDownload,
  ICustomerBalanceReport,
  ICustomerBalanceReportDownload,
  IVendorBalanceReport,
  IVendorBalanceReportDownload,
  ILedgerReportAccount,
  ILedgerReportDownload,
  ISendBackApprovalTaskFormData,
  IGINLineItem,
} from "#/_types/approvals.types";

import apiRequest from "./api-request";

import {IPaginatedResponse} from "#/_types/api.types";
import {getAllSelectedBranchUUIDs, getCurrentBranchId, getDefaultInstitutionId} from "./helpers";
import {toParams} from "../_lib/utils";
import {downloadFileApi, triggerDownload} from "./api.helpers";
const BASE = "approval";

/* -------------------- ACTIONS -------------------- */
export const ACTIONS_API = {
  fetchActions: async (params?: {search?: string; page?: number; page_size?: number}) => {
    const res = await apiRequest.get(`${BASE}/actions/`);

    return res.data as
      | {count?: number; next?: string | null; previous?: string | null; results?: Action[]}
      | Action[];
  },
};

/* -------------------- APPROVABLE MODELS -------------------- */
export const APPROVABLE_MODELS_API = {
  fetchAll: async (query: Record<string, unknown> = {}) => {
    const params = toParams(query);
    const res = await apiRequest.get(`${BASE}/approvable-models/?${params.toString()}`);
    return res.data as IPaginatedResponse<ContentTypeLite>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const res = await apiRequest.get(url);
    return res.data as IPaginatedResponse<ContentTypeLite>;
  },

  fetchById: async ({id}: {id: number}) => {
    const res = await apiRequest.get(`${BASE}/approvable-models/${id}`);
    return res.data as ContentTypeLite;
  },
};
/* -------------------- APPROVALS -------------------- */
export const APPROVALS_API = {
  fetchAll: async (params?: {
    search?: string;
    status?: "ongoing" | "rejected" | "completed";
    page?: number;
    page_size?: number;
    content_type_id?: number;
    object_base_uuid?: string;
  }) => {
    const res = await apiRequest.get(`${BASE}/approvals/`, params);

    return res.data as {
      count: number;
      next: string | null;
      previous: string | null;
      results: Approval[];
    };
  },

  fetchById: async ({id}: {id: string}) => {
    const res = await apiRequest.get(`${BASE}/approvals/${id}/`);

    return res.data as Approval;
  },

  fetchRiskAnalysis: async ({baseUuid}: {baseUuid: string}) => {
    const res = await apiRequest.get(`${BASE}/approvals/${baseUuid}/risk-analysis/`);

    return res.data as ApprovalRiskAnalysis;
  },
};

/* -------------------- APPROVAL TASKS -------------------- */
export const APPROVAL_TASKS_API = {
  fetchAll: async (params?: {
    search?: string;
    status?: "not_started" | "pending" | "rejected" | "approved" | "terminated";
    assigned_to?: number;
    type?: string;
    page?: number;
    page_size?: number;
  }) => {
    const param = new URLSearchParams(params ? (params as any) : {});
    const res = await apiRequest.get(`${BASE}/approval-tasks/?${param.toString()}`, null);

    return res.data as IPaginatedResponse<ApprovalTask>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ApprovalTask>;
  },

  fetchById: async ({baseUuid}: {baseUuid: string}) => {
    const res = await apiRequest.get(`${BASE}/approval-tasks/${baseUuid}/`);

    return res.data as ApprovalTask;
  },

  approve: async ({baseUuid, comment}: {baseUuid: string; comment?: string}) => {
    const url = comment
      ? `${BASE}/approval-tasks/${baseUuid}/approve/?comment=${encodeURIComponent(comment)}`
      : `${BASE}/approval-tasks/${baseUuid}/approve/`;
    const res = await apiRequest.patch(url, {});

    return res.data as ApprovalTask;
  },

  reject: async ({baseUuid, comment}: {baseUuid: string; comment?: string}) => {
    const url = comment
      ? `${BASE}/approval-tasks/${baseUuid}/reject/?comment=${encodeURIComponent(comment)}`
      : `${BASE}/approval-tasks/${baseUuid}/reject/`;
    const res = await apiRequest.patch(url, {});

    return res.data as ApprovalTask;
  },

  override: async ({id, comment}: {id: number; comment?: string}) => {
    const url = comment
      ? `${BASE}/override/${id}/?comment=${encodeURIComponent(comment)}`
      : `${BASE}/approval-tasks/${id}/approve/`;
    const res = await apiRequest.patch(url, {});

    return res.data as ApprovalTask;
  },

  fetchDashboard: async () => {
    const res = await apiRequest.get(`${BASE}/tasks-analytics/`);

    return res.data as {
      incoming: {count: number; tasks: ApprovalTask[]};
      open: {count: number; tasks: ApprovalTask[]};
      critical: {count: number; tasks: ApprovalTask[]};
      expired: {count: number; tasks: ApprovalTask[]};
      outgoing: {count: number; tasks: ApprovalTask[]};
    };
  },

  sendBack: async ({
    baseUuid,
    payload,
  }: {
    baseUuid: string;
    payload: ISendBackApprovalTaskFormData;
  }) => {
    const res = await apiRequest.post(`${BASE}/approval-tasks/${baseUuid}/send-back/`, {
      ...(payload.target_level != null && {target_level: payload.target_level}),
      ...(payload.comment && {comment: payload.comment}),
      return_to_sender: payload.return_to_sender ?? false,
    });

    return res.data as {
      status: "sent_back";
      target_task_id: number;
      return_route_id: number | null;
    };
  },

  recall: async ({baseUuid, comment}: {baseUuid: string; comment: string}) => {
    const res = await apiRequest.post(`${BASE}/approval-tasks/${baseUuid}/recall/`, {
      comment,
    });

    return res.data as ApprovalTask;
  },
};

/* -------------------- APPROVAL DOCUMENTS -------------------- */
export const APPROVAL_DOCUMENTS_API = {
  fetchAll: async (params?: {
    search?: string;
    page?: number;
    content_type_id?: number;
    app_label?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.append("search", params.search);
    if (params?.page) qs.append("page", String(params.page));
    if (params?.content_type_id) qs.append("content_type_id", String(params.content_type_id));
    if (params?.app_label) qs.append("app_label", params.app_label);

    const query = qs.toString();
    const res = await apiRequest.get(`${BASE}/approval-documents/${query ? `?${query}` : ""}`);

    return res.data as IPaginatedResponse<ApprovalDocument>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const res = await apiRequest.get(url);

    return res.data as IPaginatedResponse<ApprovalDocument>;
  },

  fetchById: async ({id}: {id: string}) => {
    const res = await apiRequest.get(`${BASE}/approval-documents/${id}/`);

    return res.data as ApprovalDocument;
  },

  create: async (payload: Partial<ApprovalDocumentFormData>) => {
    const res = await apiRequest.post(`${BASE}/approval-documents/`, payload);

    return res.data as ApprovalDocument;
  },

  update: async ({id, payload}: {id: string; payload: Partial<ApprovalDocumentFormData>}) => {
    const res = await apiRequest.patch(`${BASE}/approval-documents/${id}/`, payload);

    return res.data as ApprovalDocument;
  },

  delete: async ({id}: {id: string}) => {
    const res = await apiRequest.delete(`${BASE}/approval-documents/${id}/`);

    return res.status === 204;
  },
};

/* -------------------- APPROVAL DOCUMENT LEVELS -------------------- */
export const APPROVAL_DOCUMENT_LEVELS_API = {
  fetchAll: async (params?: {search?: string; page?: number; approval_document?: number}) => {
    const res = await apiRequest.get(
      `${BASE}/approval-document-levels/`,
      null,
      params ? {params} : {},
    );

    return res.data as IPaginatedResponse<ApprovalDocumentLevel>;
  },

  fetchById: async ({id}: {id: string}) => {
    const res = await apiRequest.get(`${BASE}/approval-document-levels/${id}/`);

    return res.data as ApprovalDocumentLevel;
  },

  create: async (payload: Partial<ApprovalDocumentLevelFormData>) => {
    const res = await apiRequest.post(`${BASE}/approval-document-levels/`, payload);

    return res.data as ApprovalDocumentLevel;
  },

  update: async ({id, payload}: {id: string; payload: Partial<ApprovalDocumentLevelFormData>}) => {
    const res = await apiRequest.patch(`${BASE}/approval-document-levels/${id}/`, payload);

    return res.data as ApprovalDocumentLevel;
  },

  delete: async ({id}: {id: string}) => {
    await apiRequest.delete(`${BASE}/approval-document-levels/${id}/`);
  },
  bulkCreate: async (payload: Partial<ApprovalDocumentLevelFormData>[]) => {
    const res = await apiRequest.post(`${BASE}/approval-document-levels/`, payload);

    return res.data as ApprovalDocumentLevel[];
  },
};

/* -------------------- APPROVER GROUPS -------------------- */
export const APPROVER_GROUPS_API = {
  fetchAll: async (params?: {search?: string; page?: number; page_size?: number}) => {
    const res = await apiRequest.get(`${BASE}/approver-groups/`, null, params ? {params} : {});

    return res.data as {
      count: number;
      next: string | null;
      previous: string | null;
      results: ApproverGroup[];
    };
  },

  fetchById: async ({id}: {id: string}) => {
    const res = await apiRequest.get(`${BASE}/approver-groups/${id}/`);

    return res.data as ApproverGroup;
  },

  create: async (payload: Partial<ApproverGroupFormData>) => {
    const res = await apiRequest.post(`${BASE}/approver-groups/`, payload);

    return res.data as ApproverGroup;
  },

  update: async ({id, payload}: {id: string; payload: Partial<ApproverGroupFormData>}) => {
    const res = await apiRequest.patch(`${BASE}/approver-groups/${id}/`, payload);

    return res.data as ApproverGroup;
  },

  delete: async ({id}: {id: string}) => {
    await apiRequest.delete(`${BASE}/approver-groups/${id}/`);
  },
};

export type DefaultDataCategory =
  | "UNITS"
  | "BUSINESS_DOCUMENT_CATEGORIES"
  | "CATEGORIES"
  | "OTHER_INCOME_CATEGORIES"
  | "PAYMENT_TERMS"
  | "REQUISITION_TYPES"
  | "ROLES";

export const DEFAULT_DATA_API = {
  fetchDefaults: async <T = any>({
    category_code,
    search,
    page = 1,
    page_size = 500,
    fetchAllPages = false,
  }: {
    category_code: DefaultDataCategory;
    search?: string;
    page?: number;
    page_size?: number;
    fetchAllPages?: boolean;
  }): Promise<IPaginatedResponse<T> | T[]> => {
    const params = new URLSearchParams({
      category_code,
      page: page.toString(),
      page_size: page_size.toString(),
      ...(search ? {search} : {}),
    });

    const url = `institution/default-data/?${params.toString()}`;
    const response = await apiRequest.get(url);

    const data = response.data as IPaginatedResponse<T>;

    if (fetchAllPages && data.next) {
      const remaining = await DEFAULT_DATA_API.fetchAllRemaining<T>(data.next);
      return [...data.results, ...remaining];
    }

    return data;
  },

  fetchAllRemaining: async <T = any>(nextUrl: string): Promise<T[]> => {
    if (!nextUrl) return [];

    const response = await apiRequest.get(nextUrl);
    const data = response.data as IPaginatedResponse<T>;

    const remaining = data.next ? await DEFAULT_DATA_API.fetchAllRemaining<T>(data.next) : [];
    return [...data.results, ...remaining];
  },

  fetchFromUrl: async <T = any>(url: string): Promise<IPaginatedResponse<T>> => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<T>;
  },
};

export const CASH_AT_HAND_API = {
  fetchCashAtHandAccounts: async ({page = 1, search = ""}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `/bank_management/cash-at-hand-accounts/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<ICashAtHand>;
  },

  fetchCashAtHandFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICashAtHand>;
  },

  createCashAtHand: async ({cashAtHandData}: {cashAtHandData: ICashAtHandFormData}) => {
    const response = await apiRequest.post(
      `/bank_management/cash-at-hand-accounts/`,
      cashAtHandData,
    );

    return response.data as ICashAtHand;
  },

  fetchCashAtHandById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`/bank_management/cash-at-hand-accounts/${base_uuid}/`);

    return response.data as ICashAtHand;
  },

  updateCashAtHand: async ({
    base_uuid,
    cashAtHandData,
  }: {
    base_uuid: string;
    cashAtHandData: Partial<ICashAtHandFormData>;
  }) => {
    const response = await apiRequest.patch(
      `/bank_management/cash-at-hand-accounts/${base_uuid}/`,
      cashAtHandData,
    );

    return response.data as ICashAtHand;
  },

  deleteCashAtHand: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`/bank_management/cash-at-hand-accounts/${base_uuid}/`);
  },
};

export const DIGITAL_WALLET_API = {
  fetchDigitalWallets: async ({
    page = 1,
    search = "",
    currency,
    platformName,
    isActive,
  }: {
    page?: number;
    search?: string;
    currency?: number;
    platformName?: string;
    isActive?: boolean;
  }) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (currency !== undefined) params.append("currency__currency_id", currency.toString());
    if (platformName) params.append("platform_name", platformName);
    if (isActive !== undefined) params.append("is_active", String(isActive));

    const response = await apiRequest.get(
      `/bank_management/digital-wallet-accounts/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IDigitalWallet>;
  },

  fetchDigitalWalletsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IDigitalWallet>;
  },

  createDigitalWallet: async ({digitalWalletData}: {digitalWalletData: IDigitalWalletFormData}) => {
    const response = await apiRequest.post(
      `/bank_management/digital-wallet-accounts/`,
      digitalWalletData,
    );

    return response.data as IDigitalWallet;
  },

  fetchDigitalWalletById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`/bank_management/digital-wallet-accounts/${base_uuid}/`);

    return response.data as IDigitalWallet;
  },

  updateDigitalWallet: async ({
    base_uuid,
    digitalWalletData,
  }: {
    base_uuid: string;
    digitalWalletData: IDigitalWalletUpdateData;
  }) => {
    const response = await apiRequest.patch(
      `/bank_management/digital-wallet-accounts/${base_uuid}/`,
      digitalWalletData,
    );

    return response.data as IDigitalWallet;
  },

  deleteDigitalWallet: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`/bank_management/digital-wallet-accounts/${base_uuid}/`);
  },
};

export const MOBILE_MONEY_API = {
  fetchMobileMoneyAccounts: async ({page = 1, search = ""}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `/bank_management/mobile-money-accounts/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IMobileMoneyAccount>;
  },

  fetchMobileMoneyFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IMobileMoneyAccount>;
  },

  createMobileMoneyAccount: async ({mobileMoneyData}: {mobileMoneyData: IMobileMoneyFormData}) => {
    const response = await apiRequest.post(
      `/bank_management/mobile-money-accounts/`,
      mobileMoneyData,
    );

    return response.data as IMobileMoneyAccount;
  },

  fetchMobileMoneyById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`/bank_management/mobile-money-accounts/${base_uuid}/`);

    return response.data as IMobileMoneyAccount;
  },

  updateMobileMoneyAccount: async ({
    base_uuid,
    mobileMoneyData,
  }: {
    base_uuid: string;
    mobileMoneyData: IMobileMoneyUpdateData;
  }) => {
    const response = await apiRequest.patch(
      `/bank_management/mobile-money-accounts/${base_uuid}/`,
      mobileMoneyData,
    );

    return response.data as IMobileMoneyAccount;
  },

  deleteMobileMoneyAccount: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`/bank_management/mobile-money-accounts/${base_uuid}/`);
  },
};

export const CASH_ACCOUNTS_API = {
  fetchCashAccounts: async ({
    page = 1,
    search = "",
    excludeCashbooks = false,
    currency,
  }: {
    page?: number;
    search?: string;
    excludeCashbooks?: boolean;
    currency?: number;
  }) => {
    const params = new URLSearchParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (excludeCashbooks) params.append("exclude_cashbooks", "true");
    if (search.trim()) params.append("search", search.trim());
    if (currency) params.append("currency", currency.toString());

    const response = await apiRequest.get(`/bank_management/cash-accounts/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICashAccount>;
  },
  fetchCashAccountsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ICashAccount>;
  },
};

export const STOCKMOVEMENT_API = {
  fetchStockMovements: async ({page = 1, search = ""}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `/items/branch-to-branch-stock-movement/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IStockMovementBranchToBranch>;
  },

  fetchStockMovementsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IStockMovementBranchToBranch>;
  },

  createStockMovement: async ({stockMovementData}: {stockMovementData: IStockMovementFormData}) => {
    const response = await apiRequest.post(
      `/items/branch-to-branch-stock-movement/`,
      stockMovementData,
    );

    return response.data as IStockMovementBranchToBranch;
  },

  fetchStockMovementById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`/items/branch-to-branch-stock-movement/${base_uuid}/`);

    return response.data as IStockMovementBranchToBranch;
  },

  updateStockMovement: async ({
    base_uuid,
    stockMovementData,
  }: {
    base_uuid: string;
    stockMovementData: Partial<IStockMovementFormData>;
  }) => {
    const response = await apiRequest.patch(
      `/items/branch-to-branch-stock-movement/${base_uuid}/`,
      stockMovementData,
    );

    return response.data as IStockMovementBranchToBranch;
  },

  deleteStockMovement: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`/items/branch-to-branch-stock-movement/${base_uuid}/`);
  },

  downloadStockMovementLog: async (params: IStockMovementDownloadParams) => {
    if (params.delivery_method === "download") {
      const blob = await downloadFileApi({
        url: `items/stock-movement-download/`,
        method: "POST",
        body: params,
        timeout: 120000,
      });
      const extension = params.file_type === "pdf" ? "pdf" : "xlsx";
      triggerDownload(
        blob,
        `StockMovementReport_${new Date().toISOString().replace(/[:.]/g, "-")}.${extension}`,
      );
      return {message: "Stock movement report downloaded successfully."};
    }

    const response = await apiRequest.post(`items/stock-movement-download/`, params);
    return response.data as {message: string};
  },
};

export const GOODS_RECEIVED_NOTES_API = {
  fetchGoodsReceivedNotes: async (args: {
    query?: {vendor?: string; page?: number; search?: string; ordering?: string};
    page?: number;
  }) => {
    const q = args.query ?? (args as any);
    const params = toParams({
      search: q.search,
      vendor: q.vendor,
      ordering: q.ordering,
      page: args.page ?? q.page,
    });
    const response = await apiRequest.get(`vendors/goods-received-note/?${params.toString()}`);
    return response.data as IPaginatedResponse<IGoodsReceivedNote>;
  },

  fetchGoodsReceivedNotesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IGoodsReceivedNote>;
  },

  createGoodsReceivedNote: async ({grnData}: {grnData: IGoodsReceivedNoteFormData}) => {
    const response = await apiRequest.post(`vendors/goods-received-note/`, {
      ...grnData,
    });

    return response.data as IGoodsReceivedNote;
  },

  updateGoodsReceivedNote: async ({
    grnUuid,
    grnData,
  }: {
    grnUuid: string;
    grnData: Partial<IGoodsReceivedNoteFormData>;
  }) => {
    const response = await apiRequest.patch(`vendors/goods-received-note/detail/${grnUuid}/`, {
      ...grnData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IGoodsReceivedNote;
  },

  deleteGoodsReceivedNote: async ({grnUuid}: {grnUuid: string}) => {
    await apiRequest.delete(`vendors/goods-received-note/detail/${grnUuid}/`);
  },

  fetchGoodsReceivedNoteById: async ({grnUuid}: {grnUuid: string}) => {
    const response = await apiRequest.get(`vendors/goods-received-note/detail/${grnUuid}/`);

    return response.data as IGoodsReceivedNote;
  },

  fetchGoodsReceivedNoteLineItems: async ({grnUuid}: {grnUuid: string}) => {
    const response = await apiRequest.get(`vendors/goods-received-note/${grnUuid}/line-items/`);

    return response.data as IPaginatedResponse<
      NonNullable<IGoodsReceivedNote["inventory_items"]>[number]
    >;
  },

  fetchGoodsReceivedNoteLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<
      NonNullable<IGoodsReceivedNote["inventory_items"]>[number]
    >;
  },
};

export const BACK_ORDER_API = {
  fetchBackOrders: async (query: {page?: number; search?: string; backorder_type?: string}) => {
    const {page, search, backorder_type} = query as any;

    const params = new URLSearchParams();
    if (page) params.append("page", String(page));
    if (search) params.append("search", search);
    if (backorder_type) params.append("backorder_type", backorder_type);

    const response = await apiRequest.get(`procurement/back-order/?${params.toString()}`);

    return response.data as IPaginatedResponse<IBackOrder>;
  },

  fetchBackOrdersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBackOrder>;
  },

  createBackOrders: async ({backOrderData}: {backOrderData: IBackOrderFormData}) => {
    const response = await apiRequest.post(`procurement/back-order/`, {
      ...backOrderData,
    });

    return response.data as IBackOrder;
  },

  fetchBackOrderById: async ({backOrderUuid, type}: {backOrderUuid: string; type: string}) => {
    const response = await apiRequest.get(
      `procurement/back-order/${backOrderUuid}/?backorder_type=${type}&base_uuid=${backOrderUuid}`,
    );
    return response.data as IBackOrder;
  },

  updateBackOrder: async ({
    backOrderUuid,
    backOrderData,
  }: {
    backOrderUuid: string;
    backOrderData: Partial<IBackOrderFormData>;
  }) => {
    const response = await apiRequest.patch(`procurement/back-order/${backOrderUuid}/`, {
      ...backOrderData,
    });

    return response.data as IBackOrder;
  },

  deleteBackOrder: async ({backOrderUuid}: {backOrderUuid: string}) => {
    await apiRequest.delete(`procurement/back-order/${backOrderUuid}/`);
  },
};

export const WRITE_OFF_API = {
  fetchWriteOffLineItems: async ({
    writeOffUuid,
  }: {
    writeOffUuid: string;
  }): Promise<IWriteOffLineItems> => {
    type BranchLine = Omit<IWriteOffBranchLineItem, "branch_inventory_item"> & {
      branch_inventory_item: {
        id: number;
        base_uuid: string;
        item_name: string | null;
        inventory_item: IWriteOffBranchLineItem["branch_inventory_item"]["inventory_item"];
      };
    };
    type Page =
      | (IPaginatedResponse<IWriteOffInstitutionLineItem> & {item_type: "institution"})
      | (IPaginatedResponse<BranchLine> & {item_type: "branch"});

    const items: IWriteOffLineItems = {
      institution_line_items: [],
      branch_line_items: [],
    };
    let url: string | null = `items/write-off/${writeOffUuid}/line-items/`;
    while (url) {
      const response = await apiRequest.get(url);
      const page = response.data as Page;
      if (page.item_type === "institution") {
        items.institution_line_items.push(...page.results);
      } else if (page.item_type === "branch") {
        items.branch_line_items.push(
          ...page.results.map((item) => ({
            ...item,
            branch_inventory_item: {
              ...item.branch_inventory_item,
              inventory_item: item.branch_inventory_item.inventory_item,
            },
          })),
        );
      } else {
        throw new Error("Unknown write-off line item type");
      }
      url = page.next;
    }
    return items;
  },
  fetchWriteOffs: async (query: {page?: number; search?: string}) => {
    const params = new URLSearchParams();
    if (query.page) params.append("page", String(query.page));
    if (query.search) params.append("search", query.search);

    const response = await apiRequest.get(`items/write-off/?${params.toString()}`);

    return response.data as IPaginatedResponse<IWriteOff>;
  },

  fetchWriteOffsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IWriteOff>;
  },

  createWriteOff: async ({writeOffData}: {writeOffData: IWriteOffFormData}) => {
    const response = await apiRequest.post(`items/write-off/`, {
      ...writeOffData,
    });

    return response.data as IWriteOff;
  },

  fetchWriteOffById: async ({writeOffUuid}: {writeOffUuid: string}) => {
    const response = await apiRequest.get(`items/write-off/${writeOffUuid}/`);

    return response.data as IWriteOff;
  },

  updateWriteOff: async ({
    writeOffUuid,
    writeOffData,
  }: {
    writeOffUuid: string;
    writeOffData: Partial<IWriteOffFormData>;
  }) => {
    const response = await apiRequest.patch(`items/write-off/${writeOffUuid}/`, {
      ...writeOffData,
    });

    return response.data as IWriteOff;
  },

  deleteWriteOff: async ({writeOffUuid}: {writeOffUuid: string}) => {
    await apiRequest.delete(`items/write-off/${writeOffUuid}/`);
  },
};

export const PERIOD_LOCKING_API = {
  fetchPeriodLockings: async (query: {page?: number; search?: string}) => {
    const params = new URLSearchParams();
    if (query.page) params.append("page", String(query.page));
    if (query.search) params.append("search", query.search);
    const response = await apiRequest.get(`accounts/account-locks/?${params.toString()}`);
    return response.data as IPaginatedResponse<IPeriodLocking>;
  },

  fetchPeriodLockingsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IPeriodLocking>;
  },

  createPeriodLocking: async ({periodLockingData}: {periodLockingData: IPeriodLockedFormData}) => {
    const response = await apiRequest.post(`accounts/account-locks/`, {...periodLockingData});
    return response.data;
  },

  fetchPeriodLockingById: async ({periodLockingUuid}: {periodLockingUuid: string}) => {
    const response = await apiRequest.get(`accounts/account-locks/${periodLockingUuid}/`);
    return response.data;
  },

  updatePeriodLocking: async ({
    periodLockingUuid,
    periodLockingData,
  }: {
    periodLockingUuid: string;
    periodLockingData: Partial<IPeriodLockedFormData>;
  }) => {
    const response = await apiRequest.patch(`accounts/account-locks/${periodLockingUuid}/`, {
      ...periodLockingData,
    });
    return response.data;
  },

  deletePeriodLocking: async ({periodLockingUuid}: {periodLockingUuid: string}) => {
    await apiRequest.delete(`accounts/account-locks/${periodLockingUuid}/`);
  },
};

export const GOODS_ISSUED_NOTE_API = {
  fetchGoodsIssuedNotes: async (query: {
    page?: number;
    search?: string;
    invoice_base_uuid?: string;
    status?: IGIN["status"];
    has_returnable_items?: boolean;
  }) => {
    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      ...query,
    });

    const response = await apiRequest.get(`customers/goods-issued-notes/?${params.toString()}`);

    return response.data as IPaginatedResponse<IGIN>;
  },

  fetchGoodsIssuedNotesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IGIN>;
  },

  createGoodsIssuedNote: async ({ginData}: {ginData: IGINFormData}) => {
    const response = await apiRequest.post(`customers/goods-issued-notes/`, {
      ...ginData,
    });

    return response.data as IGIN;
  },

  fetchGoodsIssuedNoteById: async ({ginUuid}: {ginUuid: string}) => {
    const response = await apiRequest.get(`customers/goods-issued-notes/${ginUuid}/`);

    return response.data as IGIN;
  },

  updateGoodsIssuedNote: async ({ginUuid, ginData}: {ginUuid: string; ginData: IGINFormData}) => {
    const response = await apiRequest.patch(`customers/goods-issued-notes/${ginUuid}/`, {
      ...ginData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IGIN;
  },

  deleteGoodsIssuedNote: async ({ginUuid}: {ginUuid: string}) => {
    await apiRequest.delete(`customers/goods-issued-notes/${ginUuid}/`);
  },

  downloadGoodsIssuedNotePDF: async ({ginUuid}: {ginUuid: string}) => {
    return downloadFileApi({
      url: `customers/goods-issued-notes-report-download/${ginUuid}`,
    });
  },

  fetchGoodsIssuedNoteLineItems: async ({
    ginUuid,
    page = 1,
    search,
  }: {
    ginUuid: string;
    page?: number;
    search?: string;
  }) => {
    const params = toParams({
      page: String(page),
      search,
    });

    const response = await apiRequest.get(
      `customers/goods-issued-notes/${ginUuid}/line-items/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IGINLineItem>;
  },

  fetchGoodsIssuedNoteLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IGINLineItem>;
  },
};

export const PRODUCTS_API = {
  fetchProductsInventory: async ({
    query,
    page,
  }: {
    query?: {search?: string; category?: number};
    page?: number;
  }): Promise<IProductsResponse> => {
    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      ...query,
      ...(page ? {page} : {}),
    });

    const response = await apiRequest.get(`/items/inventory-summary/?${params.toString()}`);
    return response.data as IProductsResponse;
  },

  fetchProductsFromUrl: async ({url}: {url: string}): Promise<IProductsResponse> => {
    const response = await apiRequest.get(url);
    return response.data as IProductsResponse;
  },

  fetchProductById: async ({productUuid}: {productUuid: string}) => {
    const response = await apiRequest.get(`/items/${productUuid}/`);

    return response.data as IProduct;
  },
};

export const ASSET_REVALUATION_API = {
  fetchAssetRevaluations: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      page: page.toString(),
    });

    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`fixed_assets/asset-revaluations/?${params.toString()}`);

    return response.data as IPaginatedResponse<IAssetRevaluation>;
  },

  fetchAssetRevaluationsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IAssetRevaluation>;
  },

  fetchAssetRevaluationById: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`fixed_assets/asset-revaluations/${baseUuid}/`);

    return response.data as IAssetRevaluation;
  },

  createAssetRevaluation: async ({data}: {data: IAssetRevaluationFormData}) => {
    const response = await apiRequest.post(`fixed_assets/asset-revaluations/`, data);

    return response.data as IAssetRevaluation;
  },

  updateAssetRevaluation: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IAssetRevaluationFormData>;
  }) => {
    const response = await apiRequest.patch(`fixed_assets/asset-revaluations/${baseUuid}/`, data);

    return response.data as IAssetRevaluation;
  },

  deleteAssetRevaluation: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`fixed_assets/asset-revaluations/${baseUuid}/`);
  },
};

export const REQUISITION_ITEMS_API = {
  fetchRequisitionItems: async (args: Record<string, any> & {page?: number}) => {
    const {page = 1, ...rest} = args;

    const params = new URLSearchParams();
    params.append("page", String(page));

    Object.entries(rest).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.append(key, String(value));
      }
    });

    const response = await apiRequest.get(`requisitions/req-items?${params.toString()}`);

    return response.data as IPaginatedResponse<IRequisitionItem>;
  },

  fetchRequisitionItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IRequisitionItem>;
  },

  createRequisitionItem: async ({
    itemData,
  }: {
    itemData: IRequisitionItemFormData | IRequisitionItemFormData[];
  }) => {
    const response = await apiRequest.post(`requisitions/req-items`, itemData);
    return response.data;
  },

  updateRequisitionItem: async ({
    itemId,
    itemData,
  }: {
    itemId: string;
    itemData: IRequisitionItemFormData;
  }) => {
    const response = await apiRequest.patch(`requisitions/req-items/${itemId}/`, {
      ...itemData,
    });

    return response.data as IRequisitionItem;
  },

  deleteRequisitionItem: async ({itemId}: {itemId: string}) => {
    await apiRequest.delete(`requisitions/req-items/${itemId}/`);
  },

  fetchRequisitionItemById: async ({itemId}: {itemId: string}) => {
    const response = await apiRequest.get(`requisitions/req-items/${itemId}/`);

    return response.data as IRequisitionItem;
  },
};

export const STOCK_REPORT_API = {
  fetchStockReport: async ({
    branch_uuids = [],
    category_uuids = [],
    inventory_item_uuids = [],
    page,
  }: {
    branch_uuids?: string[];
    category_uuids?: string[];
    inventory_item_uuids?: string[];
    page?: number;
  }) => {
    const params = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
    });

    const response = await apiRequest.post(`/reports/stock/?${params.toString()}`, {
      branch_uuids,
      category_uuids,
      inventory_item_uuids,
    });

    return response.data as IPaginatedResponse<IStockReportRow>;
  },

  fetchStockReportFromUrl: async ({
    url,
    branch_uuids = [],
    category_uuids = [],
    inventory_item_uuids = [],
  }: {
    url: string;
    branch_uuids?: string[];
    category_uuids?: string[];
    inventory_item_uuids?: string[];
  }) => {
    const response = await apiRequest.post(url, {
      branch_uuids,
      category_uuids,
      inventory_item_uuids,
    });
    return response.data as IPaginatedResponse<IStockReportRow>;
  },

  downloadStockReport: async ({
    branch_uuids = [],
    category_uuids = [],
    inventory_item_uuids = [],
    file_type,
    delivery_method,
    recipient_email = "",
  }: {
    branch_uuids?: string[];
    category_uuids?: string[];
    inventory_item_uuids?: string[];
    file_type: "excel" | "pdf";
    delivery_method: "download" | "email";
    recipient_email?: string;
  }) => {
    const body = {
      branch_uuids,
      category_uuids,
      inventory_item_uuids,
      file_type,
      delivery_method,
      recipient_email,
    };

    if (delivery_method === "download") {
      const blob = await downloadFileApi({
        url: `reports/stock/download/`,
        method: "POST",
        body,
      });

      const extension = file_type === "pdf" ? "pdf" : "xlsx";
      triggerDownload(
        blob,
        `StockReport_${new Date().toISOString().replace(/[:.]/g, "-")}.${extension}`,
      );

      return {message: "Stock report downloaded successfully."};
    }

    const response = await apiRequest.post(`reports/stock/download/`, body);
    return response.data as {message: string};
  },
};

export const ACTIVITY_ASSET_REPORT_API = {
  fetchFixedAssetReport: async ({query, page}: {query?: Record<string, any>; page?: number}) => {
    const params = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
      ...(query?.asset_uuid && {asset_uuid: query.asset_uuid}),
      ...(query?.date_from && {date_from: query.date_from}),
      ...(query?.date_to && {date_to: query.date_to}),
      ...(query?.date_filter && {date_filter: query.date_filter}),
      ...(query?.activity_type && {activity_type: query.activity_type}),
      ...(query?.category_uuid && {category_uuid: query.category_uuid}),
      ...(query?.ordering && {ordering: query.ordering}),
    });
    const response = await apiRequest.get(`/fixed_assets/activity/?${params.toString()}`);
    return response.data as IPaginatedResponse<IActivityAssetReportRow>;
  },

  fetchFixedAssetReportFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IActivityAssetReportRow>;
  },

  downloadFixedAssetReport: async ({
    asset_uuid,
    date_from,
    date_to,
    date_filter,
    file_type,
    activity_type,
    category_uuid,
  }: {
    asset_uuid?: string;
    date_from?: string;
    date_to?: string;
    date_filter?: string;
    file_type: "pdf" | "excel";
    activity_type?: string;
    category_uuid?: string;
  }) => {
    return downloadFileApi({
      url: `fixed_assets/fixed-asset-activity-download/`,
      method: "POST",
      body: {
        asset_uuid: asset_uuid ? [asset_uuid] : [],
        date_from: date_from || "",
        date_to: date_to || "",
        date_filter: date_filter || "",
        file_type,
        activity_type: activity_type || "",
        category_uuid: category_uuid ? [category_uuid] : [],
      },
    });
  },
};

export const DISPOSED_ASSET_REPORT_API = {
  fetchReport: async ({
    category_uuid,
    page,
  }: {
    category_uuid?: string;
    page?: number;
  } = {}) => {
    const params = new URLSearchParams({
      ...(category_uuid ? {category_uuid} : {}),
      ...(page ? {page: String(page)} : {}),
    });
    const response = await apiRequest.get(`/fixed_assets/disposed-report/?${params}`);
    return response.data as IPaginatedResponse<IDisposedAssetReportRow>;
  },
  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IDisposedAssetReportRow>;
  },
};

export const FIXED_ASSET_REPORT_API = {
  fetchFixedAssetReport: async (params: Record<string, any> = {}) => {
    const {page, ...rest} = params;

    const urlParams = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
      ...(rest.category_uuid && {category_uuid: rest.category_uuid}),
    });

    const response = await apiRequest.get(`/fixed_assets/report/?${urlParams.toString()}`);
    return response.data as IPaginatedResponse<IFixedAssetReportRow>;
  },

  fetchFixedAssetReportFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IFixedAssetReportRow>;
  },

  downloadFixedAssetReport: async ({
    category_uuids,
    file_type,
  }: {
    category_uuids?: string[];
    file_type: "pdf" | "excel";
  }) => {
    return downloadFileApi({
      url: `fixed_assets/report-download/`,
      method: "POST",
      body: {
        category_uuids: category_uuids || [],
        file_type,
      },
    });
  },
};

export const BALANCE_ADJUSTMENTS_API = {
  fetchBalanceAdjustments: async ({
    page,
    flow_type,
    account_type,
    account_uuid,
    account_uuids,
    date_filter = "all",
    start_date = "",
    end_date = "",
  }: {
    page?: number;
    flow_type?: "IN" | "OUT";
    account_type?: string;
    account_uuid?: string;
    account_uuids?: string[];
    date_filter?: "all" | "range";
    start_date?: string;
    end_date?: string;
  }) => {
    const params = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
      ...(flow_type ? {flow_type} : {}),
      ...(account_type ? {account_type} : {}),
      ...(account_uuid ? {account_uuid} : {}),
      ...(account_uuids?.length ? {account_uuids: account_uuids.join(",")} : {}),
      date_filter,
      ...(date_filter === "range" ? {start_date, end_date} : {}),
    });

    const response = await apiRequest.get(
      `/bank_management/adjustments-report/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IBalanceAdjustmentsFormData>;
  },

  fetchBalanceAdjustmentsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBalanceAdjustmentsFormData>;
  },

  downloadBalanceAdjustments: async (payload: IBalanceAdjustmentsDownloadPayload) => {
    const response = await apiRequest.post(`bank_management/adjustments-report-download/`, payload);
    return response.data as {message: string};
  },
};

export const CASH_ACCOUNT_REPORTS_API = {
  fetchCashAccountReports: async ({
    page,
    account_type,
    account_uuid,
    date_filter = "all",
    start_date = "",
    end_date = "",
  }: {
    page?: number;
    account_type?: string;
    account_uuid?: string;
    date_filter?: "all" | "range";
    start_date?: string;
    end_date?: string;
  }) => {
    const params = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
      ...(account_type ? {account_type} : {}),
      ...(account_uuid ? {account_uuid} : {}),
      date_filter,
      ...(date_filter === "range" ? {start_date, end_date} : {}),
    });

    const response = await apiRequest.get(`/reports/cash-account/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICashAccountReport>;
  },

  fetchCashAccountReportsFromUrl: async ({
    url,
    account_type,
    account_uuid,
    date_filter = "all",
    start_date = "",
    end_date = "",
  }: {
    url: string;
    account_type?: string;
    account_uuid?: string;
    date_filter?: "all" | "range";
    start_date?: string;
    end_date?: string;
  }) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICashAccountReport>;
  },

  downloadCashAccountReport: async (payload: ICashAccountReportDownload) => {
    const response = await apiRequest.post(`reports/cash-account-download/`, payload);
    return response.data as {message: string};
  },
};

export const CUSTOMER_BALANCE_REPORTS_API = {
  fetchCustomerBalanceReports: async ({
    page,
    customer_type,
    date_filter = "all",
    start_date = "",
    end_date = "",
  }: {
    page?: number;
    customer_type?: string;
    date_filter?: "all" | "range";
    start_date?: string;
    end_date?: string;
  }) => {
    const params = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
      ...(customer_type ? {customer_type} : {}),
      date_filter,
      ...(date_filter === "range" ? {start_date, end_date} : {}),
    });

    const response = await apiRequest.get(`/reports/customer-balance/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICustomerBalanceReport>;
  },

  fetchCustomerBalanceReportsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ICustomerBalanceReport>;
  },

  downloadCustomerBalanceReport: async (payload: ICustomerBalanceReportDownload) => {
    const response = await apiRequest.post(`reports/customer-balance-download/`, payload);
    return response.data as {message: string};
  },
};

export const VENDOR_BALANCE_REPORTS_API = {
  fetchVendorBalanceReports: async ({
    page,
    vendor_type,
    date_filter = "all",
    start_date = "",
    end_date = "",
  }: {
    page?: number;
    vendor_type?: string;
    date_filter?: "all" | "range";
    start_date?: string;
    end_date?: string;
  }) => {
    const params = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
      ...(vendor_type ? {vendor_type} : {}),
      date_filter,
      ...(date_filter === "range" ? {start_date, end_date} : {}),
    });

    const response = await apiRequest.get(`/reports/vendor-balance/?${params.toString()}`);

    return response.data as IPaginatedResponse<IVendorBalanceReport>;
  },

  fetchVendorBalanceReportsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IVendorBalanceReport>;
  },

  downloadVendorBalanceReport: async (payload: IVendorBalanceReportDownload) => {
    const response = await apiRequest.post(`reports/vendor-balance-download/`, payload);
    return response.data as {message: string};
  },
};

export const LEDGER_ACCOUNTS_REPORTS_API = {
  fetchLedgerReports: async ({
    page,
    search,
    date_filter,
    start_date = "",
    end_date = "",
  }: {
    page?: number;
    search?: string;
    date_filter?: string;
    start_date?: string;
    end_date?: string;
  }) => {
    const params = new URLSearchParams({
      ...(page ? {page: String(page)} : {}),
      ...(search ? {search} : {}),
      ...(date_filter ? {date_filter} : {}),
      ...(date_filter === "range" ? {start_date, end_date} : {}),
    });

    const response = await apiRequest.get(`reports/ledger-accounts/?${params.toString()}`);
    return response.data as IPaginatedResponse<ILedgerReportAccount>;
  },

  fetchLedgerReportsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ILedgerReportAccount>;
  },

  downloadLedgerReport: async (payload: ILedgerReportDownload) => {
    const response = await apiRequest.post(`reports/ledger-accounts-download/`, payload);
    return response.data as {message: string};
  },
};
