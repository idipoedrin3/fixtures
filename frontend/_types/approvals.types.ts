import {
  IJournalEntriesData,
  IJournalEntry,
} from "../_components/common/tables/journal-entries-table";
import {IFixedAssetItem, Role, UserProfile} from "./api.types";

export interface ApproverGroup {
  id: number;
  institution: number | null;
  institution_name?: string;
  name: string;
  description?: string;
  base_uuid: string;
  users: number[];
  roles: number[];
  users_display: UserProfile[];
  roles_display: Role[];
}

export interface ApproverGroupFormData {
  institution: number;
  name: string;
  description?: string;
  users: number[];
  roles: number[];
}

export interface ApprovalDocumentLevelApprover {
  id: number;
  approver_group: ApproverGroup;
}

export interface ApprovalDocumentLevelOverrider {
  id: number;
  approver_group: ApproverGroup;
}

export interface ProfileInstitutionUser {
  id: number;
  base_uuid: string;
  reference_code: string;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  last_activity: string | null;
  bio: string | null;
  signature_base64: string | null;
  created_by: number | null;
  updated_by: number | null;
  institution: number;
  profile: {
    id: number;
    user: IUser;
    institutions: number[];
  };
}

export interface ApprovalDocumentCategory {
  id: number;
  name: string;
  description: string;
  base_uuid: string;
  reference_code: string;
  level: number;
}

export interface ApprovalDocumentLevel {
  id: number;
  level: number;
  name: string | null;
  description: string;
  base_uuid: string;
  reference_code: string;
  is_locked: boolean;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  created_by: number | null;
  updated_by: number | null;
  approval_document: number;
  category: ApprovalDocumentCategory | null;
  approvers_detail: ApprovalDocumentLevelApprover[];
  overriders_detail: ApprovalDocumentLevelOverrider[];
  approver_users: ProfileInstitutionUser[];
  overrider_users: ProfileInstitutionUser[];
}

export interface ApprovalDocumentLevelFormData {
  name: string | null;
  description: string;
  approver_users: string[];
  approvers: string[];
  overriders: string[];
  overrider_users: string[];
  approval_document: number;
  category?: string;
  reference_code?: string;
  is_locked?: boolean;
}

export interface ApprovalDocument {
  id: number;
  base_uuid: string;
  institution: number;
  institution_name: string;
  description: string | null;
  document_name: string;
  content_type: {id: number; name: string} | number;
  actions: Array<{id: number; name: string}>;
  levels: ApprovalDocumentLevel[];
  scope_content_type: number | null;
  scope_object_id: number | null;
  is_active?: boolean;
  allow_decline_to_continue?: boolean;
}

export interface ApprovalDocumentFormData {
  institution: number;
  description: string | null;
  content_type: number;
  actions: number[];
  allow_decline_to_continue?: boolean;
}

export type ApprovalStatus = "ongoing" | "rejected" | "completed";

export type ApprovalTaskStatus =
  | "not_started"
  | "pending"
  | "rejected"
  | "approved"
  | "terminated"
  | "overridden";

export interface ApprovalReturnRoute {
  id: number;
  base_uuid: string;
  approval: number;
  source_task: number;
  source_level: number;
  target_task: number;
  target_level: number;
  parent_route: number | null;
  description: string | null;
  status: "awaiting_correction" | "returned" | "cancelled";
  sent_by: number | null;
  sent_by_fullname?: string | null;
  returned_at: string | null;
  cancelled_at: string | null;
  created_at: string;
}

