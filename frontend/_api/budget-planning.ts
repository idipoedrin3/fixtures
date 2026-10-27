import apiRequest from "./api-request";

export type BudgetBaselineActuals = {
  base_line_inflow: string;
  base_line_outflow: string;
  difference: string;
};

export async function fetchBudgetBaselineActuals(fiscalYearUuid: string) {
  const response = await apiRequest.get(
    `budget/baseline-actuals/${encodeURIComponent(fiscalYearUuid)}/`,
  );
  return response.data as BudgetBaselineActuals;
}
