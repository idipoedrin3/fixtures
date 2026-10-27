import axios from "axios";
import type {IBudgetRecentActivityResponse, ITaxSummary} from "#/_types/api.types";

export const BUDGET_ACTIVITY_API = {
  fetchRecentActivity: async ({
    page = 1,
    pageSize = 10,
  }: {
    page?: number;
    pageSize?: number;
  } = {}): Promise<IBudgetRecentActivityResponse> => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    const response = await apiRequest.get(`budget/recent-activity/?${params.toString()}`);
    return response.data;
  },

  fetchRecentActivityFromUrl: async ({
    url,
  }: {
    url: string;
  }): Promise<IBudgetRecentActivityResponse> => {
    const response = await apiRequest.get(url);
    return response.data;
  },
};
export const BUDGET_INTELLIGENCE_API = {
  fetchIntelligence: async ({fiscalYearBaseUuid}: {fiscalYearBaseUuid: string}) => {
    const response = await apiRequest.get(`budget/intelligence/${fiscalYearBaseUuid}/`);
    return response.data as IBudgetIntelligence;
  },
};
import type {
  IExpense,
  IExpenseListItem,
  IExpenseLineItem,
  IExpenseFormData,
} from "#/_types/api.types";
import apiRequest, {baseURL, buildHeaders} from "#/_api/api-request";
import type {IJournalEntriesData} from "#/_components/common/tables/journal-entries-table";
import {
  getCurrentBranchId,
  getAllSelectedBranchUUIDs,
  getDefaultInstitutionId,
} from "#/_api/helpers";
import {MAIN_DOMAIN_URL} from "#/_constants";
import {
  ICustomer,
  ICustomerFormData,
  IPaginatedResponse,
  IUser,
  IUserInstitution,
  IVendorFormData,
  IVendor,
  IAccount,
  IAccountFormData,
  ISystemAccountRole,
  ITransaction,
  ITransactionFormData,
  IJournalEntryImportResponse,
  IInventoryItem,
  IInventoryItemFormData,
  IItemCategory,
  IItemCategoryFormData,
  IFiscalYear,
  IFixedAssetItem,
  IFixedAssetItemFormData,
  IDepreciationMethod,
  IAssetDisposal,
  IAssetDisposalFormData,
  IQuotationFormData,
  IPurchaseOrder,
  IPurchaseOrderLineItem,
  IPurchaseOrderFormData,
  ISalesOrderPayment,
  ISalesOrderPaymentFormData,
  IInvoice,
  IInvoiceLineItem,
  IInvoiceFormData,
  ICustomerPaymentRecord,
  ICustomerPaymentRecordFormData,
  IVendorPurchaseOrder,
  IVendorPurchaseOrderFormData,
  IVendorBill,
  IVendorBillLineItem,
  IVendorBillFormData,
  IVendorPayment,
  IVendorPaymentFormData,
  IVendorCredit,
  IVendorCreditFormData,
  IRequisition,
  IRequisitionType,
  IRequisitionTypeFormData,
  UserProfile,
  ISalePersonFormData,
  ISalesPerson,
  IPaymentTerm,
  IPaymentTermFormData,
  IItemUnitOfMeasureFormData,
  IItemUnitOfMeasure,
  Currency,
  ISalesPersonCommission,
  ITransactionEntry,
  IAssetCategory,
  IAssetCategoryFormData,
  IAssetClass,
  ITaxType,
  ITaxTypeFormData,
  ITaxRule,
  ITaxRuleFormData,
  ITaxDependency,
  ITaxDependencyFormData,
  ITaxSchedule,
  ITaxScheduleFormData,
  ITax,
  ITaxAccountRead,
  ITaxFormData,
  IBank,
  IBankFormData,
  IInstitutionSupportedBank,
  IBranchAllocation,
  IBranchAllocationFormData,
  IBranchInventoryItem,
  IBranchInventoryItemUnitOfMeasure,
  IBalanceAdjustment,
  IReport,
  IReportDownloadData,
  ICreditNote,
  ICreditNoteLineItem,
  ICreditNoteFormData,
  IDebitNote,
  IDebitNoteFormData,
  ICashBookRequisition,
  ICashBookRequisitionFormData,
  ICashBookCredit,
  ICashBookCreditFormData,
  IDepreciation,
  IDepreciationItemFormData,
  IBusinessDocument,
  IBusinessDocumentCategory,
  IQuotation,
  IQuotationLineItem,
  IFiscalYearFormData,
  IAssetDisposalType,
  IBankStatement,
  IBankStatementFormData,
  IBankStatementTransactionFormData,
  IBankStatementTransaction,
  IDocumentCatergory,
  IDocumentCatergoryFormData,
  IReturnReason,
  IReturnReasonFormData,
  IInventoryItemReturn,
  IInventoryItemReturnFormData,
  ReturnedItem,
  ITaxReturn,
  ITaxReturnFormData,
  ITaxPayment,
  ITaxPaymentFormData,
  IVendorInsights,
  IContentType,
  IObject,
  Branch,
  IBranchSupportedCurrency,
  IBranchFormData,
  IInventoryItemPriceChange,
  IRecurringInvoice,
  IRecurringInvoiceFormData,
  IRecurringInvoiceLineItemFormData,
  IRecurringInvoiceLineItem,
  buildVendorPurchaseOrderPayload,
  Permission,
  IStaffFormData,
  IIndustry,
  IBranchInventoryItemUpdatePayload,
  ISystemNotification,
  IInstitutionNotificationSetting,
  INotificationSettingInput,
  IRequisitionPayload,
  ICustomerDepositAllocation,
  IApprovalDocumentCategory,
  IRequisitionGeneralStatistics,
  IRequisitionDashboardSummary,
  IRequisitionPayment,
  IRequisitionRecentActivityResponse,
  ICommonlyUsedRequisitionType,
  IRequisitionTaxPreview,
  IMarkRequisitionAsPaidPayload,
  IInventoryItemUnitOfMeasure,
  IPublicRequisitionPreview,
  IRequisitionListItem,
  IRequisitionAttachment,
  IStockLayer,
  IStockMovementListItem,
} from "#/_types/api.types";
import {toFileEntry} from "#/_lib/file-utils";
import {
  ForgotPasswordRequest,
  IDepreciationEntry,
  IDepreciationSchedulePayload,
  IDepreciationSummaryPayload,
  IDepreciationSummaryResponse,
  ILoginResponse,
  IReversalEntry,
} from "#/_types/types.utils";
import {getSliceState} from "@/store/get-slice-state";
import {InstitutionData} from "../(dashboard)/inst-setup/setup-context";
import {
  ICalculateAmountWithTaxesRequest,
  ICalculateAmountWithTaxesResponse,
  IPrepaymentAllocation,
  IReportDownloadBody,
  IVendorBalanceAdjustment,
} from "../_types/approvals.types";
import {toParams} from "../_lib/utils";
import {IPermissionCategory, IProfile} from "./services/user.service";
import {
  IBudgetIntelligence,
  IInstitutionSupportedCurrency,
  IRequisitionArrear,
} from "../_types/email";

export type FileDownloadParams = {
  url: string;
  expectedMime?: string;
  timeout?: number;
  method?: "GET" | "POST";
  body?: Record<string, any>;
};

export function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();

  window.URL.revokeObjectURL(url);
}

export async function downloadFileApi({
  url,
  expectedMime,
  timeout = 30000,
  method = "GET",
  body,
}: FileDownloadParams): Promise<Blob> {
  const fullUrl = url.startsWith("http") || url.startsWith("https") ? url : `${baseURL}/${url}`;

  try {
    const response = await axios({
      method,
      url: fullUrl,
      headers: buildHeaders({
        initialHeaders: method === "POST" ? {"Content-Type": "application/json"} : {},
      }),
      data: method === "POST" ? body : undefined,
      responseType: "blob",
      timeout,
    });

    const blob = response.data as Blob;

    if (blob.size === 0) {
      throw new Error("Downloaded file is empty.");
    }

    if (expectedMime && blob.type && !blob.type.includes(expectedMime)) {
      throw new Error(`Downloaded file is not a valid ${expectedMime}.`);
    }

    return blob;
  } catch (error: any) {
    if (error.response?.status === 404) {
      throw new Error("File not found.");
    }

    if (error.response?.status === 403) {
      throw new Error("You do not have permission to download this file.");
    }

    if (error.response?.status === 401) {
      throw new Error("Authentication required. Please log in again.");
    }

    if (error.code === "ECONNABORTED") {
      throw new Error("Download timed out. Please try again.");
    }

    throw new Error(error.message || "Failed to download file.");
  }
}

export const SYSTEM_NOTIFICATIONS_API = {
  fetchAll: async ({search = "", page = 1}: {search?: string; page?: number} = {}) => {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    params.append("page", String(page));
    const response = await apiRequest.get(`system/system-notifications/?${params.toString()}`);
    return response.data as IPaginatedResponse<ISystemNotification>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ISystemNotification>;
  },
};

export const INSTITUTION_NOTIFICATIONS_API = {
  fetchInstitutionSettings: async () => {
    const response = await apiRequest.get(`institution/notifications/`);
    return response.data as IPaginatedResponse<IInstitutionNotificationSetting>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IInstitutionNotificationSetting>;
  },

  createOrUpdate: async (payload: INotificationSettingInput[]) => {
    const response = await apiRequest.post(`institution/notifications/`, payload);
    return response.data;
  },

  patch: async (base_uuid: string, payload: Partial<INotificationSettingInput>) => {
    const response = await apiRequest.patch(`institution/notifications/${base_uuid}/`, payload);
    return response.data;
  },
};

export const INSTITUTIONS_API = {
  async create(payload: InstitutionData) {
    const response = await apiRequest.post("institution/", payload);

    return response.data;
  },
  getInstitutionById: async (InstitutionId: string) => {
    const response = await apiRequest.get(`institution/${InstitutionId}/`);

    return response.data as IUserInstitution;
  },
  createBranch: async ({data}: {data: any}) => {
    try {
      const response = await apiRequest.post(`institution/branch/`, data);

      return response.data;
    } catch (error) {
      throw error;
    }
  },
  fetchInstitutionBranches: async ({search}: {search?: string} = {}) => {
    try {
      const institutionId = getDefaultInstitutionId();

      if (!institutionId) {
        throw new Error("No institution ID found");
      }
      const params = new URLSearchParams();

      if (search) params.append("search", search);
      const queryString = params.toString();
      const response = await apiRequest.get(`institution/branch/?${queryString}`);

      return response.data;
    } catch (error) {
      throw error;
    }
  },
  fetchInstitutionBranchesFromUrl: async ({url}: {url: string}) => {
    try {
      const response = await apiRequest.get(url);

      return response.data;
    } catch (error) {
      throw error;
    }
  },
  fetchInstitutionRoles: async ({search}: {search?: string} = {}) => {
    try {
      const params = new URLSearchParams();

      if (search) params.append("search", search);
      const queryString = params.toString();
      const response = await apiRequest.get(`user/role/?${queryString}`);

      return response.data;
    } catch (error) {
      throw error;
    }
  },
  fetchInstitutionRolesFromUrl: async ({url}: {url: string}) => {
    try {
      const response = await apiRequest.get(url);

      return response.data;
    } catch (error) {
      throw error;
    }
  },

  institutionUpdate: async (institution_uuid: string, institution_data: any) => {
    try {
      let formData: any;

      if (institution_data.institution_logo) {
        formData = new FormData();

        Object.keys(institution_data).forEach((key) => {
          const value = institution_data[key];

          if (value !== null && value !== undefined) {
            if (value instanceof File) {
              formData.append(key, value);
            } else {
              formData.append(key, value.toString());
            }
          }
        });
      } else {
        formData = institution_data;
      }

      const response = await apiRequest.patch(`institution/${institution_uuid}/`, formData);

      return response.data;
    } catch (error) {
      throw error;
    }
  },
};

export const AUTH_API = {
  loginWithEmailAndPassword: async (
    identifier: string,
    password: string,
    institution_uuid?: string,
  ) => {
    const payload = {identifier, password, ...(institution_uuid ? {institution_uuid} : {})};
    const response = await apiRequest.post("user/login/", payload);
    const responseData = response.data;

    return {
      ...responseData,
      InstitutionsAttached: response.data.institutions_attached,
    } as ILoginResponse;
  },

  switchInstitution: async (institutionBaseUuid: string, currentRefreshToken: string) => {
    const response = await apiRequest.post("user/switch-to-institution/", {
      institution_base_uuid: institutionBaseUuid,
      current_refresh_token: currentRefreshToken,
    });

    return response.data as ILoginResponse;
  },

  forgotPassword: async (email: string, frontendUrl?: string) => {
    const payload: ForgotPasswordRequest = {
      email,
      ...(frontendUrl && {frontend_url: frontendUrl}),
    };

    await apiRequest.post("/user/forgot-password", payload);
  },

  verifyResetToken: async (token: string) => {
    await apiRequest.post("/user/verify-token", {token});
  },
  resetPassword: async (token: string, newPassword: string) => {
    await apiRequest.post("/user/reset-password", {
      token,
      new_password: newPassword,
    });
  },

  refreshTokens: async ({refreshToken}: {refreshToken: string}) => {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL || `${MAIN_DOMAIN_URL}/api`}/user/token/refresh/`,
      {refresh: refreshToken},
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    return response.data as ILoginResponse;
  },

  changeEmailAndResendOtp: async ({
    old_email,
    new_email,
  }: {
    old_email: string;
    new_email: string;
  }) => {
    if (!old_email || !new_email) {
      throw new Error("Both the old and new emails are required!");
    }
    const response = await apiRequest.post("user/change-email-and-resend-otp/", {
      old_email,
      new_email,
    });

    return response;
  },

  resendOtp: async ({email, mode}: {email: string; mode: "otp" | "password_link"}) => {
    const response = await apiRequest.post(`user/resend-otp/?mode=${mode}`, {email});

    return response;
  },

  verifyOtp: async ({email, otp}: {email: string; otp: string}) => {
    const response = await apiRequest.post("user/verify-otp/", {email, otp});

    return response;
  },

  logout: async (refreshToken: string) => {
    await apiRequest.post("user/logout/", {refresh: refreshToken});
  },
};

export const REPORTS_API = {
  getBalanceSheet: async (body: {
    statement_type: "balance_sheet_statement";
    branches?: string[];
    fiscal_years?: {fiscal_year_base_uuid: string}[];
    custom_dates?: {start_date: string; end_date: string}[];
  }) => {
    const response = await apiRequest.post(`/accounts/financial-reports/`, body);
    return response.data;
  },

  getIncomeStatement: async (body: {
    statement_type: "income_statement";
    branches?: string[];
    fiscal_years?: {fiscal_year_base_uuid: string}[];
    custom_dates?: {start_date: string; end_date: string}[];
  }) => {
    const response = await apiRequest.post(`/accounts/financial-reports/`, body);
    return response.data;
  },

  getTrialBalance: async (body: {
    statement_type: "trial_balance_statement";
    branches?: string[];
    fiscal_years?: {fiscal_year_base_uuid: string}[];
    custom_dates?: {start_date: string; end_date: string}[];
  }) => {
    const response = await apiRequest.post(`/accounts/financial-reports/`, body);
    return response.data;
  },

  getCashFlowStatement: async (body: {
    statement_type: "cash_flow_statement";
    branches?: string[];
    fiscal_years?: {fiscal_year_base_uuid: string}[];
    custom_dates?: {start_date: string; end_date: string}[];
    cash_flow_method?: "direct" | "indirect";
  }) => {
    const response = await apiRequest.post(`/accounts/financial-reports/`, body);
    return response.data;
  },

  downloadReport: async (body: IReportDownloadBody): Promise<Blob> => {
    return downloadFileApi({
      url: "accounts/financial-reports/download/",
      expectedMime: body.file_type === "pdf" ? "pdf" : "spreadsheet",
      method: "POST",
      body,
    });
  },
};

export const USERS_API = {
  fetchUserTasks: async () => {
    try {
      return await apiRequest.get("workflow/task/");
    } catch (error) {
      throw error;
    }
  },

  fetchUserById: async (userId: number): Promise<IUser | null> => {
    try {
      const response = await apiRequest.get(`user/${userId}/`);

      return response.data as IUser;
    } catch {
      return null;
    }
  },
  fetchUserAttachedInstitutions: async () => {
    const response = await apiRequest.get("user/institutions/");

    return (response.data.institutions ?? []) as Array<{
      name: string;
      base_uuid: string;
      reference_code: string;
    }>;
  },

  fetchUsers: async ({search}: {search?: string}) => {
    const params = new URLSearchParams();

    if (search) params.append("search", search);
    const queryString = params.toString();
    const url = queryString ? `user/?${queryString}` : "user/";
    const response = await apiRequest.get(url);

    return {
      results: response.data as IUser[],
      next: null,
      previous: null,
      count: response.data.length,
    } as IPaginatedResponse<IUser>;
  },

  fetchUsersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IUser>;
  },
  getProfiles: async () => {
    const response = await apiRequest.get(`/institution/profile/`);
    return response.data as IPaginatedResponse<UserProfile>;
  },

  fetchCurrentUserSettings: async () => {
    const response = await apiRequest.get("user/settings/");
    return response.data as {
      base_uuid: string;
      fullname: string;
      email: string;
      gender: string;
      signature_base64: string | null;
      profile_photo_base64: string | null;
    };
  },
  updateCurrentUserSettings: async (updateData: {
    fullname?: string;
    gender?: string;
    signature_base64?: string | null;
    profile_photo_base64?: string | null;
  }) => {
    const response = await apiRequest.patch("user/settings/", updateData);
    return response.data as {
      base_uuid: string;
      fullname: string;
      email: string;
      gender: string;
      signature_base64: string | null;
      profile_photo_base64: string | null;
    };
  },
  updateUser: async ({
    userId,
    updateData,
  }: {
    userId: string;
    updateData: {
      fullname?: string;
      email?: string;
      roles_ids?: number[];
      // Note: is_active, is_staff, is_email_verified, is_password_verified are read-only fields
      // and cannot be updated through this endpoint
    };
  }) => {
    const response = await apiRequest.patch(`user/${userId}/`, updateData);

    return response.data as IUser;
  },
  changePassword: async (passwordData: {old_password: string; new_password: string}) => {
    const response = await apiRequest.post("user/auth/change-password/", passwordData);

    return response;
  },
};

export const CUSTOMERS_API = {
  fetchCustomers: async (params: Record<string, string | number | boolean> = {}) => {
    const {page, ...rest} = params;

    const urlParams = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
      ...Object.fromEntries(
        Object.entries(rest)
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => [k, String(v)]),
      ),
      ...(page ? {page: String(page)} : {page: "1"}),
    });

    const response = await apiRequest.get(`/customers/?${urlParams.toString()}`);
    return response.data as IPaginatedResponse<ICustomer>;
  },

  fetchCustomersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICustomer>;
  },

  createCustomer: async ({customerData}: {customerData: ICustomerFormData | FormData}) => {
    const response = await apiRequest.post(`customers/`, customerData);

    return response.data as ICustomer;
  },

  updateCustomer: async ({
    customerUuid,
    customerData,
  }: {
    customerUuid: string;
    customerData: ICustomerFormData | FormData;
  }) => {
    const response = await apiRequest.patch(`customers/detail/${customerUuid}/`, customerData);

    return response.data as ICustomer;
  },

  deleteCustomer: async ({customerUuid}: {customerUuid: string}) => {
    await apiRequest.delete(`customers/detail/${customerUuid}/`);
  },

  fetchCustomerById: async ({customerUuid}: {customerUuid: string}) => {
    const response = await apiRequest.get(`customers/detail/${customerUuid}/`);

    return response.data as ICustomer;
  },

  fetchUserCurrency: async () => {
    const response = await apiRequest.get("user/currencies");

    return response.data as IPaginatedResponse<Currency>;
  },

  fetchBalanceAdjustments: async ({
    base_uuid,
    balance_adjusted,
  }: {
    base_uuid: string;
    balance_adjusted?: string;
  }) => {
    const params = new URLSearchParams({
      ...(balance_adjusted ? {balance_adjusted} : {}),
    });
    const response = await apiRequest.get(
      `customers/balance-adjustments/${base_uuid}/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IBalanceAdjustment>;
  },

  fetchBalanceAdjustmentsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBalanceAdjustment>;
  },

  downloadBulkUploadTemplate: async ({
    file_format = "excel",
  }: {
    file_format?: "excel" | "csv";
  }): Promise<Blob> => {
    return downloadFileApi({
      url: `bulk_upload/?template_type=customer&file_format=${file_format}`,
      expectedMime: file_format === "csv" ? "csv" : "spreadsheet",
      method: "GET",
    });
  },
  sendDemandNotice: async ({invoice_uuids}: {invoice_uuids: string[]}) => {
    const response = await apiRequest.post(`customers/demand-notice/`, {
      invoice_uuids,
    });

    return response.data;
  },
};