export interface ApprovalTask {
  id: number;
  base_uuid: string;
  sequence?: number;
  status: ApprovalTaskStatus;
  comment: string | null;
  approved_by: number | null;
  approved_by_fullname?: string | null;
  updated_at: string;
  level: ApprovalDocumentLevel;
  level_name: string;
  approval_document_description: string | null;
  object_base_uuid: string;
  object_id: string;
  content_object?: {
    app_label?: string;
    model?: string;
    object_id?: number | string;
    url?: string | null;
    content_type?: {
      id?: number;
      app_label?: string;
      model?: string;
      name?: string;
    };
  };
  actions?: IApprovalTaskAction[];
  active_return_route?: ApprovalReturnRoute | null;
  can_recall?: boolean;
  timing?: {
    state: "completed" | "waiting";
    started_at: string;
    ended_at: string | null;
    elapsed_seconds: number;
    started_by:
      | "workflow_initiated"
      | "approved"
      | "rejected"
      | "sent_back"
      | "reset"
      | "overridden"
      | "recalled";
  } | null;
}

export interface ISendBackApprovalTaskFormData {
  target_level?: number;
  comment?: string;
  return_to_sender?: boolean;
}

export interface IApprovalTaskAction {
  id: number;
  base_uuid: string;
  action: "approved" | "rejected" | "reset" | string;
  acted_by: number | null;
  acted_by_fullname?: string | null;
  comment?: string | null;
  created_at: string;
  from_level: number;
  to_level: number;
  from_status: string;
  to_status: string;
  return_route?: number | null;
}

export interface Action {
  id: number;
  name: string;
  code: string;
  description: string | null;
  base_uuid?: string;
}

export interface Approval {
  id: number;
  base_uuid: string;
  created_at: string;
  status: ApprovalStatus;
  completion_risk_score: number | null;
  completion_risk_rating: ApprovalRiskRating | null;
  risk_assessed_at: string | null;
  document: ApprovalDocument;
  action: Action;
  content_type: number;
  object_id: number;
  tasks: ApprovalTask[];
  return_routes?: ApprovalReturnRoute[];
  initiation?: {
    created_at: string;
    created_by_fullname: string;
  } | null;
}

export type ApprovalRiskRating = "low" | "medium" | "high" | "critical";

export interface ApprovalRiskFactor {
  code: string;
  source: "general" | "requisition" | string;
  severity: ApprovalRiskRating;
  points: number;
  message: string;
  level: string | null;
  category: string | null;
  comment: string | null;
  acted_by: string | null;
  occurred_at: string | null;
}

export interface ApprovalRiskAnalysis {
  score: number;
  rating: ApprovalRiskRating;
  has_dissent: boolean;
  counts: {
    rejections: number;
    continued_rejections: number;
    send_backs: number;
    overrides: number;
    reopens: number;
    recalls: number;
    decisions_without_reason: number;
    repeated_approver_levels: number;
    fast_decisions: number;
    slow_decisions: number;
    evidence_issues: number;
    amount_outliers: number;
  };
  factors: ApprovalRiskFactor[];
  generated_at: string;
  is_snapshot: boolean;
  assessed_at: string | null;
}

export type ApprovableEntityStatus =
  | "under_creation"
  | "under_update"
  | "under_deletion"
  | "active"
  | "approved";

export interface IBaseApprovable {
  id: number;
  base_uuid: string;
  model_content_type_id?: number;
  is_approvable?: boolean;
  reference_code?: string;
  is_deleted?: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
  created_by?: {
    id: number;
    base_uuid: string;
    email: string;
    fullname: string;
    reference_code: string;
    profile_photo_base64?: string | null;
  };
  updated_by?: {
    id: number;
    base_uuid: string;
    email: string;
    fullname: string;
    reference_code: string;
  };
  original_data?: Record<string, unknown> | null;
  approval_status?: ApprovableEntityStatus;
  approvals?: Approval[];
  allow_changes?: boolean;
}

export interface ContentTypeLite {
  id: number;
  app_label: string;
  model: string;
  name: string;
  plural_name: string;
}

// Helper to build approvable read types without mutating existing interfaces
export type Approvable<T> = T & IBaseApprovable;

export interface Currency {
  id: number;
  code: string;
  name: string;
  symbol: string;
  decimail_places: number;
  rate: string;
  base_uuid: string;
  decimal_places?: string;
}

export interface IInstitution {
  id: number;
  institution_name: string;
  institution_email: string;
  first_phone_number: string;
  base_uuid: string;
}

