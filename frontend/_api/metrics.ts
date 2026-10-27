import apiRequest from "./api-request";
import {getAllSelectedBranchUUIDs} from "./helpers";

type Filters = {
  date_filter:
    | "today"
    | "yesterday"
    | "this_week"
    | "this_month"
    | "this_year"
    | "last_year"
    | "current_fiscal_year"
    | "current_period";
  fiscal_year_base_uuid: string;
  branch_uuids: string;
  [k: string]: string;
};

type Section =
  | "all"
  | "financial_overview"
  | "totals"
  | "accounts"
  | "top_customers"
  | "revenue_expense_trend"
  | "net_profit_trend"
  | "invoices"
  | "top_items"
  | "expenses_by_period"
  | "inventory_items_or_fixed_assets_or_cash_accounts"
  | "paid_vs_unpaid_invoices"
  | "top_customers"
  | "top_vendors"
  | "revenue_profit_trend_inventory_items";

export const ANALYTICS = {
  async getMetrics<T>(section: Section = "all", filters?: Partial<Filters>) {
    const params = new URLSearchParams();

    params.append("dashboard_section", section);
    params.append("branch_uuids", getAllSelectedBranchUUIDs().join(",") || "");
    if (filters) {
      Object.keys(filters).forEach((key) => {
        if (filters[key]) {
          params.append(key, filters[key] || "");
        }
      });
    }

    const response = await apiRequest.get(`/analytics/dashboard-analytics/?${params.toString()}`);

    const data = response.data?.[section] ?? response.data;

    return data as T;
  },
};