export const QUOTATIONS_API = {
  fetchQuotations: async (
    query: {
      page?: number;
      search?: string;
      ordering?: string;
      customer__base_uuid?: string;
      status?: string;
    } = {},
  ) => {
    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      ...query,
    });

    const response = await apiRequest.get(`/customers/quotations/?${params.toString()}`);

    return response.data as IPaginatedResponse<IQuotation>;
  },

  fetchQuotationsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IQuotation>;
  },

  createQuotation: async ({quotationData}: {quotationData: IQuotationFormData}) => {
    const response = await apiRequest.post(`customers/quotations/`, {
      ...quotationData,
    });

    return response.data as IQuotation;
  },

  updateQuotation: async ({
    quotationUuid,
    quotationData,
  }: {
    quotationUuid: string;
    quotationData: IQuotationFormData;
  }) => {
    const response = await apiRequest.patch(`customers/quotations/detail/${quotationUuid}/`, {
      ...quotationData,
    });

    return response.data as IQuotation;
  },

  deleteQuotation: async ({quotationUuid}: {quotationUuid: string}) => {
    await apiRequest.delete(`customers/quotations/detail/${quotationUuid}/`);
  },

  fetchQuotationById: async ({quotationUuid}: {quotationUuid: string}) => {
    const response = await apiRequest.get(`customers/quotations/detail/${quotationUuid}/`);

    return response.data as IQuotation;
  },
  fetchQuotationLineItems: async ({
    quotationBaseUuid,
    page = 1,
  }: {
    quotationBaseUuid: string;
    page?: number;
  }) => {
    const response = await apiRequest.get(
      `customers/quotation-line-items/${quotationBaseUuid}/?page=${page}`,
    );

    return response.data as IPaginatedResponse<IQuotationLineItem>;
  },
  fetchQuotationLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IQuotationLineItem>;
  },
  sendResendQuotation: async ({quotationUuid}: {quotationUuid: string}) => {
    await apiRequest.post(`customers/quotations/${quotationUuid}/send/`, {
      base_uuid: quotationUuid,
    });
  },
  downloadQuotationPDF: async ({invoiceUuid}: {invoiceUuid: string}) => {
    return downloadFileApi({
      url: `customers/quotation-report-download/${invoiceUuid}`,
      expectedMime: "pdf",
    });
  },
};

// export const SYSTEM_GROUP_ACCOUNT_TYPES_API = {
//   fetchSystemGroupAccountTypes: async ({page = 1, search}: {page?: number; search?: string}) => {
//     const params = new URLSearchParams({page: String(page)});

//     if (search) params.append("search", search);
//     const response = await apiRequest.get(
//       `/accounts/system/group-account-types/?${params.toString()}`,
//     );

//     return response.data as IPaginatedResponse<ISystemGroupAccountType>;
//   },

//   fetchSystemGroupAccountTypesFromUrl: async ({url}: {url: string}) => {
//     const response = await apiRequest.get(url);

//     return response.data as IPaginatedResponse<ISystemGroupAccountType>;
//   },
// };