export interface IBranch {
  id: number;
  branch_name: string;
  base_uuid: string;
  reference_code: string;
  branch_email?: string;
  branch_phone_number?: string;
  branch_location?: string;
  inventory_cost_variance_account?: {
    id: number;
    base_uuid?: string;
    account_name?: string;
    reference_code?: string | null;
  } | null;
}

export interface IUser {
  id: number;
  base_uuid: string;
  fullname: string;
  email: string;
}
export interface ICashAtHand {
  id: number;
  approvals: any[];
  created_by: IUser;
  updated_by: IUser;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  original_data: string | null;
  approval_status: "under_creation" | "pending" | "approved" | "rejected" | "active";
  account_name: string;
  account_code: string;
  account_balance: string;
  description: string;
  location: string;
  responsible_person: string;
  currency: Currency | null;
  institution: IInstitution;
  branch: IBranch | null;
  general_journal_items?: IJournalEntriesData;
  charts_of_accounts_reference?: {
    id: number;
    reference_code: string;
    account_name: string;
    base_uuid: string;
  };
}

export interface ICashAtHandFormData {
  auto_create_ledger_account?: boolean;
  account_name: string;
  account_balance: string;
  description: string;
  responsible_person: string;
  currency?: string;
  branch?: string;
  reference_code?: string;
  charts_of_accounts_reference?: string | number;
  confirm_financial_mapping_change?: boolean;
}

export interface IExchangeRate {
  id: number;
  base_uuid: string;
  rate: string;
  format: string;
  currency: Currency | null;
  one_side: {value: number; currency: Currency};
  other_side: {value: number; currency: Currency};
}

export interface IDigitalWallet {
  custodian?: UserProfile | null;
  id: number;
  approvals: string;
  created_by: IUser;
  updated_by: IUser;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  model_content_type_id?: number;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  original_data: string | null;
  approval_status: "under_creation" | "pending" | "approved" | "rejected" | "active";
  account_name: string;
  account_code: string;
  account_balance: string;
  description: string;
  email: string;
  platform_name: string;
  wallet_id: string;
  currency: Currency;
  institution: IInstitution;
  branch: IBranch;
  charts_of_accounts_reference?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    account_name: string;
  };
  general_journal_items?: IJournalEntriesData;
}

export interface IDigitalWalletFormData {
  custodian?: string | null;
  account_name: string;
  auto_create_ledger_account?: boolean;
  account_balance: string;
  description: string;
  email: string;
  platform_name: string;
  wallet_id: string;
  currency?: string;
  branch?: string;
  reference_code: string;
  charts_of_accounts_reference?: string | number;
  confirm_financial_mapping_change?: boolean;
}

export interface IDigitalWalletUpdateData {
  custodian?: string | null;
  account_name: string;
  auto_create_ledger_account?: boolean;
  description: string;
  email: string;
  platform_name: string;
  wallet_id: string;
  currency?: string;
  charts_of_accounts_reference?: string;
  confirm_financial_mapping_change?: boolean;
  branch?: string;
  reference_code: string;
}

export interface IMobileMoneyAccount {
  id: number;
  approvals: string;
  created_by: IUser;
  updated_by: IUser;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  original_data: string | null;
  approval_status: "under_creation" | "pending" | "approved" | "rejected" | "active";
  account_name: string;
  account_code: string;
  account_balance: string;
  description: string;
  phone_number: string;
  provider_name: string;
  currency: Currency | null;
  institution: IInstitution;
  branch: IBranch;
  general_journal_items?: IJournalEntriesData;
  charts_of_accounts_reference?: {
    id: number;
    reference_code: string;
    account_name: string;
    base_uuid: string;
  };
}

export interface IMobileMoneyFormData {
  account_name: string;
  account_balance: string;
  auto_create_ledger_account?: boolean;
  description: string;
  phone_number: string;
  provider_name: string;
  currency?: number | string;
  branch?: string;
  reference_code: string;
  charts_of_accounts_reference?: number | string;
  confirm_financial_mapping_change?: boolean;
}

