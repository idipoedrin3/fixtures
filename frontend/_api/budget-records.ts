import apiRequest from "./api-request";
import type {ApprovableEntityStatus} from "#/_types/approvals.types";
import type {IPaginatedResponse} from "#/_types/api.types";

export type BudgetSummary = {
  base_uuid: string;
  reference_code: string | null;
  start_date: string;
  end_date: string;
};

export type BudgetItemAllocationInput = {
  base_uuid?: string;
  amount: string;
  start_date: string;
  end_date: string;
  description: string;
  reference_code: string;
  external_base_uuid: string;
};

export type BudgetItemAllocationRecord = BudgetItemAllocationInput & {
  base_uuid: string;
  model_content_type_id: number;
  status: "under_review" | "rejected" | "approved";
  approval_status: ApprovableEntityStatus;
  approvals: {status: string}[];
};

export type BudgetItemRecord = {
  base_uuid: string;
  reference_code: string | null;
  name: string;
  description: string | null;
  budget: string;
  budget_details: BudgetSummary;
  budget_type: string;
  budget_type_name: string;
  allowed_movement_types: "inflow" | "outflow" | "both";
  account: string;
  account_name: string;
  movement_type: "inflow" | "outflow" | null;
  total_amount: string;
  allocations?: BudgetItemAllocationRecord[];
  created_at: string;
  updated_at: string;
};

export type BudgetItemInput = {
  allocations: BudgetItemAllocationInput[];
  budget: string;
  budget_type: string;
  account: string;
  name: string;
  description?: string;
  reference_code?: string;
  movement_type?: "inflow" | "outflow" | null;
};

export type BudgetAdjustmentType = "amendment" | "reallocation" | "supplementary";

export type BudgetAdjustmentRecord = {
  base_uuid: string;
  reference_code: string | null;
  title: string;
  adjustment_types: BudgetAdjustmentType[];
  status: "draft" | "under_review" | "rejected" | "approved";
  approval_status: string;
  budget_details: BudgetSummary;
  created_at: string;
};

export type BudgetRecordQuery = {
  search?: string;
  budget__base_uuid?: string;
};

function listEndpoint<T>(path: string) {
  return {
    async fetchFirstPage({page = 1, query = {}}: {page?: number; query?: BudgetRecordQuery}) {
      const params = new URLSearchParams({page: String(page)});
      Object.entries(query).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const response = await apiRequest.get(`${path}?${params.toString()}`);
      return response.data as IPaginatedResponse<T>;
    },
    async fetchFromUrl({url}: {url: string}) {
      const response = await apiRequest.get(url);
      return response.data as IPaginatedResponse<T>;
    },
  };
}

type BudgetItemResponse = Omit<
  BudgetItemRecord,
  | "budget"
  | "budget_details"
  | "budget_type"
  | "budget_type_name"
  | "account"
  | "account_name"
  | "allowed_movement_types"
> & {
  budget: {
    base_uuid: string;
    reference_code?: string | null;
    fiscal_year: {start_date: string; end_date: string};
  };
  budget_type: {
    base_uuid: string;
    name: string;
    allowed_movement_types: "inflow" | "outflow" | "both";
  };
  account: {base_uuid: string; account_name: string};
};

function normalizeBudgetItem(item: BudgetItemResponse): BudgetItemRecord {
  return {
    ...item,
    budget: item.budget.base_uuid,
    budget_details: {
      base_uuid: item.budget.base_uuid,
      reference_code: item.budget.reference_code ?? null,
      start_date: item.budget.fiscal_year.start_date,
      end_date: item.budget.fiscal_year.end_date,
    },
    budget_type: item.budget_type.base_uuid,
    budget_type_name: item.budget_type.name,
    allowed_movement_types: item.budget_type.allowed_movement_types,
    account: item.account.base_uuid,
    account_name: item.account.account_name,
    total_amount: String(item.total_amount),
  };
}

const budgetItemList = listEndpoint<BudgetItemResponse>("budget/items/");

export const BUDGET_ITEMS_API = {
  async fetchFirstPage(options: Parameters<typeof budgetItemList.fetchFirstPage>[0]) {
    const page = await budgetItemList.fetchFirstPage(options);
    return {...page, results: page.results.map(normalizeBudgetItem)};
  },
  async fetchFromUrl(options: {url: string}) {
    const page = await budgetItemList.fetchFromUrl(options);
    return {...page, results: page.results.map(normalizeBudgetItem)};
  },
  async fetchById(baseUuid: string) {
    const response = await apiRequest.get(`budget/items/${baseUuid}/`);
    return normalizeBudgetItem(response.data as BudgetItemResponse);
  },
  async create(data: BudgetItemInput) {
    const response = await apiRequest.post("budget/items/", data);
    return normalizeBudgetItem(response.data as BudgetItemResponse);
  },
  async update(baseUuid: string, data: Partial<BudgetItemInput>) {
    const response = await apiRequest.patch(`budget/items/${baseUuid}/`, data);
    return normalizeBudgetItem(response.data as BudgetItemResponse);
  },
  async delete(baseUuid: string) {
    await apiRequest.delete(`budget/items/${baseUuid}/`);
  },
};

export const BUDGET_ADJUSTMENTS_API = listEndpoint<BudgetAdjustmentRecord>("budget/adjustments/");