export const VENDORS_API = {
  fetchVendors: async ({
    search = "",
    page = 1,
    vendor_type = "",
    ordering = "",
    without_requisition_beneficiary = false,
    has_purchase_orders,
    has_vendor_bills,
    // institutionId,
  }: {
    search?: string;
    page?: number;
    vendor_type?: string;
    ordering?: string;
    without_requisition_beneficiary?: boolean;
    has_purchase_orders?: boolean;
    has_vendor_bills?: boolean;
    // institutionId: number;
  }) => {
    const params = new URLSearchParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (vendor_type) params.append("vendor_type", vendor_type);
    if (without_requisition_beneficiary) {
      params.append("without_requisition_beneficiary", "true");
    }
    if (has_purchase_orders !== undefined) {
      params.append("has_purchase_orders", String(has_purchase_orders));
    }
    if (has_vendor_bills !== undefined) {
      params.append("has_vendor_bills", String(has_vendor_bills));
    }
    params.append("page", page.toString());
    const response = await apiRequest.get(`vendors/?${params.toString()}`);

    return response.data as IPaginatedResponse<IVendor>;
  },

  fetchVendorsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IVendor>;
  },

  fetchVendorById: async ({baseUuuid}: {baseUuuid: string}) => {
    const response = await apiRequest.get(`vendors/detail/${baseUuuid}/`);

    return response.data as IVendor;
  },

  createVendor: async ({data}: {data: IVendorFormData}) => {
    const response = await apiRequest.post(`vendors/`, {...data});

    return response.data as IVendor;
  },

  updateVendor: async ({baseUuuid, data}: {baseUuuid: string; data: IVendorFormData}) => {
    const response = await apiRequest.patch(`vendors/detail/${baseUuuid}/`, data);

    return response.data as IVendor;
  },

  deleteVendor: async ({baseUuuid}: {baseUuuid: string}) => {
    const response = await apiRequest.delete(`vendors/detail/${baseUuuid}/`);

    return response.data;
  },

  insights: async ({baseUuuid}: {baseUuuid: string}) => {
    const response = await apiRequest.get(`vendors/detail/${baseUuuid}/insights/`);

    return response.data as IVendorInsights;
  },

  fetchBalanceAdjustments: async ({
    baseUuid,
    balance_adjusted,
  }: {
    baseUuid: string;
    balance_adjusted?: string;
  }) => {
    const params = new URLSearchParams({
      ...(balance_adjusted ? {balance_adjusted} : {}),
    });
    const response = await apiRequest.get(
      `vendors/balance-adjustments/${baseUuid}/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IVendorBalanceAdjustment>;
  },

  fetchBalanceAdjustmentsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IVendorBalanceAdjustment>;
  },

  downloadBulkUploadTemplate: async ({
    file_format = "excel",
  }: {
    file_format?: "excel" | "csv";
  }): Promise<Blob> => {
    return downloadFileApi({
      url: `bulk_upload/?template_type=vendor&file_format=${file_format}`,
      expectedMime: file_format === "csv" ? "csv" : "spreadsheet",
      method: "GET",
    });
  },
};

export const ACCOUNTS_API = {
  async fetchObjects({
    account_uuid,
    search,
    page,
  }: {
    account_uuid?: string;
    search?: string;
    page?: number;
  }) {
    if (!account_uuid || account_uuid === "undefined") {
      return {results: [], count: 0, next: null, previous: null};
    }
    const params = new URLSearchParams();
    if (page) params.append("page", page.toString());
    if (search) params.append("search", search);
    const res = await apiRequest.get(
      `accounts/transaction-object/${account_uuid}/?${params.toString()}`,
    );
    return res.data as IPaginatedResponse<any>;
  },
  async fetchObjectsFromUrl({url}: {url: string}) {
    const res = await apiRequest.get(url);

    return res.data as IPaginatedResponse<any>;
  },
  updateOpeningBalance: async (data: {account_uuid: string; amount: number}) => {
    const res = apiRequest.post("accounts/account-opening-balance-update/", data);

    return res;
  },
  fetchAccounts: async ({
    page,
    search,
    has_children,
    get_asset_based_account,
    linked_to_cash_account,
    has_reconciliation_session,
    show_top_level,
    account_role,
    account_role_code,
    system_group_account_type_choice,
    currency,
    exclude_currency,
    ordering,
  }: {
    page?: number;
    search?: string;
    status?: string;
    payment_status?: string;
    goods_received_note_status?: string;
    has_children?: boolean;
    show_top_level?: boolean;
    get_asset_based_account?: boolean;
    linked_to_cash_account?: boolean;
    has_reconciliation_session?: boolean;
    account_role?: string[];
    account_role_code?: string[];
    system_group_account_type_choice?: string[];
    currency?: number;
    exclude_currency?: number;
    ordering?: string;
  }) => {
    const params = new URLSearchParams();

    if (search) params.append("search", search);
    if (page) params.append("page", page.toString());
    if (ordering) params.append("ordering", ordering.toString());
    if (currency) params.append("currency", currency.toString());
    if (exclude_currency) {
      params.append("exclude_currency", exclude_currency.toString());
    }
    if (has_children !== undefined) params.append("has_children", has_children.toString());
    if (show_top_level !== undefined) params.append("show_top_level", show_top_level.toString());
    if (get_asset_based_account !== undefined)
      params.append("get_asset_based_account", get_asset_based_account.toString());
    if (linked_to_cash_account !== undefined)
      params.append("linked_to_cash_account", linked_to_cash_account.toString());
    if (has_reconciliation_session !== undefined)
      params.append("has_reconciliation_session", has_reconciliation_session.toString());
    if (account_role?.length) {
      account_role.forEach((roleId) => params.append("account_role", roleId));
    }
    if (account_role_code?.length) {
      account_role_code.forEach((roleCode) => params.append("account_role_code", roleCode));
    }
    if (system_group_account_type_choice?.length) {
      system_group_account_type_choice.forEach((type) =>
        params.append("system_group_account_type_choice", type),
      );
    }

    const response = await apiRequest.get(`accounts/accounts/?${params.toString()}`);

    return response.data as IPaginatedResponse<IAccount>;
  },

  fetchAccountsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IAccount>;
  },

  fetchAccountById: async ({accountId}: {accountId: string}) => {
    const response = await apiRequest.get(`accounts/accounts/${accountId}/`);

    return response.data as IAccount;
  },

  createAccount: async ({data}: {data: IAccountFormData}) => {
    const response = await apiRequest.post(`accounts/accounts/`, data);

    return response.data as IAccount;
  },

  updateAccount: async ({
    accountId,
    data,
  }: {
    accountId: string;
    data: Partial<IAccountFormData>;
  }) => {
    const response = await apiRequest.patch(`accounts/accounts/${accountId}/`, data);

    return response.data as IAccount;
  },

  deleteAccount: async ({accountId}: {accountId: string}) => {
    const response = await apiRequest.delete(`accounts/accounts/${accountId}/`);

    return response.data;
  },
};

export const SYSTEM_ACCOUNT_ROLES_API = {
  fetchAccountRoles: async ({
    page = 1,
    search,
    used_by_institution,
  }: {
    page?: number;
    search?: string;
    used_by_institution?: boolean;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (used_by_institution !== undefined) {
      params.append("used_by_institution", used_by_institution.toString());
    }
    const response = await apiRequest.get(`system/account-roles/?${params.toString()}`);

    return response.data as ISystemAccountRole;
  },

  fetchAccountRolesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as ISystemAccountRole;
  },
};

export const ITEM_CATEGORIES_API = {
  fetchItemCategories: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      page: page.toString(),
    });

    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`items/item-categories/?${params.toString()}`);

    return response.data as IPaginatedResponse<IItemCategory>;
  },

  fetchItemCategoriesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IItemCategory>;
  },

  createItemCategory: async (data: IItemCategoryFormData | IItemCategoryFormData[]) => {
    const dataArray = Array.isArray(data) ? data : [data];

    const response = await apiRequest.post(`items/item-categories/`, dataArray);

    return Array.isArray(data) ? response.data : response.data[0];
  },

  updateItemCategory: async ({
    categoryUuid,
    data,
  }: {
    categoryUuid: string;
    data: IItemCategoryFormData;
  }) => {
    const response = await apiRequest.patch(`items/item-categories/detail/${categoryUuid}/`, {
      ...data,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IItemCategory;
  },

  deleteItemCategory: async ({categoryUuid}: {categoryUuid: string}) => {
    await apiRequest.delete(`items/item-categories/detail/${categoryUuid}/`);
  },

  fetchItemCategoryById: async ({categoryUuid}: {categoryUuid: string}) => {
    const response = await apiRequest.get(`items/item-categories/detail/${categoryUuid}/`);

    return response.data as IItemCategory;
  },
  bulkUploadItemCategories: async (data: FormData) => {
    const response = await apiRequest.post(`bulk_upload/`, data);

    return response.data;
  },
};

export const INVENTORY_ITEMS_API = {
  fetchItemStockLayers: async (query: {
    inventory_item_uuid?: string;
    issue_date_period?: string;
    issue_date_to?: string;
    issue_date_from?: string;
    ordering?: string;
    page?: number;
  }) => {
    const params = new URLSearchParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(","),
      ...Object.fromEntries(
        Object.entries(query).filter(([_, v]) => v !== undefined && v !== null && v !== ""),
      ),
    });

    const response = await apiRequest.get(
      `items/inventory-item-stock-layers/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<any>;
  },

  fetchItemStockLayersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<any>;
  },

  fetchAllItemStockLayers: async (query: {inventory_item_uuid?: string}) => {
    if (!query.inventory_item_uuid) {
      return {count: 0, next: null, previous: null, results: []};
    }

    const response = await apiRequest.get(`items/${query.inventory_item_uuid}/stock-layers/`);

    const warehouseLayers = response.data.warehouse.map((layer: any) => ({
      ...layer,
      location_type: "WAREHOUSE",
      location_name: "Main Warehouse",
    }));

    const branchLayers = response.data.branches.flatMap((group: any) =>
      group.stock_layers.map((layer: any) => ({
        ...layer,
        recieved_date: layer.received_date,
        location_type: "BRANCH",
        location_name: group.branch.branch_name,
      })),
    );

    const results = [...warehouseLayers, ...branchLayers];

    return {
      count: results.length,
      next: null,
      previous: null,
      results,
    } as IPaginatedResponse<any>;
  },

  fetchInventoryItemPriceHistory: async ({
    item_base_uuid,
    page,
    issue_date_from,
    issue_date_to,
    ordering,
  }: {
    item_base_uuid?: string;
    page?: number;
    issue_date_from?: string;
    issue_date_to?: string;
    ordering?: string;
  }) => {
    if (!item_base_uuid || item_base_uuid === "undefined") {
      return {results: [], count: 0, next: null, previous: null};
    }

    const params = new URLSearchParams();

    params.append("branch_uuids", getAllSelectedBranchUUIDs().join(",") || "");
    if (page) params.append("page", page.toString());
    if (issue_date_from) params.append("issue_date_from", issue_date_from);
    if (issue_date_to) params.append("issue_date_to", issue_date_to);
    if (ordering) params.append("ordering", ordering);

    const response = await apiRequest.get(
      `items/inventory-item-price-change/${item_base_uuid}/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IInventoryItemPriceChange>;
  },

  fetchInventoryItemPriceHistoryFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IInventoryItemPriceChange>;
  },

  fetchInventoryItems: async (args: Record<string, any> & {page?: number}) => {
    const {page = 1, ...query} = args;

    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      page: String(page),
      ...query,
    });
    const response = await apiRequest.get(`items/inventory-items/?${params.toString()}`);
    return response.data as IPaginatedResponse<IInventoryItem>;
  },

  fetchInventoryItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IInventoryItem>;
  },

  createInventoryItem: async ({data}: {data: IInventoryItemFormData}) => {
    const response = await apiRequest.post(`items/inventory-items/`, data);

    return response.data as IInventoryItem;
  },

  updateInventoryItem: async ({
    itemUuid,
    data,
  }: {
    itemUuid: string;
    data: Partial<IInventoryItemFormData>;
  }) => {
    const response = await apiRequest.patch(`items/inventory-items/detail/${itemUuid}/`, data);
    return response.data as IInventoryItem;
  },

  deleteInventoryItem: async ({itemUuid}: {itemUuid: string}) => {
    await apiRequest.delete(`items/inventory-items/detail/${itemUuid}/`);
  },
  fetchInventoryItemById: async ({itemUuid}: {itemUuid: string}) => {
    const response = await apiRequest.get(`items/inventory-items/detail/${itemUuid}/`);
    return response.data as IInventoryItem;
  },

  fetchItemStockLogs: async ({
    page = 1,
    ...query
  }: Record<string, string | number | undefined> & {page?: number}) => {
    const params = new URLSearchParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(","),
      ...Object.fromEntries(
        Object.entries(query)
          .filter(([_, value]) => value !== undefined && value !== "")
          .map(([key, value]) => [key, String(value)]),
      ),
      page: String(page),
    });

    const response = await apiRequest.get(`items/stock/movements/?${params.toString()}`);

    return response.data as IPaginatedResponse<any>;
  },

  fetchItemStockLogsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<any>;
  },
  bulkUploadInventoryItems: async (data: FormData) => {
    const url = `items/inventory-items/bulk-upload/`;
    const response = await apiRequest.post(url, data);

    return response.data;
  },

  fetchStockLayerById: async ({layerUuid}: {layerUuid: string}): Promise<IStockLayer> => {
    const params = new URLSearchParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(","),
    });

    const response = await apiRequest.get(
      `items/inventory-item-stock-layers/${layerUuid}/?${params.toString()}`,
    );

    return response.data as IStockLayer;
  },
};

export const FIXED_ASSET_ITEMS_API = {
  fetchFixedAssetItems: async ({
    page = 1,
    search,
    get_disposed_assets = false,
    asset_class_base_uuid,
    asset_category_base_uuid,
  }: {
    page?: number;
    search?: string;
    get_disposed_assets?: boolean;
    asset_class_base_uuid?: string;
    asset_category_base_uuid?: string;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      get_disposed_assets: get_disposed_assets.toString(),
    });

    if (search) params.append("search", search);
    if (asset_class_base_uuid) params.append("asset_class_base_uuid", asset_class_base_uuid);
    if (asset_category_base_uuid)
      params.append("asset_category_base_uuid", asset_category_base_uuid);

    const response = await apiRequest.get(`fixed_assets/fixed-assets/?${params.toString()}`);
    return response.data as IPaginatedResponse<IFixedAssetItem>;
  },

  fetchFixedAssetItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IFixedAssetItem>;
  },

  createFixedAssetItem: async ({data}: {data: IFixedAssetItemFormData}) => {
    const response = await apiRequest.post(`fixed_assets/fixed-assets/`, data);

    return response.data as IFixedAssetItem;
  },

  updateFixedAssetItem: async ({
    itemUuid,
    data,
  }: {
    itemUuid: string;
    data: Partial<IFixedAssetItemFormData>;
  }) => {
    const response = await apiRequest.patch(`fixed_assets/fixed-assets/${itemUuid}/`, data);

    return response.data as IFixedAssetItem;
  },

  processFixedAssetJournals: async ({
    itemUuid,
    purchaseDate,
    purchasePrice,
    salvageValue,
    usefulLife,
    openingBalanceAccount,
  }: {
    itemUuid: string;
    purchaseDate: string;
    purchasePrice: string;
    salvageValue?: string;
    usefulLife?: string | null;
    openingBalanceAccount?: string | null;
  }) => {
    const response = await apiRequest.post(
      `fixed_assets/fixed-assets/${itemUuid}/process-journals/`,
      {
        purchase_date: purchaseDate,
        purchase_price: purchasePrice,
        salvage_value: salvageValue,
        useful_life: usefulLife,
        opening_balance_account: openingBalanceAccount,
      },
    );

    return response.data as IFixedAssetItem;
  },

  deleteFixedAssetItem: async ({itemUuid}: {itemUuid: string}) => {
    await apiRequest.delete(`fixed_assets/fixed-assets/${itemUuid}/`);
  },

  fetchFixedAssetItemById: async ({itemUuid}: {itemUuid: string}) => {
    const response = await apiRequest.get(`fixed_assets/fixed-assets/${itemUuid}/`);

    return response.data as IFixedAssetItem;
  },
};

export const ASSET_CATEGORIES_API = {
  fetchAssetCategories: async ({
    page = 1,
    search,
    asset_class_base_uuid,
  }: {
    page?: number;
    search?: string;
    asset_class_base_uuid?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (asset_class_base_uuid) params.append("asset_class_base_uuid", asset_class_base_uuid);

    const response = await apiRequest.get(`/fixed_assets/categories/?${params.toString()}`);

    return response.data as IPaginatedResponse<IAssetCategory>;
  },

  fetchAssetCategoriesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IAssetCategory>;
  },

  createAssetCategory: async ({data}: {data: IAssetCategoryFormData}) => {
    const response = await apiRequest.post(`/fixed_assets/categories/`, data);

    return response.data as IAssetCategory;
  },

  updateAssetCategory: async ({
    categoryUuid,
    data,
  }: {
    categoryUuid: string;
    data: IAssetCategoryFormData;
  }) => {
    const response = await apiRequest.patch(`/fixed_assets/categories/${categoryUuid}/`, data);

    return response.data as IAssetCategory;
  },

  // Delete a category
  deleteAssetCategory: async ({categoryUuid}: {categoryUuid: string}) => {
    await apiRequest.delete(`/fixed_assets/categories/${categoryUuid}/`);
  },

  // Fetch single category details
  fetchAssetCategoryById: async ({categoryUuid}: {categoryUuid: string}) => {
    const response = await apiRequest.get(`/fixed_assets/categories/${categoryUuid}/`);

    return response.data as IAssetCategory;
  },

  fetchNetBookValue: async ({data}: {data: IDepreciationSummaryPayload}) => {
    const response = await apiRequest.post(
      `/fixed_assets/proposed-netbook-value-depreciation-entry/`,
      data,
    );
    return response.data as IDepreciationSummaryResponse;
  },

  getDepreciationSummary: async ({data}: {data: IDepreciationSummaryPayload}) => {
    const response = await apiRequest.post(
      `/fixed_assets/proposed-netbook-value-depreciation-entry/`,
      data,
    );
    return response.data as IDepreciationSummaryResponse;
  },

  fetchDepreciationSchedule: async ({params}: {params: IDepreciationSchedulePayload}) => {
    const query = new URLSearchParams({
      asset_category_base_uuid: params.asset_category_base_uuid,
      purchase_date: params.purchase_date,
      purchase_price: params.purchase_price,
      salvage_value: params.salvage_value ?? "0",
    });
    if (params.useful_life) {
      query.set("useful_life", params.useful_life);
    }
    if (params.depreciation_start_date) {
      query.set("depreciation_start_date", params.depreciation_start_date);
    }
    const response = await apiRequest.get(
      `/fixed_assets/proposed-netbook-value-depreciation-entry/?${query.toString()}`,
    );
    return response.data as IPaginatedResponse<IDepreciationEntry>;
  },

  fetchDepreciationScheduleFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IDepreciationEntry>;
  },
};

export const ASSET_CLASSES_API = {
  // Fetch paginated list of asset classes
  fetchAssetClasses: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);

    const response = await apiRequest.get(`/fixed_assets/asset-classes/?${params.toString()}`);

    return response.data as IPaginatedResponse<IAssetClass>;
  },

  // Fetch paginated data from a "next" URL
  fetchAssetClassesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IAssetClass>;
  },

  // Create a new asset class
  createAssetClass: async ({data}: {data: any}) => {
    const response = await apiRequest.post(`/fixed_assets/asset-classes/`, data);

    return response.data as IAssetClass;
  },

  // Update a specific asset class
  updateAssetClass: async ({classUuid, data}: {classUuid: string; data: any}) => {
    const response = await apiRequest.patch(`/fixed_assets/asset-classes/${classUuid}/`, data);

    return response.data as IAssetClass;
  },

  // Delete an asset class
  deleteAssetClass: async ({classUuid}: {classUuid: string}) => {
    await apiRequest.delete(`/fixed_assets/asset-classes/${classUuid}/`);
  },

  // Fetch single asset class details
  fetchAssetClassById: async ({classUuid}: {classUuid: string}) => {
    const response = await apiRequest.get(`/fixed_assets/asset-classes/${classUuid}/`);

    return response.data as IAssetClass;
  },
};

export const TRANSACTIONS_API = {
  processFinancialEvents: async ({
    contentTypeId,
    objectBaseUuid,
  }: {
    contentTypeId: number;
    objectBaseUuid: string;
  }): Promise<void> => {
    await apiRequest.post("system/process-financial-events/", {
      content_type: contentTypeId,
      object_uuid: objectBaseUuid,
    });
  },

  fetchObjectJournalEntries: async ({
    contentTypeId,
    objectBaseUuid,
    start_date,
    end_date,
  }: {
    contentTypeId: number;
    objectBaseUuid: string;
    start_date?: string;
    end_date?: string;
  }) => {
    const params = new URLSearchParams({
      content_type_id: String(contentTypeId),
      object_base_uuid: objectBaseUuid,
    });

    if (start_date) params.append("start_date", start_date);
    if (end_date) params.append("end_date", end_date);

    const response = await apiRequest.get(`/transactions/journal-items/?${params.toString()}`);

    return response.data as IJournalEntriesData;
  },

  downloadJournalEntryImportTemplate: async ({format}: {format: "excel" | "csv"}) => {
    const response = await apiRequest.get(
      `transactions/journal-entry-import/?file_format=${format}`,
      null,
      {},
      {responseType: "blob"},
    );

    return response.data as Blob;
  },

  previewJournalEntryImport: async ({data}: {data: FormData}) => {
    const response = await apiRequest.post("transactions/journal-entry-import/", data);

    return response.data as IJournalEntryImportResponse;
  },

  fetchTransactions: async ({
    page = 1,
    search,
    fiscal_year_uuid,
    start_date,
    end_date,
    transaction_status,
    ordering,
    account_uuid,
  }: Partial<{
    page: number;
    search: string;
    fiscal_year_uuid: string;
    start_date: string;
    end_date: string;
    transaction_status: string;
    ordering: string;
    account_uuid: string;
  }>) => {
    const params = new URLSearchParams({page: page.toString()});

    getAllSelectedBranchUUIDs().forEach((uuid) => {
      params.append("branch_uuid", uuid);
    });

    if (search) {
      params.append("search", search);
    }
    if (fiscal_year_uuid) params.append("fiscal_year_uuid", fiscal_year_uuid);
    if (start_date) params.append("start_date", start_date);
    if (end_date) params.append("end_date", end_date);
    if (transaction_status) params.append("transaction_status", transaction_status);
    if (account_uuid) params.append("account_uuid", account_uuid);
    if (ordering) params.append("ordering", ordering);

    const response = await apiRequest.get(`/transactions/?${params.toString()}`);

    return response.data as IPaginatedResponse<ITransaction>;
  },

  fetchTransactionsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITransaction>;
  },

  createTransaction: async ({transactionData}: {transactionData: ITransactionFormData}) => {
    const response = await apiRequest.post(`transactions/`, {
      ...transactionData,
      branch: getCurrentBranchId(),
    });

    return response.data as ITransaction;
  },

  updateTransaction: async ({
    transactionId,
    transactionData,
  }: {
    transactionId: string;
    transactionData: ITransactionFormData;
  }) => {
    const response = await apiRequest.patch(`transactions/detail/${transactionId}/`, {
      ...transactionData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as ITransaction;
  },

  deleteTransaction: async ({transactionId}: {transactionId: string}) => {
    await apiRequest.delete(`transactions/detail/${transactionId}/`);
  },

  fetchTransactionById: async ({transactionId}: {transactionId: string}) => {
    const response = await apiRequest.get(`transactions/${transactionId}/`);

    return response.data as ITransaction;
  },

  revertTransaction: async ({
    transactionId,
    revert_reason,
  }: {
    transactionId: string;
    revert_reason: string;
  }) => {
    const response = await apiRequest.post(`transactions/revert/`, {
      base_uuid: transactionId,
      reason: revert_reason,
    });

    return response.data as ITransaction;
  },
  fetchTransactionReversal: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.post(`transactions/reversals/${base_uuid}/`, {base_uuid});
    return response.data as IPaginatedResponse<IReversalEntry>;
  },

  fetchTransactionReversalFromUrl: async ({url, base_uuid}: {url: string; base_uuid: string}) => {
    const response = await apiRequest.post(url, {base_uuid});
    return response.data as IPaginatedResponse<IReversalEntry>;
  },

  download: async (
    filetype: string,
    filters: {
      fiscal_years_uuids: string[];
      branch_uuids?: string[];
    },
  ) => {
    if (!(filetype === "pdf" || filetype === "excel")) return;

    const response = await apiRequest.post(`/transactions/download/`, {
      file_type: filetype,
      fiscal_years_uuids: filters.fiscal_years_uuids,
      branch_uuids: filters.branch_uuids || [],
    });

    return response.data as {message: string};
  },
};

export const TRANSACTION_ENTRIES_API = {
  fetchTransactionEntries: async ({
    reconciliation_session_uuid,
    account_uuid,
    fiscal_year_uuid,
    transaction_uuid,
    page = 1,
    search,
    linked_to_cash_account,
    is_reconciled,
    start_date,
    end_date,
    flow_type,
    balance_scope,
    branch_uuids,
    detail_scope,
    detail_direction,
    detail_section,
    detail_label,
  }: {
    reconciliation_session_uuid?: string;
    account_uuid?: string;
    fiscal_year_uuid?: string;
    transaction_uuid?: string;
    page?: number;
    search?: string;
    linked_to_cash_account?: boolean;
    is_reconciled?: boolean;
    start_date?: string;
    end_date?: string;
    flow_type?: "INFLOW" | "OUTFLOW";
    balance_scope?: "income_statement" | "balance_sheet";
    branch_uuids?: string[];
    detail_scope?: "trial_balance" | "cash_flow";
    detail_direction?: "debit" | "credit" | "inflow" | "outflow";
    detail_section?: string;
    detail_label?: string;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
    });

    if (search) params.append("search", search);
    if (reconciliation_session_uuid)
      params.append("reconciliation_session_uuid", reconciliation_session_uuid);
    if (account_uuid) params.append("account_uuid", account_uuid);
    if (fiscal_year_uuid) params.append("fiscal_year_uuid", fiscal_year_uuid);
    if (transaction_uuid) params.append("transaction_uuid", transaction_uuid);
    if (linked_to_cash_account !== undefined)
      params.append("linked_to_cash_account", String(linked_to_cash_account));
    if (is_reconciled !== undefined) params.append("is_reconciled", String(is_reconciled));
    if (start_date) params.append("start_date", start_date);
    if (end_date) params.append("end_date", end_date);
    if (flow_type) params.append("flow_type", flow_type);
    if (balance_scope) params.append("balance_scope", balance_scope);
    branch_uuids?.forEach((uuid) => params.append("branch_uuid", uuid));
    if (detail_scope) params.append("detail_scope", detail_scope);
    if (detail_direction) params.append("detail_direction", detail_direction);
    if (detail_section) params.append("detail_section", detail_section);
    if (detail_label) params.append("detail_label", detail_label);

    const response = await apiRequest.get(
      `/transactions/transaction-entries/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<ITransactionEntry>;
  },

  fetchTransactionEntriesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITransactionEntry>;
  },
};

export const FISCAL_YEARS_API = {
  fetchFiscalYears: async ({
    page = 1,
    search,
    ordering,
    is_closed,
    is_current,
  }: {
    page?: number;
    search?: string;
    ordering?: string;
    is_closed?: boolean;
    is_current?: boolean;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
    });

    if (search) {
      params.append("search", search);
    }

    if (ordering) {
      params.append("ordering", ordering);
    }

    if (is_closed !== undefined) {
      params.append("is_closed", String(is_closed));
    }
    if (is_current !== undefined) {
      params.append("is_current", String(is_current));
    }

    const response = await apiRequest.get(`items/fiscal-years/?${params.toString()}`);

    return response.data as IPaginatedResponse<IFiscalYear>;
  },

  fetchFiscalYearsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IFiscalYear>;
  },

  createFiscalYear: async ({data}: {data: IFiscalYearFormData}) => {
    const response = await apiRequest.post(`items/fiscal-years/`, {
      ...data,
    });

    return response.data as IFiscalYear;
  },

  updateFiscalYear: async ({yearUuid, data}: {yearUuid: string; data: IFiscalYearFormData}) => {
    const response = await apiRequest.patch(`items/fiscal-years/detail/${yearUuid}/`, {
      ...data,
    });

    return response.data as IFiscalYear;
  },

  deleteFiscalYear: async ({yearUuid}: {yearUuid: string}) => {
    await apiRequest.delete(`items/fiscal-years/detail/${yearUuid}/`);
  },

  fetchFiscalYearById: async ({yearUuid}: {yearUuid: string}) => {
    const response = await apiRequest.get(`items/fiscal-years/detail/${yearUuid}/`);

    return response.data as IFiscalYear;
  },
};

// content type api
export const CONTENT_TYPE_API = {
  fetchContentTypes: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      page: page.toString(),
    });

    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`system/content-types/?${params.toString()}`);

    return response.data as IPaginatedResponse<IContentType>;
  },
  fetchContentTypesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IContentType>;
  },
};