export interface IMobileMoneyUpdateData {
  account_name: string;
  auto_create_ledger_account?: boolean;
  description: string;
  phone_number?: string;
  provider_name?: string;
  currency?: string;
  branch?: string;
  charts_of_accounts_reference?: string;
  confirm_financial_mapping_change?: boolean;
  reference_code: string;
}

export interface ICashAccount {
  account_name: string;
  bank_name: string;
  reference_code: string;
  description?: string | null;
  account_balance?: string | null;
  base_uuid: string;
  currency?: {
    id: number;
    code: string;
    name: string;
    symbol: string;
  } | null;
  model: {
    id: number;
    model_name: string;
  };
}

export interface IStockMovementBranchToBranch {
  id: number;
  base_uuid: string;
  reference_code: string;
  stock_movement_code: string;
  stock_movement_date: string;
  stock_movement_status: "ALLOCATED" | "PENDING" | "COMPLETED" | "CANCELLED";
  approval_status: string;
  is_stock_moved: boolean;
  is_deleted: boolean;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  updated_by: number | null;
  branch_from: {
    base_uuid: string;
    branch_name: string;
    branch_location?: string;
    branch_email?: string;
    branch_phone_number?: string;
  } | null;
  branch_to: {
    base_uuid: string;
    branch_name: string;
    branch_location?: string;
    branch_email?: string;
    branch_phone_number?: string;
  } | null;
  items: {
    id: number;
    inventory_item: number;
    unit_of_measure: number;
    quantity: string;
  }[];
}

export interface IStockMovementFormData {
  stock_movement_date: string;
  branch_from: string;
  branch_to: string;
  reference_code?: string;
  description?: string;
  items: {
    inventory_item: string;
    unit_of_measure: string;
    quantity: string;
  }[];
}

export interface ICalculateAmountWithTaxesRequest {
  amount: string | number;
  base_uuid?: string;
  type?: string;
  applicable_taxes?: {
    tax: string | number;
    is_inclusive: boolean;
  }[];
}

export interface ICalculateAmountWithTaxesResponse {
  net_amount: number;
  tax_amount: number;
  gross_amount: number;
}

export interface IInventoryLineItem {
  line_item: string;
  unit_of_measure: string;
  quantity: number;
  unit_price?: string;
  item_name?: string;
  applicable_taxes?: {tax: number; is_inclusive: boolean}[];
  selected_uom_uuid?: string;
  item?: any;
}

export interface IOtherLineItem {
  line_item: string;
  unit_of_measure: string;
  quantity: number;
  unit_price: string;
}

export interface IFixedAssetLineItem {
  line_item: string;
  asset_category?: number | string;
  unit_of_measure: string;
  quantity: number;
  unit_price: string;
}

export type ApprovalStatuses = "under_creation" | "pending_approval" | "approved" | "rejected";

export type GRNStatus = "DRAFT" | "PENDING" | "APPROVED" | "REJECTED";

export interface IGoodsReceivedNote extends IBaseApprovable {
  id: number;
  base_uuid: string;
  reference_code: string;
  date_received: string;
  status: GRNStatus;
  remarks: string;
  description?: string;
  is_automated?: boolean;
  is_inventory_moved?: boolean;
  create_back_order?: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  is_deleted: boolean;
  is_active: boolean;
  created_by: number | null;
  updated_by: number | null;
  general_journal_items?: IJournalEntriesData;
  bill?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    purchase_order: {
      id: number;
      base_uuid: string;
      reference_code: string;
    };
    vendor_name: string;
  };
  purchase_order?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    vendor_name: string;
  };
  inventory_items: {
    id: number;
    base_uuid: string;
    item_type: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    line_item_name: string | null;
    other_asset_unit_of_measure: string | null;
    inventory_item: {
      id: number;
      base_uuid: string;
      item_name: string;
      reference_code?: string;
    };
    unit_of_measure: {id: number; base_uuid: string; unit_name: string} | null;
  }[];
  fixed_asset_items: {
    id: number;
    base_uuid: string;
    item_type: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    line_item_name: string;
    other_asset_unit_of_measure: string | null;
    asset_category: {id: number; base_uuid: string; category_name: string} | null;
  }[];
  other_items: {
    id: number;
    base_uuid: string;
    item_type: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    line_item_name: string;
    other_asset_unit_of_measure: string | null;
  }[];
  branch?: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string;
  } | null;
}

