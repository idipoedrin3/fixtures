import {IJournalEntriesData} from "../_components/common/tables/journal-entries-table";
import {FileEntry, toFileEntry, withNamedFile} from "../_lib/file-utils";
import {
  IInventoryItem,
  IInventoryItemUnitOfMeasure,
  IInstitutionSupportedBank,
  IUser,
  IUserInstitution,
  Permission,
} from "./api.types";

export interface ForgotPasswordRequest {
  email: string;
  frontend_url?: string;
}

export type ILoginResponse = {
  tokens: {
    access: string;
    refresh: string;
  };
  user: IUser;
  institutions_attached: IUserInstitution[];
};

export interface ICountry {
  name: string;
  official_name: string;
  iso2: string;
  iso3: string;
  numeric_code: string;
  phone_code: string;
  capital: string;
  currency: {
    code: string;
    name: string;
    symbol: string;
  };
  region: string;
  subregion: string;
  nationality: string;
  timezone: string;
  flag: string;
  flag_svg: string;
  languages: string[];
  latitude: number;
  longitude: number;
}

interface IReversalTransaction {
  id: number;
  base_uuid: string;
  reference_code: string;
}

interface IReversedBy {
  id: number;
  username: string;
  email: string;
  fullname: string;
  reference_code: string;
}

export interface IReversalEntry {
  original_transaction: IReversalTransaction;
  reversal_transaction: IReversalTransaction;
  reversed_by: IReversedBy;
  reason?: string;
  reversed_at: string;
}

export interface IDepreciationSummaryPayload {
  depreciation_start_date?: string;
  asset_category_base_uuid: string;
  purchase_date: string;
  purchase_price: string;
}

export interface IDepreciationSummaryResponse {
  net_book_value: string;
}

export interface IDepreciationEntry {
  depreciation_date: string;
  depreciation_amount: string;
  accumulated_depreciation: string;
  net_book_value: string;
}

export interface IDepreciationSchedulePayload {
  depreciation_start_date?: string;
  useful_life?: string;
  salvage_value?: string;
  asset_category_base_uuid: string;
  purchase_date: string;
  purchase_price: string;
}

type UserSummary = {
  id: number;
  fullname: string;
  base_uuid: string;
  reference_code: string;
  email: string;
};
export type ReconciliationStatus =
  | "DRAFT"
  | "MAPPING_DONE"
  | "MATCHING_IN_PROCESS"
  | "LOCKED"
  | "COMPLETED"
  | "CANCELLED";

export interface IReconciliationSession {
  id: number;
  base_uuid: string;
  reference_code: string;
  external_base_uuid?: string | null;
  approval_status: string;
  status: ReconciliationStatus;
  selected_period_in_days: number;
  description?: string | null;
  institution: number;
  cash_account_object_id: number;
  statement_closing_balance: string;
  balance_changes: {
    ledger_opening_balance: string;
    ledger_closing_balance: string;
    balance_difference: string;
  };
  cash_account_content_type: number;
  coa_reference: {
    id: number;
    account_name: string;
    reference_code?: string | null;
    base_uuid: string;
    account_role: {
      base_uuid: string;
      role_name: string;
      role_code: string;
    };
  };
  start_date: string;
  end_date: string;
  statement_file: string | null;
  is_statement_file_available: boolean;
  statement_file_columns: string[] | null;
  expected_statement_file_columns?: any | null;
  is_file_mapping_completed: boolean;
  statement_mapping_details: string | null;
  approvals?: any[];
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
  created_at: string;
  updated_at: string;
  original_data?: string | null;
}

export interface ICashAccount {
  base_uuid: string;
  content_type: number;
  account_name: string;
  reference_code: string;
  last_reconciled_balance: string | null;
  last_reconciled_at: string | null;
  current_balance: string;
  coa_account_name: string;
  coa_reference_code: string;
}

export interface IReconciliationCreateFormData {
  reference_code?: string;
  coa_reference?: string;
  cash_account?: {
    content_type: number;
    content_object_uuid: string;
  };
  start_date: string;
  end_date: string;
  statement_opening_balance?: string;
  statement_closing_balance?: string;
  description?: string;
}

export type MatchBadge = "auto" | "manual" | "unmatched";