// object api
export const OBJECTS_API = {
  fetchObjects: async ({
    contentTypeId,
    page = 1,
    search,
  }: {
    contentTypeId: number;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
    });

    if (search) {
      params.append("search", search);
    }

    // url needs an id
    const response = await apiRequest.get(
      `system/content-type-objects/${contentTypeId}/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IObject>;
  },
  fetchObjectsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IObject>;
  },
};

export const PURCHASE_ORDERS_API = {
  fetchPurchaseOrders: async (args: Record<string, any> & {page?: number}) => {
    const {page, ...query} = args;
    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      page,
      ...query,
    });

    const response = await apiRequest.get(`customers/purchase-orders/?${params.toString()}`);
    return response.data as IPaginatedResponse<IPurchaseOrder>;
  },

  fetchPurchaseOrdersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IPurchaseOrder>;
  },

  fetchPurchaseOrderLineItems: async ({purchaseOrderUuid}: {purchaseOrderUuid: string}) => {
    let page = (
      await apiRequest.get(
        `customers/purchase-orders/${purchaseOrderUuid}/line-items/?page_size=100`,
      )
    ).data as IPaginatedResponse<IPurchaseOrderLineItem>;

    const lineItems = [...page.results];

    while (page.next) {
      page = (await apiRequest.get(page.next)).data as IPaginatedResponse<IPurchaseOrderLineItem>;
      lineItems.push(...page.results);
    }

    return {
      ...page,
      count: lineItems.length,
      next: null,
      previous: null,
      results: lineItems,
    };
  },

  fetchPurchaseOrderLineItemsPage: async ({
    purchaseOrderUuid,
    page = 1,
  }: {
    purchaseOrderUuid: string;
    page?: number;
  }) => {
    const response = await apiRequest.get(
      `customers/purchase-orders/${purchaseOrderUuid}/line-items/?page=${page}`,
    );
    return response.data as IPaginatedResponse<IPurchaseOrderLineItem>;
  },

  createPurchaseOrder: async ({purchaseOrderData}: {purchaseOrderData: IPurchaseOrderFormData}) => {
    const response = await apiRequest.post(`customers/purchase-orders/`, {
      ...purchaseOrderData,
    });

    return response.data as IPurchaseOrder;
  },

  updatePurchaseOrder: async ({
    purchaseOrderUuid,
    purchaseOrderData,
  }: {
    purchaseOrderUuid: string;
    purchaseOrderData: IPurchaseOrderFormData;
  }) => {
    const response = await apiRequest.patch(
      `customers/purchase-orders/detail/${purchaseOrderUuid}/`,
      {
        ...purchaseOrderData,
        institution: getDefaultInstitutionId(),
      },
    );

    return response.data as IPurchaseOrder;
  },

  deletePurchaseOrder: async ({purchaseOrderUuid}: {purchaseOrderUuid: string}) => {
    await apiRequest.delete(`customers/purchase-orders/detail/${purchaseOrderUuid}/`);
  },

  fetchPurchaseOrderById: async ({purchaseOrderUuid}: {purchaseOrderUuid: string}) => {
    const response = await apiRequest.get(`customers/purchase-orders/detail/${purchaseOrderUuid}/`);

    return response.data as IPurchaseOrder;
  },
  downloadSalesOrderPDF: async ({orderUUID}: {orderUUID: string}) => {
    return downloadFileApi({
      url: `customers/incoming-order-report-download/${orderUUID}`,
      expectedMime: "pdf",
    });
  },

  createPurchaseOrderPayment: async ({
    purchaseOrderUuid,
    paymentData,
  }: {
    purchaseOrderUuid: string;
    paymentData: ISalesOrderPaymentFormData;
  }) => {
    const params = new URLSearchParams({
      customer_purchase_order_base_uuid: purchaseOrderUuid,
    });
    const response = await apiRequest.post(
      `customers/sales-orders/payments/?${params.toString()}`,
      paymentData,
    );

    return response.data as ISalesOrderPayment;
  },
};

// Invoice API
export const EXPENSES_API = {
  fetch: async ({page = 1, search = "", ordering = "-expense_date", branch = ""} = {}) => {
    const params = new URLSearchParams({
      page: String(page),
      search,
      ordering: ordering || "-expense_date",
    });
    if (branch) params.set("branch__base_uuid", branch);
    const response = await apiRequest.get(`requisitions/expenses/?${params}`);
    return response.data as IPaginatedResponse<IExpenseListItem>;
  },
  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IExpenseListItem>;
  },
  fetchOne: async (uuid: string) => {
    const response = await apiRequest.get(`requisitions/expenses/${uuid}/`);
    return response.data as IExpense;
  },
  create: async (payload: IExpenseFormData) => {
    const response = await apiRequest.post("requisitions/expenses/", {
      ...payload,
      attachment: payload.attachment ? await toFileEntry(payload.attachment) : null,
    });
    return response.data as IExpense;
  },
  update: async (
    uuid: string,
    payload: Pick<IExpenseFormData, "expense_date" | "description" | "attachment"> &
      Partial<Pick<IExpenseFormData, "line_items">>,
  ) => {
    const {attachment, ...fields} = payload;
    const response = await apiRequest.patch(`requisitions/expenses/${uuid}/`, {
      ...fields,
      ...(attachment !== undefined && {
        attachment: attachment ? await toFileEntry(attachment) : null,
      }),
    });
    return response.data as IExpense;
  },
  deleteByUUID: async (uuid: string) => {
    await apiRequest.delete(`requisitions/expenses/${uuid}/`);
  },
  fetchLineItems: async (uuid: string, page = 1) => {
    const response = await apiRequest.get(`requisitions/expenses/${uuid}/line-items/?page=${page}`);
    return response.data as IPaginatedResponse<IExpenseLineItem>;
  },
  fetchLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IExpenseLineItem>;
  },
};

export const INVOICES_API = {
  fetchInvoices: async (query: {
    page?: number;
    search?: string;
    customer_base_uuid?: string;
    currency_id?: number;
    filter_out_fully_paid_invoices?: boolean;
    ordering?: string;
    invoice_payment_status?: "unpaid" | "partially_paid" | "paid";
    goods_issued_note_status?:
      | "all"
      | "full_issued"
      | "not_issued"
      | "partially_issued"
      | "not_required";
  }) => {
    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      ...query,
    });

    const response = await apiRequest.get(`customers/invoices/?${params.toString()}`);

    return response.data as IPaginatedResponse<IInvoice>;
  },

  fetchInvoicesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IInvoice>;
  },

  createInvoice: async ({invoiceData}: {invoiceData: IInvoiceFormData}) => {
    const response = await apiRequest.post(`customers/invoices/`, {
      ...invoiceData,
    });

    return response.data as IInvoice;
  },

  updateInvoice: async ({
    invoiceUuid,
    invoiceData,
  }: {
    invoiceUuid: string;
    invoiceData: IInvoiceFormData;
  }) => {
    const response = await apiRequest.patch(`customers/invoices/detail/${invoiceUuid}/`, {
      ...invoiceData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IInvoice;
  },

  deleteInvoice: async ({invoiceUuid}: {invoiceUuid: string}) => {
    await apiRequest.delete(`customers/invoices/detail/${invoiceUuid}/`);
  },
  fetchInvoiceById: async ({invoiceUuid}: {invoiceUuid: string}) => {
    const response = await apiRequest.get(`customers/invoices/detail/${invoiceUuid}/`);

    return response.data as IInvoice;
  },

  fetchInvoiceLineItems: async ({invoiceUuid}: {invoiceUuid: string}) => {
    let page = (await apiRequest.get(`customers/invoice/line-items/${invoiceUuid}/?page_size=100`))
      .data as IPaginatedResponse<IInvoiceLineItem>;

    const lineItems = [...page.results];

    while (page.next) {
      page = (await apiRequest.get(page.next)).data as IPaginatedResponse<IInvoiceLineItem>;
      lineItems.push(...page.results);
    }

    return lineItems;
  },

  fetchInvoiceLineItemsPage: async ({
    invoiceUuid,
    page = 1,
    search,
    excludeReturnedItems,
  }: {
    invoiceUuid: string;
    page?: number;
    search?: string;
    excludeReturnedItems?: boolean;
  }) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (excludeReturnedItems) params.append("exclude_returned_items", "true");

    const response = await apiRequest.get(
      `customers/invoice/line-items/${invoiceUuid}/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IInvoiceLineItem>;
  },

  fetchInvoiceLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IInvoiceLineItem>;
  },

  downloadInvoicePDF: async ({invoiceUuid}: {invoiceUuid: string}) => {
    return downloadFileApi({
      url: `customers/invoice-report-download/${invoiceUuid}`,
    });
  },

  previewTaxCalculation: async ({
    amount,
    base_uuid,
    type,
    applicable_taxes,
  }: ICalculateAmountWithTaxesRequest) => {
    const response = await apiRequest.post(`customers/tax-calculation-preview/`, {
      amount: amount.toString(),
      ...(base_uuid && type && {base_uuid, type}),
      ...(applicable_taxes?.length && {applicable_taxes}),
    });
    return response.data as ICalculateAmountWithTaxesResponse;
  },
};

export const RECURRING_INVOICES_API = {
  fetchRecurringInvoices: async (q: any = {}) => {
    const {query = {}, page, ...rest} = q;

    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      ...query,
      ...rest,
      page,
    });

    const response = await apiRequest.get(`customers/recurring-invoices/?${params.toString()}`);
    return response.data as IPaginatedResponse<IRecurringInvoice>;
  },

  fetchRecurringInvoicesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IRecurringInvoice>;
  },

  fetchRecurringInvoiceById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`customers/recurring-invoices/${base_uuid}/`);

    return response.data as IRecurringInvoice;
  },

  createRecurringInvoice: async ({templateData}: {templateData: IRecurringInvoiceFormData}) => {
    const response = await apiRequest.post(`customers/recurring-invoices/`, {
      ...templateData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IRecurringInvoice;
  },

  updateRecurringInvoice: async ({
    base_uuid,
    templateData,
  }: {
    base_uuid: string;
    templateData: Partial<IRecurringInvoiceFormData>;
  }) => {
    const response = await apiRequest.patch(`customers/recurring-invoices/${base_uuid}/`, {
      ...templateData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IRecurringInvoice;
  },

  deleteRecurringInvoice: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`customers/recurring-invoices/${base_uuid}/`);
  },

  fetchRecurringInvoiceItems: async ({recurringInvoiceUuid}: {recurringInvoiceUuid: string}) => {
    const params = toParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      recurring_invoice_base_uuid: recurringInvoiceUuid,
    });

    const response = await apiRequest.get(
      `customers/recurring-invoice-items/?${params.toString()}`,
    );
    return response.data as IRecurringInvoiceLineItem[];
  },

  fetchRecurringInvoiceItemById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`customers/recurring-invoice-items/${base_uuid}/`);

    return response.data as IRecurringInvoiceLineItem;
  },

  createRecurringInvoiceItem: async ({itemData}: {itemData: IRecurringInvoiceLineItemFormData}) => {
    const response = await apiRequest.post(`customers/recurring-invoice-items/`, {
      ...itemData,
      branch: getCurrentBranchId(),
      institution: getDefaultInstitutionId(),
    });

    return response.data as IRecurringInvoiceLineItem;
  },

  updateRecurringInvoiceItem: async ({
    base_uuid,
    itemData,
  }: {
    base_uuid: string;
    itemData: Partial<IRecurringInvoiceLineItemFormData>;
  }) => {
    const response = await apiRequest.patch(`customers/recurring-invoice-items/${base_uuid}/`, {
      ...itemData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IRecurringInvoiceLineItem;
  },

  deleteRecurringInvoiceItem: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`customers/recurring-invoice-items/${base_uuid}/`);
  },
};

export interface IRecurringInvoiceListQuery {
  page?: number;
  search?: string;
  status?: "active" | "paused" | "completed" | "canceled";
  customer_base_uuid?: string;
}

// Vendor Purchase Order API
export const VENDOR_PURCHASE_ORDERS_API = {
  fetchLineItems: async ({
    purchaseOrderUuid,
    page = 1,
  }: {
    purchaseOrderUuid: string;
    page?: number;
  }) => {
    const response = await apiRequest.get(
      `vendors/purchase-orders/${purchaseOrderUuid}/line-items/?page=${page}&page_size=100`,
    );

    return response.data;
  },
  fetchVendorPurchaseOrders: async (query: {
    search?: string;
    vendor_base_uuid?: string;
    vendor__base_uuid?: string;
    status?: string;
    bill_status?: string;
    goods_received_note_status?: string;
    get_only_not_full_billed?: boolean;
    only_approved?: boolean;
    line_item_base_uuid?: string;
    issue_date_period?: string;
    issue_date_to?: string;
    issue_date_from?: string;
    ordering?: string;
    page?: number;
  }) => {
    const params = toParams({
      search: query.search || "",
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      ...query,
    });

    const response = await apiRequest.get(`vendors/purchase-orders/?${params.toString()}`);
    return response.data as IPaginatedResponse<IVendorPurchaseOrder>;
  },

  fetchVendorPurchaseOrdersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IVendorPurchaseOrder>;
  },

  createVendorPurchaseOrder: async ({
    institutionId,
    purchaseOrderData,
    supporting_document_file,
  }: {
    institutionId: number | string;
    purchaseOrderData: any;
    supporting_document_file?: File;
  }) => {
    const payload = await buildVendorPurchaseOrderPayload({
      ...purchaseOrderData,
      supporting_document_file: supporting_document_file ?? null,
    });

    const response = await apiRequest.post(`vendors/purchase-orders/`, payload);
    return response.data;
  },

  updateVendorPurchaseOrder: async ({
    purchaseOrderUuid,
    purchaseOrderData,
    supporting_document_file,
  }: {
    purchaseOrderUuid: string;
    purchaseOrderData: IVendorPurchaseOrderFormData;
    supporting_document_file?: File;
  }) => {
    const payload = supporting_document_file
      ? await buildVendorPurchaseOrderPayload({
          ...purchaseOrderData,
          supporting_document_file,
        })
      : purchaseOrderData;

    const response = await apiRequest.patch(
      `vendors/purchase-orders/detail/${purchaseOrderUuid}/`,
      {
        ...payload,
        institution: getDefaultInstitutionId(),
      },
    );

    return response.data as IVendorPurchaseOrder;
  },

  deleteVendorPurchaseOrder: async ({purchaseOrderUuid}: {purchaseOrderUuid: string}) => {
    await apiRequest.delete(`vendors/purchase-orders/detail/${purchaseOrderUuid}/`);
  },

  fetchVendorPurchaseOrderById: async ({purchaseOrderUuid}: {purchaseOrderUuid: string}) => {
    const response = await apiRequest.get(`vendors/purchase-orders/detail/${purchaseOrderUuid}/`);

    return response.data as IVendorPurchaseOrder;
  },
  downloadPDF: async ({purchaseOrderUuid}: {purchaseOrderUuid: string}) => {
    return downloadFileApi({
      url: `vendors/purchase-orders/${purchaseOrderUuid}/download/`,
      expectedMime: "pdf",
    });
  },
};