export interface IGoodsReceivedNoteFormData {
  branch?: string;
  purchase_order: string;
  description?: string;
  status?: GRNStatus;
  approval_status?: ApprovalStatuses;
  inventory_line_items: IInventoryLineItem[];
  reference_code?: string;
}

export type IBackOrderStatus = "pending_approval" | "approved" | "rejected" | "cancelled";

export interface IBackOrderPurchaseOrder {
  id: number;
  base_uuid: string;
  reference_code: string;
}

export interface IBackOrderGoodsReceivedNote {
  id: number;
  base_uuid: string;
  reference_code: string;
}

export interface IBackOrderInventoryLineItem {
  id: number;
  base_uuid: string;
  item_type: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item_name: string | null;
  other_asset_unit_of_measure: string | null;
  inventory_item: {id: number; base_uuid: string; item_name: string};
  unit_of_measure: {id: number; base_uuid: string; unit_name: string} | null;
}

export interface IBackOrderFixedAssetLineItem {
  id: number;
  base_uuid: string;
  item_type: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item_name: string;
  other_asset_unit_of_measure: string | null;
  asset_category: {id: number; base_uuid: string; category_name: string} | null;
}

export interface IBackOrderOtherLineItem {
  id: number;
  base_uuid: string;
  item_type: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item_name: string;
  other_asset_unit_of_measure: string | null;
}

export interface IBackOrderLineItem {
  id: number;
  base_uuid: string;
  reference_code: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item?: {
    base_uuid: string;
    inventory_item?: {
      item_name: string;
      item_code: string;
    };
  };
  unit_of_measure?: {
    unit_of_measure?: {
      unit_name: string;
      unit_abbreviation: string;
    };
  };
}

export interface IBackOrder {
  id: number;
  approvals: any[];
  created_by: IUser;
  updated_by: IUser | null;
  purchase_order: IBackOrderPurchaseOrder;
  goods_received_note: IBackOrderGoodsReceivedNote;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  original_data: string | null;
  approval_status: ApprovableEntityStatus;
  status: IBackOrderStatus;
  description: string;
  additional_notes: string;
  are_initial_journal_entries_made: boolean;
  inventory_line_items: IBackOrderInventoryLineItem[];
  fixed_asset_line_items: IBackOrderFixedAssetLineItem[];
  other_line_items: IBackOrderOtherLineItem[];
  general_journal_items?: IJournalEntriesData;
  line_items?: IBackOrderLineItem[];
  branch: {
    base_uuid: string;
    branch_name: string;
    reference_code: string;
  };
  goods_issue_note?: {
    id: number;
    base_uuid: string;
    reference_code: string;
  } | null;
}

export interface IBackOrderFormData {
  purchase_order?: string;
  goods_received_note?: string;
  inventory_line_items: IInventoryLineItem[];
  fixed_asset_line_items: IFixedAssetLineItem[];
  other_line_items: IOtherLineItem[];
  external_base_uuid?: string;
  reference_code?: string;
  status?: IBackOrderStatus;
  additional_notes?: string;
  are_initial_journal_entries_made?: boolean;
}

export type WriteOffReason = "damaged" | "expired" | "lost" | "obsolete" | "stolen" | "other";
export type WriteOffStatus = "draft" | "posted" | "cancelled";

