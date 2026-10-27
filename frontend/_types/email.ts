import type {Approval, ApprovableEntityStatus} from "./approvals.types";

export interface EmailDraft {
  to: string[];
  cc: string[];
  bcc: string[];
  subject: string;
  body: string;
  from: string;
}

export interface Email {
  id: number;
  from: {
    name: string;
    email: string;
  };
  subject: string;
  body: string;
  received_at: string;
}

export interface IInstitutionSupportedCurrency {
  id: number;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  one_side: {value: number; currency: ICurrencyDetail};
  other_side: {value: number; currency: ICurrencyDetail};
  rate: string;
  format: "base_to_other" | "other_to_base";
  description: string | null;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  created_by: number | null;
  updated_by: number | null;
  institution: number;
  currency: ICurrencyDetail;
}

interface ICurrencyDetail {
  id: number;
  code: string;
  name: string;
  symbol: string;
  decimail_places: number;
}

export interface IRequisitionArrear {
  base_uuid: string;
  date_range: string;
  reference_code: string;
  requisition_type: {
    name: string;
  };
  branch?: {
    branch_name: string;
  };
  requested_by?: {
    fullname: string;
  };
  gross_amount: number;
  status: string;
  is_paid: boolean;
  created_at: string;
  days_overdue: number;
  pending_count: number;
  approval_progress: number;
}

export interface IPreferredVendorUnitPrice {
  unit_of_measure: string;
  price: string;
  minimum_order_qty: number;
}

export interface IPreferredVendor {
  id: number;
  unit_prices: string;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  description: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string;
  created_by: number;
  updated_by: number;
  item: number;
  vendor: number;
}

export interface IPreferredVendorFormData {
  vendor: string;
  unit_prices: IPreferredVendorUnitPrice[];
}

export interface IBudget {
  planning_method?: "zero_based" | "historical";
  base_line_fiscal_year?: string | null;
  base_line_inflow?: string | null;
  base_line_outflow?: string | null;
  forecast_inflow?: string | null;
  forecast_outflow?: string | null;
  id: number;
  model_content_type_id: number;
  is_approvable: boolean;
  created_by: {
    fullname: string;
    base_uuid: string;
    profile_photo_base64: string | null;
  } | null;
  approvals: unknown[];
  updated_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  } | null;
  allow_changes: boolean;
  fiscal_year: {
    base_uuid: string;
    name: string;
    reference_code: string;
    start_date: string;
    end_date: string;
  };
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  description: string | null;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  original_data: string | null;
  approval_status: "active" | "under_creation" | string;
  status: "open" | "draft" | "closed";
}

export type BudgetForecastInput =
  | {amount: string; percentage?: never}
  | {percentage: string; amount?: never};

export interface IBudgetFormData {
  planning_method: "zero_based" | "historical";
  base_line_fiscal_year: string | null;
  inflow: BudgetForecastInput;
  outflow: BudgetForecastInput;
  fiscal_year: string;
  items: Array<{
    additionalProp1: string;
    additionalProp2: string;
    additionalProp3: string;
  }>;
  description: string;
  external_base_uuid?: string;
  reference_code: string;
}

export interface IBudgetProposal {
  total_amount?: string;
  id: number;
  model_content_type_id: string;
  is_approvable: string;
  created_by: {
    fullname: string;
    base_uuid: string;
    profile_photo_base64: string | null;
  } | null;
  budget_type: {
    base_uuid: string;
    name: string;
    allowed_movement_types: "inflow" | "outflow" | "both";
  };
  budget: {
    base_uuid: string;
    reference_code: string;
    fiscal_year: {
      base_uuid: string;
      start_date: string;
      end_date: string;
    };
  };
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  description: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string;
  status: "draft" | string;
  updated_by: number;
}

export interface IBudgetProposalExpanded extends IBudgetProposal {
  items: Array<
    Omit<IBudgetProposalItemFormData, "proposal" | "account" | "allocations"> & {
      base_uuid: string;
      status: string;
      account: {
        base_uuid: string;
        account_name: string;
        reference_code: string;
      };
      allocations: Array<
        IBudgetProposalItemFormData["allocations"][number] & {
          base_uuid: string;
          approval_status: string;
        }
      >;
    }
  >;
}