// Vendor Bill API
export const VENDOR_BILLS_API = {
  fetchLineItems: async ({billUuid}: {billUuid: string}) => {
    const response = await apiRequest.get(`vendors/bills/${billUuid}/line-items/`);

    return response.data;
  },
  fetchLineItemsPage: async ({
    billUuid,
    page = 1,
    search,
  }: {
    billUuid: string;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({
      paginated: "true",
      page: String(page),
    });
    if (search) params.set("search", search);

    const response = await apiRequest.get(
      `vendors/bills/${billUuid}/line-items/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IVendorBillLineItem>;
  },
  fetchLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IVendorBillLineItem>;
  },
  fetchVendorBills: async (query: {
    vendor?: string;
    page?: number;
    search?: string;
    filter_out_fully_paid_bills?: boolean;
    issue_date_period?: string;
    issue_date_from?: string;
    issue_date_to?: string;
    ordering?: string;
  }) => {
    const {vendor, ...rest} = query || {};
    const params = toParams({...(rest as any)});

    if (vendor) params.append("vendor_base_uuid", vendor);

    const response = await apiRequest.get(`vendors/bills/?${params.toString()}`);

    return response.data as IPaginatedResponse<IVendorBill>;
  },

  fetchVendorBillsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IVendorBill>;
  },

  createVendorBill: async ({billData}: {billData: IVendorBillFormData}) => {
    const response = await apiRequest.post(`vendors/bills/`, {
      ...billData,
    });

    return response.data as IVendorBill;
  },

  updateVendorBill: async ({
    billUuid,
    billData,
  }: {
    billUuid: string;
    billData: IVendorBillFormData;
  }) => {
    const response = await apiRequest.patch(`vendors/bills/${billUuid}/`, {
      ...billData,
    });

    return response.data as IVendorBill;
  },

  deleteVendorBill: async ({billUuid}: {billUuid: string}) => {
    await apiRequest.delete(`vendors/bills/${billUuid}/`);
  },

  fetchVendorBillById: async ({billUuid}: {billUuid: string}) => {
    const response = await apiRequest.get(`vendors/bills/${billUuid}/`);

    return response.data as IVendorBill;
  },
};

export const CUSTOMER_PAYMENTS_API = {
  fetchCustomerPayments: async ({
    page = 1,
    search = "",
    customer_base_uuid,
    invoice_base_uuid,
    payment_type,
    payment_status,
    ordering,
  }: {
    page?: number;
    search?: string;
    customer_base_uuid?: string;
    invoice_base_uuid?: string;
    payment_type?: "invoice_payment" | "prepayment";
    payment_status?: "DRAFT" | "APPROVED" | "CANCELLED";
    ordering?: string;
  } = {}) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (customer_base_uuid) {
      params.append("customer_base_uuid", customer_base_uuid);
    }
    if (invoice_base_uuid) {
      params.append("invoice_base_uuid", invoice_base_uuid);
    }
    if (payment_type) params.append("payment_type", payment_type);
    if (payment_status) params.append("payment_status", payment_status);
    if (ordering) params.append("ordering", ordering);

    const response = await apiRequest.get(`customers/payments/?${params.toString()}`);
    return response.data as IPaginatedResponse<ICustomerPaymentRecord>;
  },

  fetchCustomerPaymentsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ICustomerPaymentRecord>;
  },

  createCustomerPayment: async ({paymentData}: {paymentData: ICustomerPaymentRecordFormData}) => {
    const response = await apiRequest.post("customers/payments/", paymentData);
    return response.data as ICustomerPaymentRecord;
  },

  fetchCustomerPaymentById: async ({paymentUuid}: {paymentUuid: string}) => {
    const response = await apiRequest.get(`customers/payments/${paymentUuid}/`);
    return response.data as ICustomerPaymentRecord;
  },

  updateCustomerPayment: async ({
    paymentUuid,
    paymentData,
  }: {
    paymentUuid: string;
    paymentData: Partial<ICustomerPaymentRecordFormData>;
  }) => {
    const response = await apiRequest.patch(`customers/payments/${paymentUuid}/`, paymentData);
    return response.data as ICustomerPaymentRecord;
  },

  deleteCustomerPayment: async ({paymentUuid}: {paymentUuid: string}) => {
    await apiRequest.delete(`customers/payments/${paymentUuid}/`);
  },

  reconcilePrepayments: async ({
    prepayment_uuids,
    invoice_uuids,
  }: {
    prepayment_uuids: string[];
    invoice_uuids: string[];
  }) => {
    const response = await apiRequest.post("customers/reconcile-prepayments/", {
      prepayment_uuids,
      invoice_uuids,
    });
    return response.data;
  },

  fetchPrepaymentAllocations: async ({
    prepaymentUuid,
    page = 1,
  }: {
    prepaymentUuid: string;
    page?: number;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      customer_payment_base_uuid: prepaymentUuid,
    });
    const response = await apiRequest.get(`customers/deposit-allocations/?${params.toString()}`);
    return response.data as IPaginatedResponse<ICustomerDepositAllocation>;
  },

  fetchPrepaymentAllocationsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ICustomerDepositAllocation>;
  },
};

// Vendor Payments API
export const VENDOR_PAYMENTS_API = {
  fetchVendorPayments: async ({
    page = 1,
    search = "",
    vendor_base_uuid,
    has_bill,
    bill_base_uuid,
    only_paid,
  }: {
    page?: number;
    search?: string;
    vendor_base_uuid?: string;
    has_bill?: boolean;
    bill_base_uuid?: string;
    only_paid?: boolean;
  }) => {
    const params = new URLSearchParams();

    params.append("page", page.toString());
    if (search) {
      params.append("search", search);
    }
    if (vendor_base_uuid) {
      params.append("vendor_base_uuid", vendor_base_uuid);
    }
    if (has_bill !== undefined) params.append("has_bill", String(has_bill));
    if (bill_base_uuid) params.append("bill_base_uuid", bill_base_uuid);
    if (only_paid !== undefined) params.append("only_paid", String(only_paid));
    const response = await apiRequest.get(`vendors/payments/?${params.toString()}`);

    return response.data as IPaginatedResponse<IVendorPayment>;
  },

  fetchVendorPaymentsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IVendorPayment>;
  },

  createVendorPayment: async ({paymentData}: {paymentData: IVendorPaymentFormData}) => {
    const response = await apiRequest.post(`vendors/payments/`, {
      ...paymentData,
    });

    return response.data as IVendorPayment;
  },

  updateVendorPayment: async ({
    paymentUuid,
    paymentData,
  }: {
    paymentUuid: string;
    paymentData: IVendorPaymentFormData;
  }) => {
    const response = await apiRequest.patch(`vendors/payments/${paymentUuid}/`, paymentData);

    return response.data as IVendorPayment;
  },

  deleteVendorPayment: async ({paymentUuid}: {paymentUuid: string}) => {
    await apiRequest.delete(`vendors/payments/${paymentUuid}/`);
  },

  fetchVendorPaymentById: async ({paymentUuid}: {paymentUuid: string}) => {
    const response = await apiRequest.get(`vendors/payments/${paymentUuid}/`);

    return response.data as IVendorPayment;
  },
  linkPrepaymentsToBills: async ({
    prepayment_uuids,
    bill_uuids,
  }: {
    prepayment_uuids: string[];
    bill_uuids: string[];
  }) => {
    const response = await apiRequest.post(`vendors/reconcile-prepayments/`, {
      prepayment_uuids,
      bill_uuids,
    });
    return response.data;
  },
  fetchPrepaymentAllocations: async ({
    prepaymentUuid,
    page = 1,
  }: {
    prepaymentUuid: string;
    page?: number;
  }) => {
    const params = new URLSearchParams({page: page.toString()});
    const response = await apiRequest.get(
      `vendors/prepayment-allocations/?vendor_payment_base_uuid=${prepaymentUuid}&${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IPrepaymentAllocation>;
  },

  fetchPrepaymentAllocationsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IPrepaymentAllocation>;
  },
};

// Vendor Credits API
export const VENDOR_CREDITS_API = {
  fetchVendorCredits: async ({
    institutionId,
    page = 1,
    search = "",
  }: {
    institutionId: number | string;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams();

    params.append("page", page.toString());
    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`vendors/vendor-credits/?${params.toString()}`);

    return response.data as IPaginatedResponse<IVendorCredit>;
  },

  fetchVendorCreditsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IVendorCredit>;
  },

  createVendorCredit: async ({creditData}: {creditData: IVendorCreditFormData}) => {
    const response = await apiRequest.post(`vendors/vendor-credits/`, {
      ...creditData,
      branch: getCurrentBranchId(),
    });

    return response.data as IVendorCredit;
  },

  updateVendorCredit: async ({
    creditUuid,
    creditData,
  }: {
    creditUuid: string;
    creditData: IVendorCreditFormData;
  }) => {
    const response = await apiRequest.patch(`vendors/vendor-credits/detail/${creditUuid}/`, {
      ...creditData,
      institution: getDefaultInstitutionId(),
    });

    return response.data as IVendorCredit;
  },

  deleteVendorCredit: async ({creditUuid}: {creditUuid: string}) => {
    await apiRequest.delete(`vendors/vendor-credits/detail/${creditUuid}/`);
  },

  fetchVendorCreditById: async ({creditUuid}: {creditUuid: string}) => {
    const response = await apiRequest.get(`vendors/vendor-credits/detail/${creditUuid}/`);

    return response.data as IVendorCredit;
  },
};

// Requisitions API
export const REQUISITIONS_API = {
  fetchRequisitions: async ({
    page = 1,
    ordering,
    search = "",
    status = "",
    payment_status = "",
    requisition_type_base_uuid = "",
    requisition_types = [],
    branches = [],
    requested_by = [],
    only_those_on_my_level,
    approval_queue = "",
    date_filter = "",
    requisition_item_base_uuid = "",
  }: {
    page?: number;
    ordering?: string;
    search?: string;
    status?: string;
    payment_status?: string;
    requisition_type_base_uuid?: string;
    requisition_types?: string[];
    branches?: string[];
    requested_by?: string[];
    only_those_on_my_level?: boolean;
    approval_queue?: string;
    date_filter?: string;
    requisition_item_base_uuid?: string;
  }) => {
    const params = new URLSearchParams();

    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (status) params.append("status", status);
    if (payment_status) params.append("payment_status", payment_status);
    if (requisition_type_base_uuid)
      params.append("requisition_type_base_uuid", requisition_type_base_uuid);
    requisition_types.forEach((templateUuid) => {
      params.append("requisition_type__base_uuid", templateUuid);
    });
    branches.forEach((branchUuid) => {
      params.append("branch__base_uuid", branchUuid);
    });
    requested_by.forEach((requesterUuid) => {
      params.append("requested_by__user__profile__user__base_uuid", requesterUuid);
    });
    if (only_those_on_my_level !== undefined)
      params.append("only_those_on_my_level", String(only_those_on_my_level));
    if (approval_queue) params.append("approval_queue", approval_queue);
    if (date_filter) params.append("date_filter", date_filter);
    if (requisition_item_base_uuid) {
      params.append("requisition_item_base_uuid", requisition_item_base_uuid);
    }

    const response = await apiRequest.get(`requisitions/?${params.toString()}`);

    return response.data as IPaginatedResponse<IRequisitionListItem>;
  },

  fetchRequisitionsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IRequisitionListItem>;
  },

  createRequisition: async ({
    institutionId,
    requisitionData,
  }: {
    institutionId: number | string;
    requisitionData: IRequisitionPayload;
  }) => {
    const response = await apiRequest.post(`requisitions/`, requisitionData);
    return response.data as IRequisition;
  },

  updateRequisition: async ({
    requisitionId,
    requisitionData,
  }: {
    requisitionId: string;
    requisitionData: IRequisitionPayload;
  }) => {
    const response = await apiRequest.patch(`requisitions/${requisitionId}/`, requisitionData);
    return response.data as IRequisition;
  },

  deleteRequisition: async ({requisitionId}: {requisitionId: string}) => {
    await apiRequest.delete(`requisitions/${requisitionId}/`);
  },

  fetchRequisitionById: async ({requisitionId}: {requisitionId: string}) => {
    const response = await apiRequest.get(`requisitions/${requisitionId}/`);

    return response.data as IRequisition;
  },

  previewTaxCalculation: async ({
    lineItem,
    amount,
  }: {
    lineItem: string;
    amount: string | number;
  }) => {
    const response = await apiRequest.post(`requisitions/tax-calculation-preview/`, {
      line_item: lineItem,
      amount: String(amount),
    });

    return response.data as IRequisitionTaxPreview;
  },

  addRequisitionAttachment: async ({
    requisitionId,
    name,
    document,
  }: {
    requisitionId: string;
    name: string;
    document: File;
  }) => {
    const response = await apiRequest.post(`requisitions/${requisitionId}/attachments/`, {
      name,
      document: await toFileEntry(document),
    });
    return response.data as IRequisitionAttachment;
  },

  fetchRequisitionByReferenceCode: async ({reference_code}: {reference_code: string}) => {
    const response = await apiRequest.get(`requisitions/public-preview/${reference_code}/`);

    return response.data as IPublicRequisitionPreview;
  },

  createRequisitionType: async ({typeData}: {typeData: any[]}) => {
    const response = await apiRequest.post(`requisitions/types/bulk-create/`, {
      types_data: typeData,
    });

    return response.data;
  },

  downloadRequisitionForm: async ({baseUuid}: {baseUuid: string}) => {
    return downloadFileApi({
      url: `requisitions/${baseUuid}/download/`,
      expectedMime: "pdf",
    });
  },

  getRequisitionArrears: async ({
    page = 1,
    requisitionType,
  }: {
    page?: number;
    requisitionType?: number;
  } = {}) => {
    const params = new URLSearchParams();

    params.append("page", page.toString());
    params.append("status", "arrears");
    if (requisitionType) {
      params.append("requisition_type", requisitionType.toString());
    }

    const response = await apiRequest.get(`requisitions/arrears/?${params.toString()}`);

    return response.data as IPaginatedResponse<IRequisitionArrear>;
  },

  markAsPaid: async ({
    requisitionId,
    data,
  }: {
    requisitionId: string;
    data: IMarkRequisitionAsPaidPayload;
  }) => {
    const response = await apiRequest.post(`requisitions/payments/${requisitionId}/`, data);
    return response.data as IRequisition;
  },

  fetchRequisitionLineItems: async ({baseUuid, page = 1}: {baseUuid: string; page?: number}) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    const response = await apiRequest.get(
      `requisitions/line-items/${baseUuid}/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<any>;
  },

  fetchRequisitionLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<any>;
  },

  addRequisitionLineItem: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: {
      line_item?: string;
      quantity: number;
      unit_price?: string;
      description?: string;
      beneficiary?: string;
    }[];
  }) => {
    const response = await apiRequest.post(`requisitions/line-items/${baseUuid}/`, data);
    return response.data;
  },

  deleteRequisitionLineItem: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`requisitions/line-items/${baseUuid}/detail/`);
  },

  updateRequisitionLineItem: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: {
      quantity?: number;
      unit_price?: string;
      beneficiary?: string | null;
      is_removed?: boolean;
    };
  }) => {
    const response = await apiRequest.patch(`requisitions/line-items/${baseUuid}/detail/`, data);
    return response.data;
  },
};

// Requisition Types API
export const REQUISITION_TYPES_API = {
  fetchRequisitionTypes: async ({
    page = 1,
    search = "",
    ...rest
  }: {
    page?: number;
    search?: string;
    [key: string]: any;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      search,
    });
    Object.entries(rest).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      params.append(key, String(value));
    });

    const response = await apiRequest.get(`requisitions/types/?${params.toString()}`);
    return response.data as IPaginatedResponse<IRequisitionType>;
  },

  fetchRequisitionTypesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IRequisitionType>;
  },

  fetchRequisitionTypeItems: async ({base_uuid, search}: {base_uuid: string; search?: string}) => {
    const params = new URLSearchParams();
    if (search) {
      params.append("search", search);
    }
    const response = await apiRequest.get(
      `requisitions/type/items/${base_uuid}/?${params.toString()}`,
    );
    return response.data;
  },

  addRequisitionTypeLineItem: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: {
      item?: string;
      description?: string;
      unit_price: string;
      max_quantity?: number;
      should_unit_price_be_edited?: boolean;
      price_change_direction?: "up" | "down" | "both" | null;
      allowable_price_change_threshold_in_percentage?: string | number | null;
      allow_unconfigured_beneficiaries?: boolean;
      beneficiaries?: {beneficiary: string}[];
      taxes_that_apply?: {
        tax: string;
        withhold_tax_amount?: boolean;
      }[];
    }[];
  }) => {
    const response = await apiRequest.post(`requisitions/type/items/${baseUuid}/`, data);
    return response.data;
  },

  updateRequisitionTypeLineItem: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: {
      item?: string;
      description?: string;
      unit_price?: string;
      max_quantity?: number;
      should_unit_price_be_edited?: boolean;
      price_change_direction?: "up" | "down" | "both" | null;
      allowable_price_change_threshold_in_percentage?: string | number | null;
      allow_unconfigured_beneficiaries?: boolean;
      beneficiaries?: {beneficiary: string}[];
      taxes_that_apply?: {
        tax: string;
        withhold_tax_amount?: boolean;
      }[];
    };
  }) => {
    const response = await apiRequest.patch(`requisitions/type/items/${baseUuid}/detail/`, data);
    return response.data;
  },

  fetchRequisitionTypeLineItem: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`requisitions/type/items/${baseUuid}/detail/`);
    return response.data;
  },

  deleteRequisitionTypeLineItem: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`requisitions/type/items/${baseUuid}/detail/`);
  },

  fetchRequisitionTypeLineItemBeneficiaries: async ({
    lineItem,
    page = 1,
    search = "",
  }: {
    lineItem?: string;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});
    if (lineItem) params.append("line_item", lineItem);
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `requisitions/type/item-beneficiaries/?${params.toString()}`,
    );
    return response.data;
  },

  fetchRequisitionTypeLineItemBeneficiariesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data;
  },

  createRequisitionTypeLineItemBeneficiary: async ({
    data,
  }: {
    data: {line_item: string; beneficiary: string};
  }) => {
    const response = await apiRequest.post(`requisitions/type/item-beneficiaries/`, data);
    return response.data;
  },

  updateRequisitionTypeLineItemBeneficiary: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<{line_item: string; beneficiary: string}>;
  }) => {
    const response = await apiRequest.patch(
      `requisitions/type/item-beneficiaries/${baseUuid}/`,
      data,
    );
    return response.data;
  },

  deleteRequisitionTypeLineItemBeneficiary: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`requisitions/type/item-beneficiaries/${baseUuid}/`);
  },

  fetchRequisitionTypeItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data;
  },

  fetchUserRequisitionTypes: async ({
    user_id,
    page = 1,
    search = "",
  }: {
    user_id?: number;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) {
      params.append("search", search);
    }
    if (user_id) {
      params.append("user_id", user_id.toString());
    }

    const response = await apiRequest.get(
      `requisitions/requisition-types/my-requisition-types/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IRequisitionType>;
  },

  fetchUserRequisitionTypesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IRequisitionType>;
  },

  createRequisitionType: async ({
    typeData,
  }: {
    typeData: IRequisitionTypeFormData | IRequisitionTypeFormData[];
  }) => {
    const dataArray = Array.isArray(typeData) ? typeData : [typeData];
    const response = await apiRequest.post(
      `requisitions/types/`,
      dataArray.map((type) => ({
        ...type,
      })),
    );
    return Array.isArray(typeData) ? response.data : response.data[0];
  },

  updateRequisitionType: async ({
    typeId,
    typeData,
  }: {
    typeId: string;
    typeData: IRequisitionTypeFormData;
  }) => {
    const response = await apiRequest.patch(`requisitions/types/${typeId}/`, {
      ...typeData,
    });

    return response.data as IRequisitionType;
  },

  deleteRequisitionType: async ({typeId}: {typeId: string}) => {
    await apiRequest.delete(`requisitions/types/${typeId}/`);
  },

  fetchRequisitionTypeById: async ({typeId}: {typeId: string}) => {
    const response = await apiRequest.get(`requisitions/types/${typeId}/`);

    return response.data as IRequisitionType;
  },

  fetchAllowedBranches: async ({
    typeId,
    page = 1,
    search = "",
  }: {
    typeId: string;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `requisitions/types/${typeId}/allowed-branches/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<Branch> & {allows_all_branches: boolean};
  },

  fetchAllowedCurrencies: async ({
    typeId,
    page = 1,
    search = "",
  }: {
    typeId: string;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `requisitions/types/${typeId}/allowed-currencies/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IInstitutionSupportedCurrency>;
  },

  fetchAllowedCurrenciesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IInstitutionSupportedCurrency>;
  },

  addAllowedCurrency: async ({typeId, currency}: {typeId: string; currency: string}) => {
    const response = await apiRequest.post(`requisitions/types/${typeId}/allowed-currencies/`, {
      currency,
    });

    return response.data as IPaginatedResponse<IInstitutionSupportedCurrency>;
  },

  removeAllowedCurrency: async ({typeId, currency}: {typeId: string; currency: string}) => {
    const response = await apiRequest.delete(
      `requisitions/types/${typeId}/allowed-currencies/${currency}/`,
    );

    return response.data as IPaginatedResponse<IInstitutionSupportedCurrency>;
  },

  addAllowedBranch: async ({typeId, branch}: {typeId: string; branch: string}) => {
    const response = await apiRequest.post(`requisitions/types/${typeId}/allowed-branches/`, {
      branch,
    });
    return response.data as IPaginatedResponse<Branch> & {allows_all_branches: boolean};
  },

  removeAllowedBranch: async ({typeId, branch}: {typeId: string; branch: string}) => {
    const response = await apiRequest.delete(
      `requisitions/types/${typeId}/allowed-branches/${branch}/`,
    );
    return response.data as IPaginatedResponse<Branch> & {allows_all_branches: boolean};
  },
};