export interface IStatementLine {
  id: number;
  base_uuid: string;
  transaction_date: string;
  deposit: string | null;
  withdrawal: string | null;
  balance: string;
  description: string | null;
  is_matched: boolean;
  reference_code: string | null;
  raw_row_data: Record<string, any>;
  reconciliation_session: number;
  resolution_type?:
    | "MATCHED"
    | "OUTSTANDING"
    | "ADJUSTED"
    | "BANK_ERROR"
    | "IGNORED"
    | "UNRECONCILED"
    | null;
}

export interface IColumnMappingField {
  system_field: string;
  system_label: string;
  uploaded_column: string;
}

export interface IDetectedColumns {
  is_mapped: boolean;
  detected_columns: string[];
  expected_fields: {key: string; label: string; is_required: boolean}[];
}

export const buildReconciliationPayload = async (
  input: IReconciliationCreateFormData & {statement_file?: File | null},
) => {
  const {statement_file, cash_account, coa_reference, reference_code, description, ...rest} = input;
  return withNamedFile("statement_file", statement_file ?? null, {
    ...rest,
    ...(cash_account && {cash_account}),
    ...(coa_reference && {coa_reference}),
    ...(reference_code && {reference_code}),
    ...(description && {description}),
  });
};

export interface PermissionState {
  items: Permission[];
  count: number;
  nextUrl: string | null;
  loading: boolean;
  loadingMore: boolean;
}

export interface IReconciliationMatch {
  base_uuid: string;
  statement_line: number;
  coa_account_entry: number;
  statement_lines?: number[];
  ledger_entries?: number[];
  description?: string;
  reference_code?: string;
  match_type: "auto" | "manual";
  confidence_score?: string | null;
  created_at: string;
}

export interface IReconciliationLiveStats {
  statement_stats: {
    total_inflow: number;
    total_outflow: number;
    difference: number;
    reconciled_inflow: number;
    reconciled_outflow: number;
    unreconciled_inflow: number;
    unreconciled_outflow: number;
  };
  ledger_stats: {
    total_inflow: number;
    total_outflow: number;
    difference: number;
    reconciled_inflow: number;
    reconciled_outflow: number;
    unreconciled_inflow: number;
    unreconciled_outflow: number;
  };
}

export interface IReconciliationStrategy {
  strategy_code: string;
  base_uuid: string;
  description: string;
}

export interface IBillOfMaterialUser {
  id: number;
  fullname: string;
  base_uuid: string;
  reference_code: string;
  email: string;
}

export interface IBillOfMaterialInventoryItem {
  id: number;
  item_name: string;
  reference_code: string;
  base_uuid: string;
}

export interface IBillOfMaterialUnitOfMeasure {
  id: number;
  unit_name: string;
  unit_abbreviation?: string;
  base_uuid: string;
  reference_code: string | null;
}

export interface IBillOfMaterialLineItemResponse {
  id: number;
  base_uuid: string;
  component: IBillOfMaterialInventoryItem;
  component_unit_of_measure: IBillOfMaterialUnitOfMeasure;
  description?: string;
  external_base_uuid?: string | null;
  reference_code?: string | null;
  quantity: number;
  is_deleted?: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  bill_of_material?: number;
}

export interface IBillOfMaterialLineItem {
  component: string;
  component_unit_of_measure: string;
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  quantity: number;
  is_required?: boolean;
}

export interface IOverHeadCosts {
  overhead_account?: string | null;
  source_account?: string | null;
  reference_code?: string;
  description: string;
  cost_amount: number;
}

export interface IBOMOverheadCost {
  id: number;
  base_uuid: string;
  external_base_uuid?: string;
  reference_code?: string;
  description: string;
  cost_amount: string;
  overhead_account?:
    | {
        id: number;
        base_uuid: string;
        account_name: string;
        reference_code: string;
      }
    | string
    | null;
  source_account?:
    | {
        id: number;
        base_uuid: string;
        account_name: string;
        reference_code: string;
      }
    | string
    | null;
  is_deleted?: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  bill_of_material?: number;
}

export interface IBillOfMaterial {
  id: number;
  base_uuid: string;
  is_default_for_item: boolean;
  external_base_uuid?: string | null;
  reference_code?: string | null;
  approvals?: any[];
  inventory_item: IBillOfMaterialInventoryItem;
  unit_of_measure: IBillOfMaterialUnitOfMeasure;
  quantity: number;
  description?: string | null;
  approval_status: "under_creation" | "pending" | "approved" | "rejected";
  is_deleted?: boolean;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
  deleted_at?: string | null;
  original_data?: string | null;
  line_items?: IBillOfMaterialLineItemResponse[];
  line_items_count?: number;
  created_by?: IBillOfMaterialUser | null;
  updated_by?: IBillOfMaterialUser | null;
  estimated_unit_cost: number | null;
}