export interface IWriteOffInstitutionLineItem {
  id: number;
  base_uuid: string;
  reference_code: string;
  inventory_item: {
    id: number;
    base_uuid: string;
    item_name: string;
  };
  inventory_item_unit_of_measure: {
    id: number;
    base_uuid: string;
    unit_name: string;
  };
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface IWriteOffBranchLineItem {
  id: number;
  base_uuid: string;
  reference_code: string;
  branch_inventory_item: {
    id: number;
    base_uuid: string;
    inventory_item: {
      id: number;
      base_uuid: string;
      item_name: string;
    };
  };
  branch_item_unit_of_measure: {
    id: number;
    base_uuid: string;
    unit_name: string;
  };
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface IWriteOffLineItems {
  institution_line_items: IWriteOffInstitutionLineItem[];
  branch_line_items: IWriteOffBranchLineItem[];
}

export interface IWriteOff {
  id: number;
  approvals: any[];
  created_by: IUser;
  updated_by: IUser | null;
  institution: {
    id: number;
    base_uuid: string;
    institution_name: string;
  };
  branch: {
    id: number;
    base_uuid: string;
    branch_name: string;
  } | null;
  expense_account: {
    id: number;
    base_uuid: string;
    account_name: string;
    account_code: string | null;
  };
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  model_content_type_id?: number;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  original_data: string | null;
  approval_status: ApprovableEntityStatus;
  reason: WriteOffReason;
  additional_notes: string | null;
  description: string | null;
  write_off_date: string;
  status: WriteOffStatus;
  are_journal_entries_made: boolean;
  general_journal_items?: IJournalEntriesData;
  write_off_type: "Institution Based" | "Branch Based" | "Unknown";
}

export interface IWriteOffInstitutionLineItemFormData {
  inventory_item: string;
  inventory_item_unit_of_measure: string;
  quantity: number;
  unit_price: string;
}

export interface IWriteOffBranchLineItemFormData {
  branch_inventory_item: string;
  branch_item_unit_of_measure: string;
  quantity: number;
  unit_price: string;
}
export interface IWriteOffFormData {
  expense_account: string;
  reason: WriteOffReason;
  write_off_date: string;
  description?: string;
  reference_code?: string;
  institution_line_items: IWriteOffInstitutionLineItemFormData[];
  branch_line_items: IWriteOffBranchLineItemFormData[];
}

export interface IReportDownloadBody {
  statement_type:
    | "balance_sheet_statement"
    | "income_statement"
    | "trial_balance_statement"
    | "cash_flow_statement";
  branches?: string[];
  cash_flow_method?: "direct" | "indirect";
  fiscal_years?: {fiscal_year_base_uuid: string}[];
  custom_dates?: {start_date: string; end_date: string}[];
  file_type: "pdf" | "excel";
}
export interface IPeriodLocking {
  base_uuid: string;
  account_name: string;
  account_code: string | null;
  account_group_name: string;
  posting_locked_until: string;
  actions?: React.ReactNode;
}

export interface IPeriodLockedFormData {
  is_account_specific: boolean;
  accounts: string[];
  date: string;
}

export interface IVendorBalanceAdjustment {
  id: number;
  base_uuid: string;
  reference_code: string;
  balance_adjusted: string;
  adjustment_date: string;
  amount: string;
  amount_before_adjustment: string;
  amount_after_adjustment: string;
  reason: string;
  created_at: string;
  vendor: number;
}

export interface IGINFormData {
  purchase_order: string;
  reference_code?: string;
  description?: string;
  external_base_uuid?: string;
  date_issued?: string;
  is_automated?: boolean;
  initiated_by?: number;
}

export interface IGINLineItem {
  id: number;
  quantity: number;
  quantity_returned?: number;
  quantity_that_can_be_returned?: number;
  quantity_that_can_be_refunded?: number;
  base_uuid: string;
  unit_price: number;
  line_total?: number;
  total?: number;
  unit_of_measure?: {
    base_uuid: string;
    unit_name: string;
    unit_abbreviation: string;
  };
  line_item?: {
    base_uuid: string;
    can_be_returned?: boolean;
    inventory_item?: {
      item_name: string;
      reference_code?: string;
    };
  };
}

export interface IGIN extends IBaseApprovable {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  invoice?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    customer_name?: string;
  } | null;
  reference_code?: string;
  description?: string;
  line_items_count: number;
  status: "draft" | "pending" | "approved" | "cancelled";
  date_issued?: string;
  created_at: string;
  updated_at: string;
  created_by: {
    id: number;
    fullname: string;
    email: string;
  };
  is_automated?: boolean;
  create_back_order?: boolean;
  is_inventory_removed?: boolean;
  general_journal_items?: IJournalEntriesData;
  purchase_order?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    customer_name?: string;
  };
  branch?: {
    id: number;
    base_uuid: string;
    branch_name: string;
  };
}