export const REQUISITIONS_STATISTICS_API = {
  fetchPaymentById: async ({
    paymentId,
    requisitionId,
  }: {
    paymentId: string;
    requisitionId: string;
  }) => {
    const response = await apiRequest.get(`requisitions/payments/${paymentId}/${requisitionId}/`);
    return response.data as IRequisitionPayment;
  },

  addAfterPaymentAttachment: async ({
    paymentId,
    requisitionId,
    name,
    document,
  }: {
    paymentId: string;
    requisitionId: string;
    name: string;
    document: File;
  }) => {
    const response = await apiRequest.post(
      `requisitions/payments/${paymentId}/${requisitionId}/attachments/`,
      {
        name,
        document: await toFileEntry(document),
      },
    );
    return response.data as IRequisitionAttachment;
  },

  updatePaymentAttachment: async ({
    paymentId,
    requisitionId,
    attachmentId,
    name,
    document,
  }: {
    paymentId: string;
    requisitionId: string;
    attachmentId: string;
    name: string;
    document?: File | null;
  }) => {
    const response = await apiRequest.patch(
      `requisitions/payments/${paymentId}/${requisitionId}/attachments/${attachmentId}/`,
      {
        name,
        ...(document && {document: await toFileEntry(document)}),
      },
    );
    return response.data as IRequisitionAttachment;
  },

  deletePaymentAttachment: async ({
    paymentId,
    requisitionId,
    attachmentId,
  }: {
    paymentId: string;
    requisitionId: string;
    attachmentId: string;
  }) => {
    await apiRequest.delete(
      `requisitions/payments/${paymentId}/${requisitionId}/attachments/${attachmentId}/`,
    );
  },

  fetchPayments: async ({
    page = 1,
    requisitionBaseUuid,
    search,
    dateFilter,
    status,
    ordering,
  }: {
    page?: number;
    requisitionBaseUuid?: string;
    search?: string;
    dateFilter?: string;
    status?: string;
    ordering?: string;
  } = {}) => {
    const params = new URLSearchParams({page: page.toString()});

    if (requisitionBaseUuid) {
      params.append("requisition_base_uuid", requisitionBaseUuid);
    }
    if (search) params.append("search", search);
    if (dateFilter) params.append("date_filter", dateFilter);
    if (status) params.append("status", status);
    if (ordering) params.append("ordering", ordering);

    const response = await apiRequest.get(`requisitions/payments/?${params.toString()}`);
    return response.data as IPaginatedResponse<IRequisitionPayment>;
  },

  fetchPaymentsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IRequisitionPayment>;
  },

  fetchDashboardSummary: async () => {
    const response = await apiRequest.get("requisitions/statistics/dashboard-summary/");
    return response.data as IRequisitionDashboardSummary;
  },

  fetchRecentActivity: async ({
    page = 1,
    pageSize = 10,
  }: {
    page?: number;
    pageSize?: number;
  } = {}) => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    const response = await apiRequest.get(
      `requisitions/statistics/recent-activity/?${params.toString()}`,
    );
    return response.data as IRequisitionRecentActivityResponse;
  },

  fetchRecentActivityFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IRequisitionRecentActivityResponse;
  },

  fetchStatistics: async ({
    date_filter = "",
    requisition_type_base_uuid = "",
  }: {
    date_filter?: string;
    requisition_type_base_uuid?: string;
  } = {}) => {
    const params = new URLSearchParams();
    if (date_filter) params.append("date_filter", date_filter);
    if (requisition_type_base_uuid)
      params.append("requisition_type_base_uuid", requisition_type_base_uuid);
    const response = await apiRequest.get(
      `requisitions/statistics/requisition-intelligence/?${params.toString()}`,
    );
    return response.data as {general_statistics: IRequisitionGeneralStatistics};
  },

  fetchCommonlyUsedTemplates: async ({
    date_filter = "",
    limit = "",
  }: {date_filter?: string; limit?: string} = {}) => {
    const params = new URLSearchParams();
    if (date_filter) params.append("date_filter", date_filter);
    //if (limit) params.append("limit", limit);
    const response = await apiRequest.get(
      `requisitions/statistics/commomly-used-templates/?${params.toString()}`,
    );
    return response.data as {commonly_used_requisition_types: ICommonlyUsedRequisitionType[]};
  },
};
export const APPROVAL_DOCUMENT_CATEGORIES_API = {
  fetchCategories: async ({
    page = 1,
    search = "",
    ...rest
  }: {
    page?: number;
    search?: string;
    [key: string]: any;
  }) => {
    const params = new URLSearchParams({page: page.toString(), search});
    Object.entries(rest).forEach(([key, value]) => {
      params.append(key, String(value));
    });
    const response = await apiRequest.get(
      `approval/approval-document-categories/?${params.toString()}`,
    );
    return response.data as IApprovalDocumentCategory[];
  },

  fetchCategoriesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IApprovalDocumentCategory>;
  },
};

export const SALES_PERSON_API = {
  createSalePerson: async ({personData}: {personData: ISalePersonFormData | FormData}) => {
    const response = await apiRequest.post("customers/sales-persons/", personData);
    return response.data as ISalesPerson;
  },
  fetchSalesPersons: async ({
    page = 1,
    search = "",
  }: {
    user_id?: number;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`customers/sales-persons/?${params.toString()}`);

    return response.data as IPaginatedResponse<ISalesPerson>;
  },

  fetchSalesPersonFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ISalesPerson>;
  },

  updateSalesPerson: async ({
    user_id,
    personData,
  }: {
    user_id: string;
    personData: ISalePersonFormData | FormData;
  }) => {
    const response = await apiRequest.patch(
      `customers/sales-persons/detail/${user_id}/`,
      personData,
    );

    return response.data as ISalesPerson;
  },

  deleteSalePerson: async ({user_id}: {user_id: string}) => {
    await apiRequest.delete(`customers/sales-persons/detail/${user_id}/`);
  },

  fetchSalesPersonById: async ({user_id}: {user_id: string}) => {
    const response = await apiRequest.get(`customers/sales-persons/detail/${user_id}/`);

    return response.data as ISalesPerson;
  },
};

export const PAYMENT_TERMS_API = {
  // Fetch paginated payment terms with optional search
  fetchPaymentTerms: async ({page = 1, search}: {page?: number; search?: string} = {}) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);

    const response = await apiRequest.get(`/customers/payment-terms/?${params.toString()}`);

    return response.data as IPaginatedResponse<IPaymentTerm>;
  },

  // Fetch next page from a URL
  fetchPaymentTermsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IPaymentTerm>;
  },

  fetchPaymentTermByNumericId: async ({id}: {id: string}) => {
    const response = await apiRequest.get(`/customers/payment-terms/?id=${encodeURIComponent(id)}`);

    const data = response.data as IPaginatedResponse<IPaymentTerm>;
    return data.results[0] ?? null;
  },

  createPaymentTerm: async (data: IPaymentTermFormData | IPaymentTermFormData[]) => {
    const dataArray = Array.isArray(data) ? data : [data];
    const response = await apiRequest.post(`/customers/payment-terms/`, dataArray);

    return Array.isArray(data) ? response.data : response.data[0];
  },

  updatePaymentTerm: async ({termUuid, data}: {termUuid: string; data: IPaymentTermFormData}) => {
    const response = await apiRequest.patch(`/customers/payment-terms/detail/${termUuid}/`, {
      ...data,
    });

    return response.data as IPaymentTerm;
  },

  deletePaymentTerm: async ({termUuid}: {termUuid: string}) => {
    await apiRequest.delete(`/customers/payment-terms/detail/${termUuid}/`);
  },

  fetchPaymentTermById: async ({termUuid}: {termUuid: string}) => {
    const response = await apiRequest.get(`/customers/payment-terms/detail/${termUuid}/`);

    return response.data as IPaymentTerm;
  },
};

export const ITEM_UNIT_OF_MEASURE_API = {
  createUnitOfMeasure: async ({unitData}: {unitData: IItemUnitOfMeasureFormData[]}) => {
    const response = await apiRequest.post("items/item-units-of-measure/", unitData);
    return response.data as IItemUnitOfMeasure; // still returns single object
  },

  fetchUnitsOfMeasure: async ({page = 1, search = ""}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`items/item-units-of-measure/?${params.toString()}`);

    return response.data as IPaginatedResponse<IItemUnitOfMeasure>;
  },

  fetchUnitsOfMeasureFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IItemUnitOfMeasure>;
  },

  updateUnitOfMeasure: async ({
    base_uuid,
    unitData,
  }: {
    base_uuid: string;
    unitData: IItemUnitOfMeasureFormData[];
  }) => {
    const response = await apiRequest.patch(
      `items/item-units-of-measure/detail/${base_uuid}/`,
      unitData,
    );
    return response.data as IItemUnitOfMeasure;
  },

  deleteUnitOfMeasure: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`items/item-units-of-measure/detail/${base_uuid}/`);
  },

  fetchUnitOfMeasureById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`items/item-units-of-measure/detail/${base_uuid}/`);

    return response.data as IItemUnitOfMeasure;
  },

  fetchInventoryItemUoms: async ({inventory_item_uuid}: {inventory_item_uuid: string}) => {
    const params = new URLSearchParams({inventory_item_uuid});
    const response = await apiRequest.get(
      `items/inventory-item-units-of-measure/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IInventoryItemUnitOfMeasure>;
  },

  fetchBranchInventoryItemUoms: async ({
    branch_inventory_item_uuid,
  }: {
    branch_inventory_item_uuid: string;
  }) => {
    const params = new URLSearchParams({branch_inventory_item_uuid});
    const response = await apiRequest.get(
      `items/branch-inventory-item-units-of-measure/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IBranchInventoryItemUnitOfMeasure>;
  },

  bulkUploadUnitsOfMeasure: async (data: FormData) => {
    const response = await apiRequest.post(`bulk_upload/`, data);

    return response.data;
  },
};

export const purchaseOrderAPI = {
  getAll: () => apiRequest.get("customers/purchase-orders/"),
  getById: (base_uuid: string) => apiRequest.get(`customers/purchase-orders/detail/${base_uuid}/`),
  create: (data: any) => apiRequest.post("customers/purchase-orders/", data),
  update: (base_uuid: string, data: any) =>
    apiRequest.patch(`customers/purchase-orders/${base_uuid}/`, data),
  delete: (base_uuid: string) => apiRequest.delete(`customers/purchase-orders/${base_uuid}/`),
};

export const commissionsAPI = {
  getAll: async (): Promise<ISalesPersonCommission[]> => {
    const response = await apiRequest.get("/customers/sales-persons/commissions/");

    return response.data;
  },
  create: async (data: {
    amount: string;
    commission_type: "payments" | "earnings";
    sales_person: number;
  }): Promise<ISalesPersonCommission> => {
    const response = await apiRequest.post("/customers/sales-persons/commissions/", data);

    return response.data;
  },
};

// Tax API matching backend taxation endpoints
export const TAXES_API = {
  fetchTaxes: async ({
    page = 1,
    search,
    is_statutory_obligation,
    only_applicable_to_invoices,
    only_applicable_to_bills,
  }: {
    page?: number;
    search?: string;
    is_statutory_obligation?: boolean;
    only_applicable_to_invoices?: boolean;
    only_applicable_to_bills?: boolean;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (search) params.append("search", search);
    if (is_statutory_obligation !== undefined) {
      params.set("is_statutory_obligation", String(is_statutory_obligation));
    }
    if (only_applicable_to_invoices) params.append("only_applicable_to_invoices", "true");
    if (only_applicable_to_bills) params.append("only_applicable_to_bills", "true");

    const response = await apiRequest.get(`/taxation/?${params.toString()}`);
    return response.data as IPaginatedResponse<ITax>;
  },

  fetchTaxesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITax>;
  },

  createTax: async ({data}: {data: ITaxFormData}) => {
    const response = await apiRequest.post(`/taxation/`, data);

    return response.data as ITax;
  },

  updateTax: async ({taxUuid, data}: {taxUuid: string; data: Partial<ITaxFormData>}) => {
    const response = await apiRequest.patch(`/taxation/${taxUuid}/`, data);

    return response.data as ITax;
  },

  resetTaxSystemDefaults: async ({taxUuid}: {taxUuid: string}) => {
    const response = await apiRequest.post(`/taxation/${taxUuid}/reset-system-defaults/`);

    return response.data as ITax;
  },

  getTax: async ({taxUuid}: {taxUuid: string}) => {
    const response = await apiRequest.get(`/taxation/${taxUuid}/`);

    return response.data as ITax;
  },

  deleteTax: async ({taxUuid}: {taxUuid: string}) => {
    const response = await apiRequest.delete(`/taxation/${taxUuid}/`);

    return response.data;
  },

  fetchTaxAccounts: async ({
    taxUuid,
    page = 1,
    search,
  }: {
    taxUuid: string;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});
    if (search) params.append("search", search);
    const response = await apiRequest.get(`/taxation/${taxUuid}/accounts/?${params.toString()}`);
    return response.data as IPaginatedResponse<ITaxAccountRead>;
  },

  fetchTaxSummary: async ({
    taxUuid,
    start_date,
    end_date,
  }: {
    taxUuid: string;
    start_date: string;
    end_date: string;
  }) => {
    const params = new URLSearchParams({
      tax_base_uuid: taxUuid,
      start_date,
      end_date,
    });
    const response = await apiRequest.get(`/taxation/returns/summary/?${params.toString()}`);
    return response.data as ITaxSummary;
  },
};

export const TAX_TYPES_API = {
  fetchTaxTypes: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      page: page.toString(),
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (search) params.append("search", search);
    const response = await apiRequest.get(`/taxation/?${params.toString()}`);

    return response.data as IPaginatedResponse<ITaxType>;
  },

  fetchTaxTypesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITaxType>;
  },

  createTaxType: async ({data}: {data: ITaxTypeFormData}) => {
    const response = await apiRequest.post(`/taxation/`, data);

    return response.data as ITaxType;
  },

  updateTaxType: async ({
    taxTypeUuid,
    data,
  }: {
    taxTypeUuid: string;
    data: Partial<ITaxTypeFormData>;
  }) => {
    const response = await apiRequest.patch(`/taxation/${taxTypeUuid}/`, data);

    return response.data as ITaxType;
  },

  deleteTaxType: async ({taxTypeUuid}: {taxTypeUuid: string}) => {
    await apiRequest.delete(`/taxation/${taxTypeUuid}/`);
  },

  fetchTaxTypeById: async ({taxTypeUuid}: {taxTypeUuid: string}) => {
    const response = await apiRequest.get(`/taxation/${taxTypeUuid}/`);

    return response.data as ITaxType;
  },
};

export const TAX_RULES_API = {
  fetchTaxRules: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      page: page.toString(),
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (search) params.append("search", search);
    const response = await apiRequest.get(`/taxation/rules/?${params.toString()}`);

    return response.data as IPaginatedResponse<ITaxRule>;
  },

  fetchTaxRulesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITaxRule>;
  },

  createTaxRule: async ({data}: {data: ITaxRuleFormData}) => {
    const response = await apiRequest.post(`/taxation/rules/`, data);

    return response.data as ITaxRule;
  },

  updateTaxRule: async ({
    taxRuleUuid,
    data,
  }: {
    taxRuleUuid: string;
    data: Partial<ITaxRuleFormData>;
  }) => {
    const response = await apiRequest.patch(`/taxation/rules/${taxRuleUuid}/`, data);

    return response.data as ITaxRule;
  },

  deleteTaxRule: async ({taxRuleUuid}: {taxRuleUuid: string}) => {
    await apiRequest.delete(`/taxation/rules/${taxRuleUuid}/`);
  },

  fetchTaxRuleById: async ({taxRuleUuid}: {taxRuleUuid: string}) => {
    const response = await apiRequest.get(`/taxation/rules/${taxRuleUuid}/`);

    return response.data as ITaxRule;
  },
};

export const TAX_DEPENDENCY_API = {
  fetchTaxDependencies: async ({
    page = 1,
    search = "",
    taxBaseUuid,
  }: {
    page?: number;
    search?: string;
    taxBaseUuid?: string;
  }) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (taxBaseUuid) params.append("tax_base_uuid", taxBaseUuid);

    const response = await apiRequest.get(`/taxation/tax_dependency/?${params.toString()}`);

    return response.data as IPaginatedResponse<ITaxDependency>;
  },

  fetchTaxDependenciesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITaxDependency>;
  },

  createTaxDependency: async ({data}: {data: ITaxDependencyFormData}) => {
    const response = await apiRequest.post(`/taxation/tax_dependency/`, data);

    return response.data as ITaxDependency;
  },

  updateTaxDependency: async ({
    taxDependencyUuid,
    data,
  }: {
    taxDependencyUuid: string;
    data: Partial<ITaxDependencyFormData>;
  }) => {
    const response = await apiRequest.patch(`/taxation/tax_dependency/${taxDependencyUuid}/`, data);

    return response.data as ITaxDependency;
  },

  deleteTaxDependency: async ({taxDependencyUuid}: {taxDependencyUuid: string}) => {
    await apiRequest.delete(`/taxation/tax_dependency/${taxDependencyUuid}/`);
  },

  fetchTaxDependencyById: async ({taxDependencyUuid}: {taxDependencyUuid: string}) => {
    const response = await apiRequest.get(`/taxation/tax_dependency/${taxDependencyUuid}/`);

    return response.data as ITaxDependency;
  },
};

export const TAX_SCHEDULE_API = {
  fetchTaxScheduleById: async ({taxScheduleUuid}: {taxScheduleUuid: string}) => {
    const response = await apiRequest.get(`/taxation/tax_schedule/${taxScheduleUuid}/`);

    return response.data as ITaxSchedule;
  },

  updateTaxSchedule: async ({
    taxScheduleUuid,
    data,
  }: {
    taxScheduleUuid: string;
    data: Partial<ITaxScheduleFormData>;
  }) => {
    const response = await apiRequest.patch(`/taxation/tax_schedule/${taxScheduleUuid}/`, data);

    return response.data as ITaxSchedule;
  },
};

export const BANKS_API = {
  fetchBanks: async ({page = 1, search = ""}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    params.append("page", page.toString());
    if (search) params.append("search", search);

    const response = await apiRequest.get(`/bank_management/bank-accounts/?${params.toString()}`);

    return response.data as IPaginatedResponse<IBank>;
  },

  fetchBanksFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBank>;
  },

  createBank: async ({bankData}: {bankData: IBankFormData}) => {
    const response = await apiRequest.post(`/bank_management/bank-accounts/`, bankData);

    return response.data as IBank;
  },

  fetchBankById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`/bank_management/bank-accounts/${base_uuid}/`);

    return response.data as IBank;
  },

  updateBank: async ({
    base_uuid,
    bankData,
  }: {
    base_uuid: string;
    bankData: Partial<IBankFormData>;
  }) => {
    const response = await apiRequest.patch(
      `/bank_management/bank-accounts/${base_uuid}/`,
      bankData,
    );

    return response.data as IBank;
  },

  deleteBank: async ({base_uuid}: {base_uuid: string}) => {
    await apiRequest.delete(`/bank_management/bank-accounts/${base_uuid}/`);
  },
};