export interface IBillOfMaterialFormData {
  inventory_item: string;
  unit_of_measure: string;
  quantity: number;
  line_items: IBillOfMaterialLineItem[];
  other_overhead_costs: IOverHeadCosts[];
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  is_default_for_item?: boolean;
}

export interface IBOMLineItem {
  id: number;
  base_uuid: string;
  reference_code: string;
  is_required: boolean;
  component: {
    id: number;
    base_uuid: string;
    item_name: string;
    reference_code: string;
  };
  component_unit_of_measure: {
    id: number;
    base_uuid: string;
    unit_name: string;
    reference_code: string | null;
  };
  quantity: number;
  quantity_in_stock: number;
  description: string | null;
  unit_cost: number | string;
}

export interface IPotentialConsumption {
  type: "material" | "overhead";
  item_base_uuid: string;
  component: {
    base_uuid: string;
    reference_code: string;
    item_name: string;
  } | null;
  unit_of_measure?: {
    base_uuid: string;
    reference_code: string | null;
    unit_name: string;
    unit_abbreviation: string;
  } | null;
  bom_quantity: string | null;
  quantity_in_stock: string | null;
  expected_quantity_to_consume: string | null;
  is_required: boolean | null;
  description?: string | null;
  reference_code?: string | null;
  expected_cost_amount?: string | null;
  overhead_account?: {
    base_uuid: string;
    account_name: string;
    reference_code?: string | null;
  } | null;
  source_account?: {
    base_uuid: string;
    account_name: string;
    reference_code?: string | null;
  } | null;
}

export interface IExecutionRemainingConsumption extends IPotentialConsumption {
  consumed_quantity: string;
  remaining_quantity: string;
}

export interface IOrderFormData {
  branch?: string;
  inventory_item?: string;
  unit_of_measure?: string;
  bill_of_material?: string;
  quantity_to_produce: number;
  priority?: "low" | "normal" | "high" | "urgent";
  //status: "draft" | "confirmed" | "in_progress" | "completed" | "cancelled";
  issue_date: string;
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  client?: string;
  executor?: string;
  expected_completion_date?: string;
}

export interface IOrder {
  id: number;
  base_uuid: string;
  has_executions: boolean;
  external_base_uuid?: string | null;
  reference_code?: string | null;
  branch: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string;
  } | null;
  bill_of_material: {
    id: number;
    base_uuid: string;
    reference_code: string;
    inventory_item?: {
      id: string;
      base_uuid: string;
      item_name: string;
      reference_code?: string;
    };

    unit_of_measure?: {
      id: string;
      base_uuid: string;
      unit_name: string;
      reference_code?: string;
      unit_abbreviation?: string;
    };
  } | null;
  inventory_item: {
    id: string;
    base_uuid: string;
    item_name: string;
    reference_code?: string;
  } | null;
  unit_of_measure: {
    id: string;
    base_uuid: string;
    unit_name: string;
    unit_abbreviation?: string;
    reference_code?: string;
  } | null;
  client: {
    id: number;
    base_uuid: string;
    customer_name: string;
    customer_type?: string;
    email?: string | null;
    address?: string | null;
    phone_number?: string | null;
    profile_photo?: string | null;
    tin?: string | null;
  } | null;
  quantity_to_produce: number;
  status: "draft" | "confirmed" | "in_progress" | "completed" | "cancelled";
  issue_date: string;
  expected_completion_date?: string | null;
  actual_completion_date?: string | null;
  executor?: any;
  estimated_unit_cost?: number | string | null;
  production_cost?: number | string | null;
  completion_duration_seconds?: number | null;
  completion_duration_display?: string | null;
  due_duration_seconds?: number | null;
  due_duration_display?: string | null;
  is_overdue?: boolean;
  description?: string | null;
  approval_status: "under_creation" | "pending" | "approved" | "rejected" | "active";
  is_deleted?: boolean;
  is_active?: boolean;
  created_at: string;
  updated_at?: string | null;
  deleted_at?: string | null;
  original_data?: string | null;
  approvals?: any;
  created_by?: IUser | null;
  updated_by?: IUser | null;
  priority: "low" | "normal" | "high" | "urgent";
}

export interface IExecutionConsumption {
  component: string;
  unit_of_measure: string;
  manufacturing_order: string;
  quantity_used: string;
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  date_of_consumption?: string;
}