export interface IStockLocation {
  location_type: "WAREHOUSE" | "BRANCH";
  location_name: string;
  quantity_remaining: number;
}

export interface IProductUnitOfMeasure {
  unit_of_measure: string;
  unit_abbreviation: string;
  stock_locations: IStockLocation[];
}

export interface IProductCategory {
  name: string;
}

export interface IProduct {
  id: number;
  base_uuid: string;
  reference_code: string;
  item_name: string;
  total_quantity: number;
  total_buying_value: number;
  total_selling_value: number;
  category?: IProductCategory;
  units_of_measure: IProductUnitOfMeasure[];
}

export interface IProductsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: {
    products: IProduct[];
  };
}

export interface IStockMovementDownloadParams {
  product_id?: string;
  branch_id?: string;
  file_type: "pdf" | "excel";
  delivery_method: "download" | "email";
  recipient_email?: string;
  movement_type?: string;
  stock_level?: string;
  date_filter?: string;
  start_date?: string;
  end_date?: string;
}

export type RevaluationType = "UPWARD" | "DOWNWARD";

export interface IAssetRevaluation {
  id: number;
  approvals: string;
  created_by: IUser;
  updated_by: IUser;
  asset_name: string;
  asset_reference: string;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  description: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string | null;
  original_data: string;
  approval_status: "under_creation" | "pending" | "approved" | "rejected" | "active";
  revaluation_date: string;
  previous_value: string;
  new_value: string;
  revaluation_amount: string;
  revaluation_type: RevaluationType;
  valuer_name: string;
  valuation_basis: string;
  are_initial_journal_entries_made: boolean;
  asset: IFixedAssetItem | number;
  general_journal_items?: IJournalEntriesData;
}

export interface IAssetRevaluationFormData {
  description?: string;
  reference_code?: string;
  revaluation_date: string;
  new_value: string;
  valuer_name?: string;
  valuation_basis?: string;
  asset: number;
}
export interface IPrepaymentAllocation {
  id: number;
  base_uuid: string;
  prepayment: {
    id: number;
    base_uuid: string;
    reference_code: string;
  };
  bill: {
    id: number;
    base_uuid: string;
    reference_code: string;
    total_amount: string;
  } | null;
  amount_applied: string;
  created_at: string;
}

export interface IRequisitionItemFormData {
  reference_code?: string;
  name: string;
  description?: string | null;
  unit_of_measure?: string | null;
  unit_price?: string | null;
  requisition_type_settings?: {
    requisition_type: string;
    description?: string | null;
    unit_of_measure?: string | null;
    unit_price?: string | null;
    beneficiaries?: {
      beneficiary: string;
    }[];
    taxes_that_apply?: {
      tax: string;
      withhold_tax_amount: boolean;
    }[];
    allow_unconfigured_beneficiaries: boolean;
    max_quantity?: number | null;
    should_unit_price_be_edited: boolean;
    price_change_direction?: "up" | "down" | "both" | null;
    allowable_price_change_threshold_in_percentage?: string | null;
  };
}

export interface IRequisitionItem {
  id: number;
  base_uuid: string;
  reference_code?: string;
  name: string;
  description?: string;
  unit_price?: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  is_deleted: boolean;
  approval_status: ApprovableEntityStatus;
  approvals: Approval[];
  unit_of_measure: string;
  institution: number;
  created_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  };
  updated_by: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  };
}