export const INSTITUTION_SUPPORTED_BANKS_API = {
  fetchFirstPage: async ({
    page = 1,
    search = "",
    ordering = "",
  }: {
    page?: number;
    search?: string;
    ordering?: string;
  } = {}) => {
    const params = new URLSearchParams({page: String(page)});
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);

    const response = await apiRequest.get(`/institution/supported-banks/?${params.toString()}`);
    return response.data as IPaginatedResponse<IInstitutionSupportedBank>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IInstitutionSupportedBank>;
  },

  create: async (data: {
    reference_code?: string;
    bank_name: string;
    description?: string | null;
  }) => {
    const response = await apiRequest.post("/institution/supported-banks/", data);
    return response.data as IInstitutionSupportedBank;
  },

  update: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: {
      reference_code?: string;
      bank_name: string;
      description?: string | null;
    };
  }) => {
    const response = await apiRequest.patch(`/institution/supported-banks/${baseUuid}/`, data);
    return response.data as IInstitutionSupportedBank;
  },

  delete: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`/institution/supported-banks/${baseUuid}/`);
  },
};

export const CURRENCIES_API = {
  fetchFirstPage: async (q: {
    search?: string;
    page?: number;
    is_institution_supported?: boolean;
  }) => {
    const params = new URLSearchParams();

    Object.entries(q).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v).trim() !== "") {
        params.append(k, String(v));
      }
    });

    const response = await apiRequest.get(`/user/currencies?${params.toString()}`);

    return response.data as IPaginatedResponse<Currency>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<Currency>;
  },
};

export const INSTITUTION_CURRENCIES_API = {
  fetchFirstPage: async (q: {search?: string; page?: number} = {}) => {
    const params = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v).trim() !== "") {
        params.append(k, String(v));
      }
    });
    const response = await apiRequest.get(`/institution/supported-currency/?${params.toString()}`);
    return response.data as IPaginatedResponse<IInstitutionSupportedCurrency>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IInstitutionSupportedCurrency>;
  },

  fetchById: async (baseUuid: string) => {
    const response = await apiRequest.get(`/institution/supported-currency/${baseUuid}/`);
    return response.data as IInstitutionSupportedCurrency;
  },

  patch: async (baseUuid: string, data: Partial<IInstitutionSupportedCurrency>) => {
    const response = await apiRequest.patch(`/institution/supported-currency/${baseUuid}/`, data);
    return response.data as IInstitutionSupportedCurrency;
  },

  delete: async (baseUuid: string) => {
    await apiRequest.delete(`/institution/supported-currency/${baseUuid}/`);
  },
};

export const BRANCH_INVENTORY_API = {
  fetchBranchInventory: async (params: Record<string, any> = {}) => {
    const {page, ...rest} = params;

    const urlParams = new URLSearchParams({
      branch_uuids: getAllSelectedBranchUUIDs().join(","),
      ...Object.fromEntries(
        Object.entries(rest)
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => [k, String(v)]),
      ),
      ...(page ? {page: String(page)} : {}),
    });

    const response = await apiRequest.get(`/items/branch-inventory/?${urlParams.toString()}`);
    return response.data as IPaginatedResponse<IBranchInventoryItem>;
  },
  fetchBranchInventoryFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBranchInventoryItem>;
  },

  fetchBranchInventoryItemById: async ({item_uuid}: {item_uuid: string}) => {
    const response = await apiRequest.get(`/items/branch-inventory-items/${item_uuid}/`);

    return response.data as IBranchInventoryItem;
  },

  updateBranchInventoryItem: async ({
    item_uuid,
    data,
  }: {
    item_uuid: string;
    data: IBranchInventoryItemUpdatePayload;
  }) => {
    const response = await apiRequest.patch(`/items/branch-inventory-items/${item_uuid}/`, data);
    return response.data as IBranchInventoryItem;
  },

  deleteBranchInventoryItem: async ({
    branch_uuid,
    item_base_uuid,
  }: {
    branch_uuid: string;
    item_base_uuid: string;
  }) => {
    await apiRequest.delete(
      `/items/branch-inventory/${branch_uuid}/?item_base_uuid=${item_base_uuid}`,
    );
  },

  fetchItemStockLayers: async (params: Record<string, string | number | boolean> = {}) => {
    const {page, ...rest} = params;

    const urlParams = new URLSearchParams({
      ...Object.fromEntries(Object.entries(rest).map(([k, v]) => [k, String(v)])),
      page: page ? String(page) : "1",
    });

    const response = await apiRequest.get(
      `items/branch-inventory-item-stock-layers/?${urlParams.toString()}`,
    );

    return response.data as IPaginatedResponse<any>;
  },

  fetchItemStockLayersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<any>;
  },
};

export const COMBINEDSTOCKMOVEMENTS_API = {
  fetchCombinedStockMovements: async ({
    search,
    branch_base_uuid,
    institution_base_uuid,
    movement_type,
    status,
    date_from,
    date_to,
  }: {
    search?: string;
    branch_base_uuid?: string;
    institution_base_uuid?: string;
    movement_type?: "BRANCH_TO_BRANCH" | "MAIN_TO_BRANCH";
    status?: "ALLOCATED" | "CANCELLED" | "PENDING";
    date_from?: string;
    date_to?: string;
  } = {}) => {
    const params = new URLSearchParams();

    if (search) params.append("search", search);
    if (branch_base_uuid) params.append("branch_base_uuid", branch_base_uuid);
    if (institution_base_uuid) params.append("institution_base_uuid", institution_base_uuid);
    if (movement_type) params.append("movement_type", movement_type);
    if (status) params.append("status", status);
    if (date_from) params.append("date_from", date_from);
    if (date_to) params.append("date_to", date_to);

    const query = params.toString();
    const response = await apiRequest.get(
      `items/combined-stock-movements/${query ? `?${query}` : ""}`,
    );

    return response.data as IPaginatedResponse<IStockMovementListItem>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IStockMovementListItem>;
  },
};

export const BRANCHALLOCATIONS_API = {
  fetchFirstPage: async ({search = "", page = 1}: {search?: string; page?: number}) => {
    const params = new URLSearchParams();

    if (search) params.append("search", search);
    params.append("page", page.toString());
    params.append("branch_uuids", getAllSelectedBranchUUIDs().join(",") || "");

    const response = await apiRequest.get(
      `items/stock-to-branch-allocations/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IBranchAllocation>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBranchAllocation>;
  },

  fetchBranchAllocationById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`items/stock-to-branch-allocations/${base_uuid}/`);

    return response.data as IBranchAllocation;
  },

  createBranchAllocation: async ({data}: {data: IBranchAllocationFormData}) => {
    const response = await apiRequest.post(`items/stock-to-branch-allocations/`, data);

    return response.data as IBranchAllocation;
  },

  updateBranchAllocation: async ({
    id,
    data,
  }: {
    id: string;
    data: Partial<IBranchAllocationFormData>;
  }) => {
    const response = await apiRequest.patch(`items/stock-to-branch-allocations/${id}/`, data);

    return response.data as IBranchAllocation;
  },

  deleteBranchAllocation: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`items/stock-to-branch-allocations/${base_uuid}/`);

    return response.data;
  },

  approveBranchAllocation: async ({id, comment}: {id: string; comment?: string}) => {
    const url = comment
      ? `items/stock-to-branch-allocations/${id}/approve/?comment=${encodeURIComponent(comment)}`
      : `items/stock-to-branch-allocations/${id}/approve/`;
    const response = await apiRequest.patch(url, {});

    return response.data as IBranchAllocation;
  },

  rejectBranchAllocation: async ({id, comment}: {id: string; comment?: string}) => {
    const url = comment
      ? `items/stock-to-branch-allocations/${id}/reject/?comment=${encodeURIComponent(comment)}`
      : `items/stock-to-branch-allocations/${id}/reject/`;
    const response = await apiRequest.patch(url, {});

    return response.data as IBranchAllocation;
  },
};

export const ADMIN_REPORTS_API = {
  fetchReport: async (model: string): Promise<IReport> => {
    const response = await apiRequest.get(`/reports/?model=${encodeURIComponent(model)}`);

    return response.data as IReport;
  },

  downloadReport: async (data: IReportDownloadData): Promise<Blob> => {
    return downloadFileApi({
      url: "reports/download/",
      method: "POST",
      body: {
        model: data.model,
        output_format: data.output_format,
        heading: data.heading,
        filters: data.filters || {},
        fields: data.fields || [],
      },
    });
  },
};

export const PURCHASE_CREDIT_NOTES_API = {
  fetchCreditNotes: async (query: any) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    Object.keys(query).forEach((key) => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        params.append(key, query[key].toString());
      }
    });

    const response = await apiRequest.get(`customers/credit-debit-notes/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICreditNote>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICreditNote>;
  },

  createCreditNote: async ({data}: {data: ICreditNoteFormData}) => {
    const response = await apiRequest.post(`customers/credit-debit-notes/`, {
      ...data,
      type: "CREDIT",
      falls_under: "PURCHASE",
    });

    return response.data as ICreditNote;
  },

  updateCreditNote: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<ICreditNoteFormData>;
  }) => {
    const response = await apiRequest.patch(`customers/credit-debit-notes/${base_uuid}/`, data);

    return response.data as ICreditNote;
  },

  deleteCreditNote: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`customers/credit-debit-notes/${base_uuid}/`);

    return response.data;
  },

  fetchCreditNote: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`customers/credit-debit-notes/${base_uuid}/`);

    return response.data as ICreditNote;
  },
};

export const PURCHASE_DEBIT_NOTES_API = {
  fetchDebitNotes: async (query: any) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    Object.keys(query).forEach((key) => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        params.append(key, query[key].toString());
      }
    });

    const response = await apiRequest.get(`customers/credit-debit-notes/?${params.toString()}`);

    return response.data as IPaginatedResponse<IDebitNote>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IDebitNote>;
  },

  createDebitNote: async ({data}: {data: IDebitNoteFormData}) => {
    const response = await apiRequest.post(`customers/credit-debit-notes/`, {
      ...data,
      type: "DEBIT",
      falls_under: "PURCHASE",
    });

    return response.data as IDebitNote;
  },

  updateDebitNote: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<IDebitNoteFormData>;
  }) => {
    const response = await apiRequest.patch(`customers/credit-debit-notes/${base_uuid}/`, data);

    return response.data as IDebitNote;
  },

  deleteDebitNote: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`customers/credit-debit-notes/${base_uuid}/`);

    return response.data;
  },

  fetchDebitNote: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`customers/credit-debit-notes/${base_uuid}/`);

    return response.data as IDebitNote;
  },
};

export const SALES_CREDIT_NOTES_API = {
  fetchCreditNotes: async (query: any) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    Object.keys(query).forEach((key) => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        params.append(key, query[key].toString());
      }
    });

    const response = await apiRequest.get(`customers/credit-debit-notes/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICreditNote>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICreditNote>;
  },

  createCreditNote: async ({data}: {data: ICreditNoteFormData}) => {
    const response = await apiRequest.post(`customers/credit-debit-notes/`, {
      ...data,
      type: "CREDIT",
      falls_under: "SALES",
    });

    return response.data as ICreditNote;
  },

  updateCreditNote: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<ICreditNoteFormData>;
  }) => {
    const response = await apiRequest.patch(`customers/credit-debit-notes/${base_uuid}/`, data);

    return response.data as ICreditNote;
  },

  deleteCreditNote: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`customers/credit-debit-notes/${base_uuid}/`);

    return response.data;
  },

  fetchCreditNote: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`customers/credit-debit-notes/${base_uuid}/`);

    return response.data as ICreditNote;
  },

  fetchLineItems: async ({noteUuid, page = 1}: {noteUuid: string; page?: number}) => {
    const response = await apiRequest.get(
      `customers/credit-debit-notes/${noteUuid}/line-items/?page=${page}`,
    );
    return response.data as IPaginatedResponse<ICreditNoteLineItem>;
  },

  fetchLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ICreditNoteLineItem>;
  },

  downloadSalesCreditNotePDF: async ({noteUUID}: {noteUUID: string}) => {
    return downloadFileApi({
      url: `customers/credit-note-report-download/${noteUUID}`,
      expectedMime: "pdf",
    });
  },
};

export const CASHBOOK_REQUEST_API = {
  fetchCashBookRequests: async (query: any) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    Object.keys(query).forEach((key) => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        params.append(key, query[key].toString());
      }
    });

    const response = await apiRequest.get(`accounts/imprest-requests/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICashBookRequisition>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICashBookRequisition>;
  },
  fetchCashBookRequest: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`accounts/imprest-requests/${base_uuid}/`);

    return response.data as ICashBookRequisition;
  },
  deleteCashBookRequest: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`accounts/imprest-requests/${base_uuid}/`);

    return {
      data: response.data,
      status: response.status,
    };
  },

  createCashBookRequest: async ({data}: {data: ICashBookRequisitionFormData}) => {
    const response = await apiRequest.post("accounts/imprest-requests/", data);

    return response.data as ICashBookRequisition;
  },
  updateCashBookRequest: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<ICashBookRequisitionFormData>;
  }) => {
    const response = await apiRequest.patch(`accounts/imprest-requests/${base_uuid}/`, data);

    return response.data as ICashBookRequisition;
  },
  linkCashBookRequestRequisition: async ({
    base_uuid,
    requisition,
  }: {
    base_uuid: string;
    requisition?: string;
  }) => {
    const response = await apiRequest.post(
      `accounts/imprest-requests/${base_uuid}/requisition/`,
      requisition ? {requisition} : {},
    );

    return response.data as ICashBookRequisition;
  },
};

export const CASHBOOK_CREDIT_API = {
  fetchCashBookCredits: async (query: any) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    Object.keys(query).forEach((key) => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        params.append(key, query[key].toString());
      }
    });

    const response = await apiRequest.get(`accounts/cash-book-topups/?${params.toString()}`);

    return response.data as IPaginatedResponse<ICashBookCredit>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ICashBookCredit>;
  },
  fetchCashBookCredit: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`accounts/cash-book-topups/${base_uuid}/`);

    return response.data as ICashBookCredit;
  },
  deleteCashBookCredit: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`accounts/cash-book-topups/${base_uuid}/`);

    return response.data as ICashBookCredit;
  },
  createCashBookCredit: async ({data}: {data: ICashBookCreditFormData}) => {
    const response = await apiRequest.post(`accounts/cash-book-topups/`, data);

    return response.data as ICashBookCredit;
  },
  updateCashBookCredit: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<ICashBookCreditFormData>;
  }) => {
    const response = await apiRequest.patch(`accounts/cash-book-topups/${base_uuid}/`, data);

    return response.data as ICashBookCredit;
  },
};

export const DEPRECIATION_METHODS_API = {
  fetchDepreciationMethods: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    const response = await apiRequest.get(
      `fixed_assets/system-depreciation-methods/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IDepreciationMethod>;
  },

  fetchDepreciationMethodsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IDepreciationMethod>;
  },
};

export interface AssetDepreciationScheduleRow {
  depreciation_base_uuid: string | null;
  reference_code: string | null;
  entry_date: string;
  period_start: string;
  period_end: string;
  depreciation_amount: string;
  accumulated_depreciation: string;
  net_book_value: string;
  status: "Applied" | "Pending approval" | "Not applied" | "Future";
  can_apply: boolean;
}

export interface AssetDepreciationScheduleResponse {
  results: AssetDepreciationScheduleRow[];
  next: string | null;
  previous: string | null;
  count: number;
  can_apply_due: boolean;
  notice: string;
}

export const DEPRECIATION_API = {
  fetchAssetSchedule: async ({assetUuid, page = 1}: {assetUuid: string; page?: number}) => {
    const query = new URLSearchParams({
      fixed_asset_base_uuid: assetUuid,
      page: String(page),
    });
    const response = await apiRequest.get(
      `fixed_assets/proposed-netbook-value-depreciation-entry/?${query}`,
    );

    return response.data as AssetDepreciationScheduleResponse;
  },
  fetchDepreciations: async ({
    page = 1,
    search,
    base_uuid,
  }: {
    page?: number;
    search?: string;
    base_uuid?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (base_uuid) params.append("asset_base_uuid", base_uuid);
    const response = await apiRequest.get(
      `fixed_assets/depreciation_entries/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IDepreciation>;
  },

  fetchDepreciationFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IDepreciation>;
  },

  fetchDepreciationById: async ({depreciation_uuid}: {depreciation_uuid: string}) => {
    const response = await apiRequest.get(`fixed_assets/depreciation_entry/${depreciation_uuid}/`);

    return response.data as IDepreciation;
  },
  createDepreciation: async ({data}: {data: IDepreciationItemFormData}) => {
    const response = await apiRequest.post(`fixed_assets/depreciation_entries/`, data);

    return response.data as IDepreciationItemFormData;
  },
  updateDepreciation: async ({
    depreciation_uuid,
    data,
  }: {
    depreciation_uuid: string;
    data: Partial<IDepreciationItemFormData>;
  }) => {
    const response = await apiRequest.patch(
      `fixed_assets/depreciation_entry/${depreciation_uuid}/`,
      data,
    );

    return response.data as IDepreciationItemFormData;
  },
  deleteDepreciation: async ({depreciation_uuid}: {depreciation_uuid: string}) => {
    const response = await apiRequest.delete(
      `fixed_assets/depreciation_entry/${depreciation_uuid}/`,
    );

    return response.data as IDepreciation;
  },

  createDepreciationAuto: async ({
    data,
  }: {
    data: {
      fixed_asset_base_uuid: string;
      entry_date?: string;
      entry_dates?: string[];
    };
  }) => {
    const response = await apiRequest.post(
      "fixed_assets/depreciation-entry/system-supported/manual/",
      data,
    );

    return response.data as {entries_created: number; message: string};
  },
};

