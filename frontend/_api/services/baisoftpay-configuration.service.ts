import apiRequest from "#/_api/api-request";
import {IPaginatedResponse} from "#/_types/api.types";

export type BaisoftPayConfigurationBranch = {
  base_uuid: string;
  branch_name: string;
};

export type BaisoftPayConfiguration = {
  base_uuid: string;
  branch: BaisoftPayConfigurationBranch | null;
  has_api_key: boolean;
  has_signing_key: boolean;
  last_verified_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BaisoftPayConfigurationPayload = {
  branch: string | null;
  api_key?: string;
  signing_key?: string;
  is_active: boolean;
};

const BASE_URL = "institution/baisoftpay-configurations/";

export const BAISOFTPAY_CONFIGURATION_API = {
  list: async ({page = 1}: {page?: number} = {}) => {
    const response = await apiRequest.get(BASE_URL, {page});
    return response.data as IPaginatedResponse<BaisoftPayConfiguration>;
  },

  listFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<BaisoftPayConfiguration>;
  },

  create: async (data: BaisoftPayConfigurationPayload) => {
    const response = await apiRequest.post(BASE_URL, data);
    return response.data as BaisoftPayConfiguration;
  },

  update: async (baseUuid: string, data: Partial<BaisoftPayConfigurationPayload>) => {
    const response = await apiRequest.patch(`${BASE_URL}${baseUuid}/`, data);
    return response.data as BaisoftPayConfiguration;
  },

  remove: async (baseUuid: string) => {
    await apiRequest.delete(`${BASE_URL}${baseUuid}/`);
  },

  verify: async (baseUuid: string) => {
    const response = await apiRequest.post(`${BASE_URL}${baseUuid}/verify/`, {});
    return response.data as {
      success: boolean;
      detail: string;
      last_verified_at: string;
    };
  },
};