export interface IExecutionOutputForm {
  quantity_produced: string;
  description?: string;
  execution_date?: string;
  reference_code?: string;
  component?: string;
  unit_of_measure?: string;
  itemize?: boolean;
}

export interface IExecutionOutput {
  quantity_produced: string;
  description?: string;
  execution_date?: string;
  general_journal_items: IJournalEntriesData;
  are_financial_events_processed: boolean;
}

export interface IExecutionFormData {
  manufacturing_order?: string;
  bill_of_material?: string;
  branch: string;
  started_at: string;
  completed_at?: string;
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  work_in_progress_account?: string | null;
}

export interface IExecution {
  id: number;
  base_uuid: string;
  external_base_uuid?: string | null;
  reference_code?: string | null;
  manufacturing_order_reference_code?: string | null;
  bill_of_material_reference_code?: string | null;
  manufacturing_order: {
    id: number;
    base_uuid: string;
    reference_code: string;
    bill_of_material?: {
      id: number;
      base_uuid: string;
      reference_code: string;
      inventory_item?: {
        id: number;
        base_uuid: string;
        item_name: string;
        reference_code?: string;
      };
      unit_of_measure?: {
        id: number;
        base_uuid: string;
        unit_name: string;
        unit_abbreviation?: string;
        reference_code?: string | null;
      };
    } | null;
  } | null;
  branch: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string;
    branch_location?: string;
  } | null;
  inventory_item:
    | {
        id: number;
        base_uuid: string;
        item_name: string;
        reference_code: string;
      }
    | string
    | null;
  unit_of_measure:
    | {
        id: number;
        base_uuid: string;
        unit_name: string;
        reference_code: string | null;
      }
    | string
    | null;
  bill_of_material:
    | {
        id: number;
        base_uuid: string;
        reference_code: string;
        inventory_item?: {
          id: number;
          base_uuid: string;
          item_name: string;
          reference_code?: string;
        };
        unit_of_measure?: {
          id: number;
          base_uuid: string;
          unit_name: string;
          unit_abbreviation?: string;
          reference_code?: string | null;
        };
      }
    | string
    | null;
  expected_quantity_to_produce: string | number | null;
  status: "in_progress" | "completed" | "cancelled" | "draft";
  approval_status: "under_creation" | "pending" | "approved" | "rejected" | "active";
  started_at: string;
  completed_at?: string | null;
  description?: string | null;
  is_deleted?: boolean;
  is_active?: boolean;
  created_at: string;
  updated_at?: string | null;
  deleted_at?: string | null;
  original_data?: string | null;
  approvals?: any;
  created_by?: any | null;
  updated_by?: any | null;
  consumptions?: any[];
  outputs?: any[];
  work_in_progress_account?: {
    id: number;
    base_uuid: string;
    account_name: string;
    reference_code?: string | null;
  } | null;
  analytics?: {
    production: {
      expected_quantity: number;
      actual_quantity: number;
      remaining_quantity: number;
      variance: number;
      variance_percentage: number | null;
      completion_rate: number | null;
    };
    materials: {
      total_consumed: number;
      expected_consumption: number;
      variance: number;
    };
    efficiency: {
      production_efficiency: number | null;
      output_efficiency: number | null;
      material_efficiency: number | null;
      yield_proxy: number | null;
    };
    order_alignment: {
      order_quantity: number | null;
      order_variance: number | null;
      order_completion: number | null;
    };
    timeline: {
      started_at: string;
      completed_at: string | null;
      duration_hours: number | null;
    };
    health: {
      score: number;
      is_on_track: boolean;
      is_over_producing: boolean;
      is_under_producing: boolean;
      status: string;
    };
  } | null;
}

export interface IJwtPayload {
  token_type: "access" | "refresh";
  exp: number;
  iat: number;
  jti: string;
  user_id: number;
  email: string;
  fullname: string;
}

export interface IExecutionOutput {
  id: number;
  base_uuid: string;
  external_base_uuid?: string;
  reference_code?: string;
  description?: string;
  date_of_production?: string;
  quantity_produced: string;
  is_deleted?: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  execution?: number;
}

