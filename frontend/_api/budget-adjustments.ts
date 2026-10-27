import apiRequest from "./api-request";
import {BUDGETS_API} from "./helpers";
import {ACCOUNTS_API} from "./api.helpers";
import {BUDGET_ITEMS_API, type BudgetAdjustmentType, type BudgetItemRecord} from "./budget-records";
import type {IBudget} from "#/_types/email";
import type {IPaginatedResponse} from "#/_types/api.types";

export type AdjustmentAllocationInput = {
  budget_allocation: string | null;
  adjustment_amount: string;
  start_date: string;
  end_date: string;
  description: string;
};
export type AdjustmentItemInput = {
  adjustment_type: BudgetAdjustmentType;
  budget_item: string | null;
  name: string;
  description: string;
  reference_code: string;
  account: string;
  budget_type: string;
  movement_type: "inflow" | "outflow" | null;
  allocations: AdjustmentAllocationInput[];
};
export type AdjustmentInput = {
  budget: string;
  title: string;
  description: string;
  items: AdjustmentItemInput[];
};
export type AdjustmentEditorItem = AdjustmentItemInput & {
  account_name: string;
  budget_type_name: string;
  source: BudgetItemRecord | null;
};
export type AdjustmentEditorData = {
  base_uuid: string;
  budget: IBudget;
  title: string;
  description: string;
  items: AdjustmentEditorItem[];
};

async function allPages<T>(initialUrl: string): Promise<T[]> {
  const results: T[] = [];
  let url: string | null = initialUrl;
  while (url) {
    const response = await apiRequest.get(url);
    const page = response.data as IPaginatedResponse<T>;
    results.push(...page.results);
    url = page.next;
  }
  return results;
}

export const ADJUSTMENT_EDITOR_API = {
  async load(id: string): Promise<AdjustmentEditorData> {
    const response = await apiRequest.get(`budget/adjustments/${id}/`);
    const record = response.data as {
      base_uuid: string;
      budget: string;
      title: string;
      description: string | null;
      status: string;
      approval_status: string;
    };
    if (record.status !== "draft" || record.approval_status !== "under_creation") {
      throw new Error("Only draft adjustments can be edited.");
    }
    const [budget, rows] = await Promise.all([
      BUDGETS_API.fetchBudgetById({baseUuid: record.budget}),
      allPages<
        Omit<AdjustmentItemInput, "allocations"> & {
          base_uuid: string;
          allocations: (AdjustmentAllocationInput & {approval_status: string})[];
        }
      >(`budget/adjustment-items/?adjustment_base_uuid=${id}`),
    ]);
    const items = await Promise.all(
      rows.map(async (row): Promise<AdjustmentEditorItem> => {
        const allocations = row.allocations;
        if (!Array.isArray(allocations)) {
          throw new Error("The adjustment item's allocations could not be loaded.");
        }
        const [account, budgetType, source] = await Promise.all([
          ACCOUNTS_API.fetchAccountById({accountId: row.account}),
          BUDGETS_API.fetchBudgetTypeById({baseUuid: row.budget_type}),
          row.budget_item ? BUDGET_ITEMS_API.fetchById(row.budget_item) : Promise.resolve(null),
        ]);
        if (source && !Array.isArray(source.allocations)) {
          throw new Error("The budget item's allocations could not be loaded.");
        }
        if (allocations.some((allocation) => allocation.approval_status !== "under_creation")) {
          throw new Error("Only adjustments with draft allocations can be edited.");
        }
        return {
          ...row,
          source,
          account_name: account.account_name,
          budget_type_name: budgetType.name,
          description: row.description ?? "",
          reference_code: row.reference_code ?? "",
          allocations: allocations.map((allocation) => ({
            budget_allocation: allocation.budget_allocation,
            adjustment_amount: allocation.adjustment_amount,
            start_date: allocation.start_date,
            end_date: allocation.end_date,
            description: allocation.description ?? "",
          })),
        };
      }),
    );
    return {
      base_uuid: record.base_uuid,
      budget,
      items,
      title: record.title,
      description: record.description ?? "",
    };
  },
  async create(data: AdjustmentInput) {
    await apiRequest.post("budget/adjustments/", data);
  },
  async update(id: string, data: AdjustmentInput) {
    await apiRequest.patch(`budget/adjustments/${id}/`, data);
  },
};