export interface IStockReportRow {
  reference_code: string;
  item_code: string;
  item_name: string;
  description: string | null;
  category: {id: number; uuid: string; name: string} | null;
  unit_of_measure: {id: number; uuid: string; name: string} | null;
  cost_price: string;
  selling_price: string;
  quantity_on_hand: string;
  free_to_use_quantity: string;
  incoming_quantity: string;
  outgoing_quantity: string;
  forecasted_quantity: string;
  total: string;
}

export interface IActivityAssetReportRow {
  activity_date: string;
  asset: {
    id: number;
    base_uuid: string;
    reference_code: string;
    asset_name: string;
  };
  category: {
    id: number;
    base_uuid: string;
    category_name: string;
  } | null;
  activity_type: string;
  activity_type_display: string;
  value_before: string | null;
  value_after: string | null;
  performed_by: {
    id: number;
    base_uuid: string;
    fullname: string;
  } | null;
  source: {
    id: number | null;
    reference: string | null;
    model: string | null;
    content_type_id: number | null;
  };
}

export interface IDisposedAssetReportRow {
  id: number;
  base_uuid: string;
  reference_code: string;
  asset: IActivityAssetReportRow["asset"];
  category: IActivityAssetReportRow["category"];
  disposal_type: {
    id: number;
    disposal_name: string;
    disposal_code: string;
  };
  disposal_date: string;
  proceeds: string | null;
  gain_or_loss: string | null;
}

export interface IFixedAssetReportRow {
  id: number;
  base_uuid: string;
  reference_code: string;
  asset_name: string;
  category_name: string;
  purchase_date: string;
  purchase_price: string;
  accumulated_depreciation: string | null;
  current_book_value: string;
  status: string;
  is_active: boolean;
  created_at: string;
}

export interface IBalanceAdjustmentsFormData {
  date: string;
  account_type: string;
  reference_code: string;
  account_name_number: string;
  flow_type: "IN" | "OUT";
  flow_type_display: string;
  balance_before: string;
  balance_after: string;
  amount: string;
  source_reference_name: string;
  source_reference_code: string;
}

export interface IBalanceAdjustmentsDownloadPayload {
  account_uuids?: string[];
  file_type: "pdf" | "excel";
  date_filter: "all" | "range";
  start_date?: string;
  end_date?: string;
  flow_type?: "IN" | "OUT";
  account_type?: string;
  account_uuid?: string;
}

export interface ICashAccountReport {
  reference_code: string;
  account_name: string;
  account_type: string;
  balance: number;
  created_at: string;
  date: string;
}

export interface ICashAccountReportDownload {
  file_type: "pdf" | "excel";
  account_name?: string;
  account_type?: string;
  account_uuid?: string;
  search?: string;
  date_filter: "all" | "range";
  start_date?: string;
  end_date?: string;
}

export interface ICustomerBalanceReport {
  reference_code: string;
  customer_name: string;
  receivables: string;
  deposit: string;
  customer_type: string;
  tin: string;
  created_at: string;
  date_filter: "all" | "range";
  start_date?: string;
  end_date?: string;
}

export interface ICustomerBalanceReportDownload {
  file_type: "pdf" | "excel";
  search?: string;
  date_filter: "all" | "range";
  start_date?: string;
  end_date?: string;
  customer_type?: string;
}

export interface IVendorBalanceReport {
  reference_code: string;
  vendor_name: string;
  payables: string;
  deposit: string;
  vendor_type: string;
  tin: string;
  created_at: string;
  date_filter: "all" | "range";
  start_date?: string;
  end_date?: string;
}

export interface IVendorBalanceReportDownload {
  file_type: "pdf" | "excel";
  search?: string;
  date_filter: "all" | "range";
  start_date?: string;
  end_date?: string;
  vendor_type?: string;
}

export interface ILedgerReportAccount {
  reference_code: string;
  account_name: string;
  debits: string;
  credits: string;
  level: number;
  children: ILedgerReportAccount[];
}

export interface ILedgerReportDownload {
  file_type: "pdf" | "excel";
  search?: string;
  date_filter?: string;
  start_date?: string;
  end_date?: string;
}
