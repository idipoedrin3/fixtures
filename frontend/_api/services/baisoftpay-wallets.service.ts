import apiRequest from "#/_api/api-request";
import {IPaginatedResponse} from "#/_types/api.types";

export type BaisoftPayWallet = {
  public_id: string;
  name: string;
  available_balance: string;
  reserved_balance: string;
  is_active: boolean;
  is_blocked: boolean;
  is_synced: boolean;
  local_wallet_base_uuid: string | null;
};

export const BAISOFTPAY_WALLETS_API = {
  list: async (configId: string, page = 1) => {
    const response = await apiRequest.get(`system/baisoftpay/wallets/${configId}/`, {
      page,
      page_size: 20,
    });
    return response.data as IPaginatedResponse<BaisoftPayWallet>;
  },

  listFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<BaisoftPayWallet>;
  },

  sync: async (
    configId: string,
    wallet: {
      public_id: string;
      email?: string;
      currency: string;
      custodian?: string;
      auto_create_ledger_account: boolean;
      charts_of_accounts_reference?: string;
    },
  ) => {
    const response = await apiRequest.post("system/baisoftpay/wallets-sync/", {
      config_base_uuid: configId,
      digital_wallets: [wallet],
    });
    return response.data as {
      success: boolean;
      synchronized_wallets: Array<{
        public_id: string;
        base_uuid: string;
        created: boolean;
      }>;
    };
  },
};