export interface IExecutionConsumptionRecord {
  id: number;
  base_uuid: string;
  external_base_uuid?: string;
  reference_code?: string;
  description?: string;
  quantity_used: string;
  is_deleted?: boolean;
  is_active?: boolean;
  date_of_consumption?: string;
  created_at?: string;
  updated_at?: string;
  execution?: number;
  component?: {
    id: number;
    base_uuid: string;
    item_name: string;
    reference_code?: string;
  };
  unit_of_measure?: {
    id: number;
    base_uuid: string;
    unit_name: string;
    unit_abbreviation?: string;
  };
  general_journal_items?: IJournalEntriesData;
  are_financial_events_processed: boolean;
}

export interface IExecutionFinancialEntry {
  transaction_entry_type: "debit" | "credit";
  amount: string;
  description: string;
  account: {
    id: number;
    base_uuid: string;
    name: string;
    reference_code: string;
  };
}

export interface IExecutionFinancialTransaction {
  source: {
    type: "Component Consumption" | "Final Output";
    reference_code: string;
    base_uuid: string;
  };
  transaction: {
    base_uuid: string;
    reference_code: string;
    date: string;
  };
  entries: IExecutionFinancialEntry[];
}

export interface IExecutionFinancials {
  execution: {
    id: number;
    base_uuid: string;
    reference_code: string;
    status: string;
  };
  transactions: IExecutionFinancialTransaction[];
  total_credits: number;
  total_debits: number;
  is_balanced: boolean;
}

export interface IBeneficiaryPaymentMethod {
  base_uuid: string;
  currency: {
    id: number;
    code: string;
    name: string;
    symbol: string;
  } | null;
  method_type: "bank" | "mobile_money" | "digital_wallet";
  operator_country_code: string | null;
  operator_code: string | null;
  operator_name: string | null;
  identifier: string;
}

export interface IBeneficiaryPaymentMethodFormData {
  base_uuid?: string;
  currency?: number | null;
  method_type: "bank" | "mobile_money" | "digital_wallet";
  operator_country_code?: string | null;
  operator_code?: string | null;
  identifier: string;
}

export interface IRequisitionBeneficiary {
  id: number;
  base_uuid: string;
  reference_code: string;
  external_base_uuid: string;
  name: string;
  contact_phone_number: string | null;
  payment_methods:
    | IBeneficiaryPaymentMethod
    | {
        payment_method: IBeneficiaryPaymentMethod;
        remaining_count: number;
      }
    | null;
  is_vendor: boolean;
  vendor_base_uuid: string | null;
  is_staff: boolean;
  profile_institution_base_uuid: string | null;
  email: string | null;
  description: string;
  approval_status: "under_creation" | "approved" | "rejected" | "pending";
  approvals: string;
  institution: number;
  is_active: boolean;
  is_deleted: boolean;
  deleted_at: string | null;
  original_data: string;
  created_at: string;
  updated_at: string;
  created_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  } | null;
  updated_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  } | null;
}

export interface IRequisitionBeneficiaryFormData {
  name: string;
  contact_phone_number?: string | null;
  email?: string | null;
  payment_methods?: IBeneficiaryPaymentMethodFormData[];
  description?: string;
  created_by_id?: number;
  updated_by_id?: number;
}

export interface IExecutionConsumptionGroup {
  id: number;
  base_uuid: string;
  reference_code: string;
  execution: {
    id: number;
    base_uuid: string;
  };
  component: {
    id: number;
    item_name: string;
    reference_code: string;
    base_uuid: string;
  };
  unit_of_measure: {
    id: number;
    unit_name: string;
    unit_abbreviation?: string;
    reference_code: string | null;
    base_uuid: string;
  };
  total_quantity_used: string;
  expected_quantity_to_consume: string;
  yet_to_be_consumed: string;
  allocated_quantity: string;
  available_quantity_to_allocate: string;
  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  created_by: number | null;
  updated_by: number | null;
  external_base_uuid: string | null;
  description: string | null;
}

export interface IExecutionOutputAllocationSuggestion {
  consumption_group: IExecutionConsumptionGroup;
  inferred_quantity: string;
}

export type IInventoryItemImageInput = {
  image_name: string;
  image: File;
  is_default: boolean;
};

export type IInventoryItemImageFormData = {
  image_name: string;
  image: FileEntry;
  is_default: boolean;
};

export interface IInventoryItemImage {
  id: number;
  base_uuid: string;
  image_name: string;
  image: string;
  inventory_item: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export const buildInventoryItemImagesPayload = async (
  images: IInventoryItemImageInput[],
): Promise<IInventoryItemImageFormData[]> =>
  Promise.all(
    images.map(async ({image_name, image, is_default}) => ({
      image_name,
      image: await toFileEntry(image),
      is_default,
    })),
  );