export const BUSINESS_DOCUMENTS_API = {
  fetchDocuments: async ({
    page = 1,
    search,
    filterBy, // "all" | "institution" | "branch"
    ordering,
    business_document_category_base_uuid,
  }: {
    page?: number;
    search?: string;
    filterBy?: string;
    ordering?: string;
    business_document_category_base_uuid?: string;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (search) params.append("search", search);
    if (filterBy) params.append("filter_by", filterBy);
    if (ordering) params.append("ordering", ordering);
    if (business_document_category_base_uuid)
      params.append("business_document_category_base_uuid", business_document_category_base_uuid);

    const response = await apiRequest.get(`/institution/documents/?${params.toString()}`);

    return response.data as IPaginatedResponse<IBusinessDocument>;
  },

  fetchDocumentsFromUrl: async ({
    url,
    extraParams,
  }: {
    url: string;
    extraParams?: Record<string, string | undefined>;
  }) => {
    const parsedUrl = new URL(url, process.env.NEXT_PUBLIC_BASE_URL);

    if (extraParams) {
      Object.entries(extraParams).forEach(([key, value]) => {
        if (value && !parsedUrl.searchParams.has(key)) {
          parsedUrl.searchParams.append(key, value);
        }
      });
    }

    const response = await apiRequest.get(parsedUrl.toString());

    return response.data as IPaginatedResponse<IBusinessDocument>;
  },

  fetchDocumentById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`/institution/documents/${base_uuid}/`);

    return response.data as IBusinessDocument;
  },

  createDocument: async ({data}: {data: Record<string, any>}) => {
    const response = await apiRequest.post(`/institution/documents/`, data);
    return response.data as IBusinessDocument;
  },

  updateDocument: async ({base_uuid, data}: {base_uuid: string; data: Record<string, any>}) => {
    const response = await apiRequest.patch(`/institution/documents/${base_uuid}/`, data);
    return response.data as IBusinessDocument;
  },

  deleteDocument: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`/institution/documents/${base_uuid}/`);

    return response.data as IBusinessDocument;
  },
};

export const BUSINESS_DOCUMENT_CATEGORIES_API = {
  fetchDocuments: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);

    const response = await apiRequest.get(`/institution/docs-category?${params.toString()}`);

    return response.data as IPaginatedResponse<IBusinessDocumentCategory>;
  },

  fetchDocumentsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBusinessDocumentCategory>;
  },
};

export const ASSET_DISPOSAL_API = {
  fetchAssetDisposals: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);

    const response = await apiRequest.get(`/fixed_assets/asset-disposals/?${params.toString()}`);

    return response.data as IPaginatedResponse<IAssetDisposal>;
  },

  fetchAssetDisposalsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IAssetDisposal>;
  },

  createAssetDisposal: async ({data}: {data: IAssetDisposalFormData}) => {
    const response = await apiRequest.post(`/fixed_assets/asset-disposals/`, data);

    return response.data as IAssetDisposal;
  },

  updateAssetDisposal: async ({
    disposalUuid,
    data,
  }: {
    disposalUuid: string;
    data: IAssetDisposalFormData;
  }) => {
    const response = await apiRequest.patch(`/fixed_assets/asset-disposals/${disposalUuid}/`, data);

    return response.data as IAssetDisposal;
  },

  deleteAssetDisposal: async ({disposalUuid}: {disposalUuid: string}) => {
    await apiRequest.delete(`/fixed_assets/asset-disposals/${disposalUuid}/`);
  },

  fetchAssetDisposalById: async ({disposalUuid}: {disposalUuid: string}) => {
    const response = await apiRequest.get(`/fixed_assets/asset-disposals/${disposalUuid}/`);

    return response.data as IAssetDisposal;
  },
};

export const ASSET_DISPOSAL_TYPES_API = {
  fetchAssetDisposalTypes: async () => {
    const response = await apiRequest.get("/fixed_assets/system-disposal-types/");

    return response.data as IPaginatedResponse<IAssetDisposalType>;
  },
  fetchAssetDisposalTypesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IAssetDisposalType>;
  },
};

export const BANK_STATEMENT_API = {
  fetch: async (query: any = {}) => {
    const params = new URLSearchParams({
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    Object.keys(query).forEach((key) => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== "") {
        params.append(key, query[key].toString());
      }
    });

    const response = await apiRequest.get(`bank_management/bank-statement/?${params.toString()}`);

    return response.data as IPaginatedResponse<IBankStatement>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBankStatement>;
  },

  create: async ({data}: {data: IBankStatementFormData}) => {
    const response = await apiRequest.post(`bank_management/bank-statement/`, data);

    return response.data as IBankStatement;
  },

  update: async ({base_uuid, data}: {base_uuid: string; data: Partial<IBankStatementFormData>}) => {
    const response = await apiRequest.patch(`bank_management/bank-statement/${base_uuid}/`, data);

    return response.data as IBankStatement;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`bank_management/bank-statement/${base_uuid}/`);

    return response.data;
  },

  fetchOne: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`bank_management/bank-statement/${base_uuid}/`);

    return response.data as IBankStatement;
  },
};

export const BANK_STATEMENT_TRANSACTIONS_API = {
  fetch: async ({
    page = 1,
    search,
    bank_base_uuid,
  }: {
    page?: number;
    search?: string;
    bank_base_uuid: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (bank_base_uuid) params.append("bank_base_uuid", bank_base_uuid);
    const response = await apiRequest.get(
      `bank_management/bank-statement-transactions/?${params.toString()}`,
    );

    return response.data as IPaginatedResponse<IBankStatementTransaction>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBankStatementTransaction>;
  },

  create: async ({data}: {data: IBankStatementTransactionFormData}) => {
    const response = await apiRequest.post(`bank_management/bank-statement-transactions/`, data);

    return response.data as IBankStatementTransaction;
  },

  update: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<IBankStatementTransactionFormData>;
  }) => {
    const response = await apiRequest.patch(
      `bank_management/bank-statement-transactions/${base_uuid}/`,
      data,
    );

    return response.data as IBankStatementTransaction;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(
      `bank_management/bank-statement-transactions/${base_uuid}/`,
    );

    return response.data;
  },

  fetchOne: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(
      `bank_management/bank-statement-transactions/${base_uuid}/`,
    );

    return response.data as IBankStatementTransaction;
  },
};

export const DOCUMENT_CATEGORY_API = {
  fetch: async ({
    page = 1,
    search,
    ordering,
  }: {
    page?: number;
    search?: string;
    ordering?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);

    const response = await apiRequest.get(`institution/document-category/?${params.toString()}`);

    return response.data as IPaginatedResponse<IDocumentCatergory>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IDocumentCatergory>;
  },

  create: async ({data}: {data: IDocumentCatergoryFormData | IDocumentCatergoryFormData[]}) => {
    const dataArray = Array.isArray(data) ? data : [data];

    const response = await apiRequest.post(`institution/document-category/`, dataArray);
    return Array.isArray(data) ? response.data : response.data[0];
  },

  update: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<IDocumentCatergoryFormData>;
  }) => {
    const response = await apiRequest.patch(`institution/document-category/${base_uuid}/`, data);

    return response.data as IDocumentCatergory;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`institution/document-category/${base_uuid}/`);

    return response.data;
  },

  fetchOne: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`institution/document-category/${base_uuid}/`);

    return response.data as IDocumentCatergory;
  },
};

export const INVENTORY_ITEM_RETURNS_API = {
  fetchInventoryItemReturns: async (args: any) => {
    const q = args.query ?? args;
    const params = toParams({
      page: args.page ?? q.page ?? 1,
      search: q.search,
      return_reason_uuid: q.return_reason_uuid,
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || undefined,
    });

    const response = await apiRequest.get(`customers/item-returns/?${params.toString()}`);

    return response.data as IPaginatedResponse<IInventoryItemReturn>;
  },

  fetchInventoryItemReturnsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IInventoryItemReturn>;
  },

  create: async ({data}: {data: IInventoryItemReturnFormData}) => {
    const response = await apiRequest.post("customers/item-returns/", data);

    return response.data as IInventoryItemReturn;
  },

  update: async ({
    returnUuid,
    data,
  }: {
    returnUuid: string;
    data: Partial<IInventoryItemReturnFormData>;
  }) => {
    const response = await apiRequest.patch(`customers/item-returns/${returnUuid}/`, data);

    return response.data as IInventoryItemReturn;
  },

  fetchOne: async ({returnUuid}: {returnUuid: string}) => {
    const response = await apiRequest.get(`customers/item-returns/${returnUuid}/`);

    return response.data as IInventoryItemReturn;
  },

  fetchLineItems: async ({returnUuid, page = 1}: {returnUuid: string; page?: number}) => {
    const response = await apiRequest.get(
      `customers/item-returns/${returnUuid}/line-items/?page=${page}`,
    );

    return response.data as IPaginatedResponse<ReturnedItem>;
  },

  fetchLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<ReturnedItem>;
  },

  delete: async ({returnUuid}: {returnUuid: string}) => {
    const response = await apiRequest.delete(`customers/item-returns/${returnUuid}/`);

    return response.data;
  },

  downloadItemReturnPDF: async ({returnUuid}: {returnUuid: string}) => {
    return downloadFileApi({
      url: `customers/item-return-report-download/${returnUuid}`,
      expectedMime: "pdf",
    });
  },
};

export const RETURN_REASONS_API = {
  fetchAll: async ({search, ordering}: {search?: string; ordering?: string}) => {
    const params = new URLSearchParams({page: "1"});
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);

    const response = await apiRequest.get(`institution/item-return-reasons/?${params.toString()}`);
    return response.data as IPaginatedResponse<IReturnReason>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IReturnReason>;
  },

  create: async ({data}: {data: IReturnReasonFormData}) => {
    const response = await apiRequest.post(`institution/item-return-reasons/`, data);

    return response.data as IReturnReason;
  },

  update: async ({base_uuid, data}: {base_uuid: string; data: Partial<IReturnReasonFormData>}) => {
    const response = await apiRequest.patch(`institution/item-return-reasons/${base_uuid}/`, data);

    return response.data as IReturnReason;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`institution/item-return-reasons/${base_uuid}/`);

    return response.data;
  },

  fetchById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`institution/item-return-reasons/${base_uuid}/`);

    return response.data as IReturnReason;
  },
};

export const TAX_RETURNS_API = {
  fetchAll: async ({
    page = 1,
    search,
    start_date,
    end_date,
  }: {
    page?: number;
    search?: string;
    start_date?: string;
    end_date?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (start_date) params.append("start_date", start_date);
    if (end_date) params.append("end_date", end_date);

    const response = await apiRequest.get(`taxation/taxation/returns/?${params.toString()}`);

    return response.data as IPaginatedResponse<ITaxReturn>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITaxReturn>;
  },

  create: async ({data}: {data: ITaxReturnFormData}) => {
    const response = await apiRequest.post(`taxation/taxation/returns/`, data);

    return response.data as ITaxReturn;
  },

  previewTaxReturn: async ({data}: {data: ITaxReturnFormData}) => {
    const response = await apiRequest.post(`taxation/taxation/returns/preview/`, data);

    return response.data as ITaxReturn;
  },

  update: async ({base_uuid, data}: {base_uuid: string; data: Partial<ITaxReturnFormData>}) => {
    const response = await apiRequest.patch(`taxation/taxation/returns/${base_uuid}/`, data);

    return response.data as ITaxReturn;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`taxation/taxation/returns/${base_uuid}/`);

    return response.data;
  },

  fetchById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`taxation/taxation/returns/${base_uuid}/`);

    return response.data as ITaxReturn;
  },

  fileTax: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.post(`taxation/returns/${base_uuid}/file/`, {});

    return response.data as ITaxReturn;
  },
};

export const TAX_PAYMENTS_API = {
  fetchAll: async ({
    page = 1,
    search,
    prn,
    status,
    tax_return_uuid,
  }: {
    page?: number;
    search?: string;
    prn?: string;
    status?: string;
    tax_return_uuid?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (prn) params.append("prn", prn);
    if (status) params.append("status", status);
    if (tax_return_uuid) params.append("tax_return_uuid", tax_return_uuid);

    const response = await apiRequest.get(`taxation/taxation/payments/?${params.toString()}`);

    return response.data as IPaginatedResponse<ITaxPayment>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<ITaxPayment>;
  },

  create: async ({data}: {data: ITaxPaymentFormData}) => {
    const response = await apiRequest.post(`taxation/taxation/payments/`, data);

    return response.data as ITaxPayment;
  },

  update: async ({base_uuid, data}: {base_uuid: string; data: Partial<ITaxPaymentFormData>}) => {
    const response = await apiRequest.patch(`taxation/taxation/payments/${base_uuid}/`, data);

    return response.data as ITaxPayment;
  },

  delete: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`taxation/taxation/payments/${base_uuid}/`);

    return response.data;
  },

  fetchById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`taxation/taxation/payments/${base_uuid}/`);

    return response.data as ITaxPayment;
  },
};

export const BRANCHES_API = {
  fetchAll: async ({
    page = 1,
    search,
    parent_base_uuid,
    has_requisitions,
    has_expenses,
  }: {
    page?: number;
    search?: string;
    parent_base_uuid?: string;
    has_requisitions?: boolean;
    has_expenses?: boolean;
  }) => {
    const params = new URLSearchParams({page: page.toString()});

    if (search) params.append("search", search);
    if (parent_base_uuid) params.append("parent_base_uuid", parent_base_uuid);
    if (has_requisitions !== undefined) {
      params.append("has_requisitions", String(has_requisitions));
    }
    if (has_expenses !== undefined) {
      params.append("has_expenses", String(has_expenses));
    }

    const response = await apiRequest.get(`institution/branch/?${params.toString()}`);

    return response.data as IPaginatedResponse<Branch>;
  },
  fetchAllFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<Branch>;
  },
  deleteBranch: async ({branchId}: {branchId: string}) => {
    const response = await apiRequest.delete(`institution/branch/${branchId}/`);

    return response.data;
  },
  fetchById: async ({branchId}: {branchId: string}) => {
    const response = await apiRequest.get(`institution/branch/${branchId}/`);

    return response.data as Branch;
  },
  updateBranch: async ({branchId, data}: {branchId: string; data: Partial<IBranchFormData>}) => {
    const response = await apiRequest.patch(`institution/branch/${branchId}/`, data);

    return response.data as Branch;
  },
  createBranch: async ({data}: {data: IBranchFormData}) => {
    const response = await apiRequest.post(`institution/branch/`, data);

    return response.data as Branch;
  },
};

export const BRANCH_SUPPORTED_CURRENCIES_API = {
  fetchAll: async ({
    page = 1,
    search,
    branch_base_uuid,
  }: {
    page?: number;
    search?: string;
    branch_base_uuid: string;
  }) => {
    const params = new URLSearchParams({page: page?.toString()});
    params.append("branch_base_uuid", branch_base_uuid);

    if (search) params.append("search", search);
    const response = await apiRequest.get(
      `institution/branch-supported-currency/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IBranchSupportedCurrency>;
  },

  fetchAllFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBranchSupportedCurrency>;
  },

  fetchById: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.get(`institution/branch-supported-currency/${base_uuid}/`);
    return response.data as IBranchSupportedCurrency;
  },

  deleteBranchSupportedCurrency: async ({base_uuid}: {base_uuid: string}) => {
    const response = await apiRequest.delete(`institution/branch-supported-currency/${base_uuid}/`);
    return response.data;
  },

  updateBranchSupportedCurrency: async ({
    base_uuid,
    data,
  }: {
    base_uuid: string;
    data: Partial<IBranchSupportedCurrency>;
  }) => {
    const response = await apiRequest.patch(
      `institution/branch-supported-currency/${base_uuid}/`,
      data,
    );
    return response.data as IBranchSupportedCurrency;
  },

  createBranchSupportedCurrency: async ({data}: {data: IBranchSupportedCurrency}) => {
    const response = await apiRequest.post(`institution/branch-supported-currency/`, data);
    return response.data as IBranchSupportedCurrency;
  },
};

export const SYSTEM_PERMISSION_CATEGORIES = {
  fetchPermissionCategories: async ({
    page = 1,
    search,
    roleBaseUuid,
  }: {
    page?: number;
    search?: string;
    roleBaseUuid?: string;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (search) {
      params.append("search", search);
    }
    if (roleBaseUuid) {
      params.append("role_base_uuid", roleBaseUuid);
    }

    const response = await apiRequest.get(`/user/permission-category/?${params.toString()}`);

    return response.data as IPaginatedResponse<IPermissionCategory>;
  },

  fetchPermissionCategoriesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IPermissionCategory>;
  },
};

export const SYSTEM_PERMISSION = {
  fetchSystemPermissions: async ({
    page = 1,
    search,
    categoryBaseUuid,
  }: {
    page?: number;
    search?: string;
    categoryBaseUuid?: string;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (categoryBaseUuid) {
      params.append("permission_category_base_uuid", categoryBaseUuid);
    }
    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`user/permission/?${params.toString()}`);

    return response.data as IPaginatedResponse<Permission>;
  },

  fetchSystemPermissionsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<Permission>;
  },
};

export const INSTITUTION_STAFF_API = {
  fetchInstitutionStaff: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = new URLSearchParams({
      page: page.toString(),
      branch_base_uuid: getAllSelectedBranchUUIDs().join(",") || "",
    });

    if (search) {
      params.append("search", search);
    }

    const response = await apiRequest.get(`/institution/profile/?${params.toString()}`);

    return response.data as IPaginatedResponse<IUser>;
  },

  fetchInstitutionStaffFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IUser>;
  },

  createStaff: async ({staffData}: {staffData: IStaffFormData}) => {
    const response = await apiRequest.post(`institution/profile/`, staffData);
    return response.data as IProfile;
  },

  updateStaff: async ({
    staffUuid,
    staffData,
  }: {
    staffUuid: string | number;
    staffData: IStaffFormData | FormData;
  }) => {
    const response = await apiRequest.patch(`institution/profile/${staffUuid}/`, staffData);
    return response.data as IProfile;
  },

  deleteStaff: async ({staffUuid}: {staffUuid: string}) => {
    await apiRequest.delete(`institution/profile/${staffUuid}/`);
  },

  fetchStaffById: async ({staffUuid}: {staffUuid: string | number}) => {
    const response = await apiRequest.get(`institution/profile/user/${staffUuid}/`);
    return response.data as IProfile;
  },
};

export const SYSTEM_INDUSTRIES_API = {
  fetchSystemIndustries: async ({page = 1, search}: {page?: number; search?: string}) => {
    const params = toParams({
      page: page.toString(),
      branch_uuids: getAllSelectedBranchUUIDs().join(",") || "",
      search: search,
    });

    const response = await apiRequest.get(`/institution/system-industries/?${params.toString()}`);

    return response.data as IPaginatedResponse<IIndustry>;
  },

  fetchSystemIndustriesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IIndustry>;
  },

  fetchById: async ({industryUuid}: {industryUuid: string}) => {
    const response = await apiRequest.get(`institution/system-industries/${industryUuid}/`);

    return response.data as IIndustry;
  },
};