export interface IBudgetProposalFormData {
  budget_type: string;
  budget: string;
  items: Array<Omit<IBudgetProposalItemFormData, "proposal">>;
  description: string;
  external_base_uuid: string;
  reference_code: string;
}

export interface IBudgetProposalItem {
  total_amount: string;
  id: number;
  model_content_type_id: string;
  is_approvable: string;
  created_by: IBudgetProposal["created_by"];
  account: string;
  account_name: string;
  account_reference_code: string;
  movement_type: "inflow" | "outflow" | null;
  proposal: string;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  description: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string;
  name: string;
  status: "draft" | string;
  updated_by: number;
}

export interface IBudgetProposalItemFormData {
  base_uuid?: string;
  account: string;
  proposal: string;
  movement_type?: "inflow" | "outflow" | "" | null;
  allocations: Array<{
    base_uuid?: string;
    description: string;
    external_base_uuid: string;
    reference_code: string;
    amount: string;
    start_date: string;
    end_date: string;
  }>;
  description: string;
  external_base_uuid: string;
  reference_code: string;
  name: string;
}

export interface IBudgetProposalItemAllocation {
  id: number;
  model_content_type_id: number;
  is_approvable: string;
  created_by: string;
  can_edit: boolean;
  status: "under_review" | "rejected" | "approved";
  updated_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  };
  allow_changes: string;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  description: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string;
  original_data: string;
  approval_status: ApprovableEntityStatus;
  amount: string;
  start_date: string;
  end_date: string;
  item: number;
}

export interface IBudgetProposalItemAllocationFormData {
  description: string;
  external_base_uuid: string;
  reference_code: string;
  amount: string;
  start_date: string;
  end_date: string;
}

export interface IBudgetTypeFormData {
  allowed_movement_types?: "inflow" | "outflow" | "both";
  approval_levels: Array<{
    base_uuid?: string;
    category: string;
    name: string;
    description: string;
    approvers: string[];
    approver_users: string[];
    overriders: string[];
    overrider_users: string[];
  }>;
  allow_decline_to_continue: boolean;
  affect_inflight_approvals: boolean;
  is_open_to_all_users: boolean;
  allowed_users?: string[];
  description: string;
  external_base_uuid?: string;
  reference_code: string;
  name: string;
}

export interface IBudgetType {
  allowed_movement_types: "inflow" | "outflow" | "both";
  id: number;
  model_content_type_id: number;
  is_approvable: boolean;
  created_by: {
    fullname: string;
    base_uuid: string;
    profile_photo_base64: string | null;
  } | null;
  approvals: unknown[];
  updated_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  } | null;
  allow_changes: boolean;
  approval_levels_detail: {
    BudgetItemAllocation: IBudgetTypeApprovalLevelDetail[];
    BudgetProposalItemAllocation: IBudgetTypeApprovalLevelDetail[];
    BudgetAdjustmentItemAllocation: IBudgetTypeApprovalLevelDetail[];
  };
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  description: string | null;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  original_data: string | null;
  approval_status: "active" | "under_creation" | string;
  name: string;
  is_open_to_all_users: boolean;
  institution: number;
  allow_decline_to_continue: {
    BudgetItemAllocation: boolean;
    BudgetProposalItemAllocation: boolean;
    BudgetAdjustmentItemAllocation: boolean;
  };
}

export interface IBudgetTypeApprovalLevelDetail {
  id: number;
  approval_document: number;
  category: {
    id: number;
    description: string;
    base_uuid: string;
    reference_code: string;
    name: string;
    level: number;
  };
  approvers_detail: unknown[];
  overriders_detail: unknown[];
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  level: number;
  description: string;
  name: string;
  is_locked: boolean;
  created_by: unknown | null;
  updated_by: unknown | null;
  approver_users: unknown[];
  overrider_users: unknown[];
}

export interface IBudgetIntelligence {
  period_elapsed_percentage: number;
  inflow_budget: number;
  inflow_actual: number;
  inflow_percentage: number;
  outflow_budget: number;
  outflow_actual: number;
  outflow_percentage: number;
  net_budget: number;
  net_actual: number;
  budget_utilization_percentage: number;
}
