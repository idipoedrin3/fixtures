import apiRequest from "./api-request";
import type {
  IAllocationPreviewResponse,
  ILender,
  ILenderFormData,
  ILoan,
  ILoanCreateData,
  ILoanDetail,
  ILoanRepayment,
  ILoanRepaymentCreateData,
  ILoanSchedulePreviewResponse,
  ILoanScheduleResponse,
  IAllocationPreviewRequest,
} from "#/_types/loans.types";
import type {IPaginatedResponse} from "#/_types/api.types";

type ListQuery = {page?: number; search?: string; ordering?: string};

function queryString({page = 1, search = "", ordering = ""}: ListQuery = {}) {
  return new URLSearchParams({
    page: String(page),
    search,
    ordering,
  }).toString();
}

export const LOANS_API = {
  downloadSchedule: async (data: ILoanCreateData): Promise<Blob> =>
    (
      await apiRequest.post("loan_mgt/loans/schedule-preview/?download=csv", data, {
        responseType: "blob",
      })
    ).data,
  detail: async (uuid: string): Promise<ILoanDetail> =>
    (await apiRequest.get(`loan_mgt/loans/${uuid}/`)).data,
  update: async (
    uuid: string,
    data: Partial<Omit<ILoanCreateData, "reference_code">>,
  ): Promise<ILoanDetail> => (await apiRequest.patch(`loan_mgt/loans/${uuid}/`, data)).data,
  previewSchedule: async (data: ILoanCreateData): Promise<ILoanSchedulePreviewResponse> =>
    (await apiRequest.post("loan_mgt/loans/schedule-preview/", data)).data,
  previewScheduleFromUrl: async (
    {url}: {url: string},
    data: ILoanCreateData,
  ): Promise<ILoanSchedulePreviewResponse> => (await apiRequest.post(url, data)).data,
  schedule: async (uuid: string, query: ListQuery = {}): Promise<ILoanScheduleResponse> =>
    (await apiRequest.get(`loan_mgt/loans/${uuid}/schedule/?${queryString(query)}`)).data,
  scheduleFromUrl: async ({url}: {url: string}): Promise<ILoanScheduleResponse> =>
    (await apiRequest.get(url)).data,
  create: async (data: ILoanCreateData): Promise<ILoan> =>
    (await apiRequest.post("loan_mgt/loans/", data)).data,
  list: async (query: ListQuery = {}): Promise<IPaginatedResponse<ILoan>> =>
    (await apiRequest.get(`loan_mgt/loans/?${queryString(query)}`)).data,
  fromUrl: async ({url}: {url: string}): Promise<IPaginatedResponse<ILoan>> =>
    (await apiRequest.get(url)).data,
};

export const LOAN_REPAYMENTS_API = {
  list: async (
    loanUuid: string,
    query: ListQuery = {},
  ): Promise<IPaginatedResponse<ILoanRepayment>> =>
    (await apiRequest.get(`loan_mgt/loans/${loanUuid}/repayments/?${queryString(query)}`)).data,
  fromUrl: async ({url}: {url: string}): Promise<IPaginatedResponse<ILoanRepayment>> =>
    (await apiRequest.get(url)).data,
  create: async (loanUuid: string, data: ILoanRepaymentCreateData): Promise<ILoanRepayment> =>
    (await apiRequest.post(`loan_mgt/loans/${loanUuid}/repayments/`, data)).data,
  update: async (
    loanUuid: string,
    paymentUuid: string,
    data: Partial<ILoanRepaymentCreateData>,
  ): Promise<ILoanRepayment> =>
    (await apiRequest.patch(`loan_mgt/loans/${loanUuid}/repayments/${paymentUuid}/`, data)).data,
  previewAllocation: async (
    loanUuid: string,
    request: IAllocationPreviewRequest,
  ): Promise<IAllocationPreviewResponse> =>
    (await apiRequest.post(`loan_mgt/loans/${loanUuid}/repayments/allocation-preview/`, request))
      .data,
};

export const LENDERS_API = {
  list: async (query: ListQuery = {}): Promise<IPaginatedResponse<ILender>> =>
    (await apiRequest.get(`loan_mgt/lenders/?${queryString(query)}`)).data,
  fromUrl: async ({url}: {url: string}): Promise<IPaginatedResponse<ILender>> =>
    (await apiRequest.get(url)).data,
  detail: async (uuid: string): Promise<ILender> =>
    (await apiRequest.get(`loan_mgt/lenders/${uuid}/`)).data,
  create: async (data: ILenderFormData): Promise<ILender> =>
    (await apiRequest.post("loan_mgt/lenders/", data)).data,
  update: async (uuid: string, data: ILenderFormData): Promise<ILender> =>
    (await apiRequest.patch(`loan_mgt/lenders/${uuid}/`, data)).data,
  remove: async (uuid: string): Promise<"deleted" | "pending"> => {
    const response = await apiRequest.delete(`loan_mgt/lenders/${uuid}/`);
    return response.status === 202 ? "pending" : "deleted";
  },
};
