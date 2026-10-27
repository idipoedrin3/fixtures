import {IProject} from "../_api/services/projects.service";
import {
  ApprovableEntityStatus,
  Approval,
  IBaseApprovable,
  IBranch,
  ICashAccount,
  IGIN,
  IInstitution,
} from "./approvals.types";
import {ICashbook} from "#/_api/cashbooks";
import {CUSTOM_CODES, PERMISSION_CODES} from "#/_constants/enums";
import {
  IExchangeRateInput,
  IExchangeRateRepresentation,
  IStockMovementStrategy,
  IStockValuationMethod,
} from "../_api/services/system.service";
import {IBranchAdmin} from "../_api/services/user.service";
import {IVendorPrepayment} from "../_api/services/vendor.service";
import {PreferredVendorRow} from "../_components/custom/purchases/line-items";
import {VendorLineItem, VendorLineItemType} from "../_components/custom/line-items-input";
import {FileEntry, toFileEntry, withNamedFile} from "../_lib/file-utils";
import {IJournalEntriesData} from "../_components/common/tables/journal-entries-table";
import {ReactNode} from "react";
import {
  IBeneficiaryPaymentMethod,
  IBeneficiaryPaymentMethodFormData,
  ICountry,
  IRequisitionBeneficiary,
} from "./types.utils";
import {FEATURE_CODES} from "#/_constants/features.enum";
import type {IInstitutionSupportedCurrency} from "./email";

export interface IPaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
  meta?: {
    ordering_fields: string[];
    filterset_fields: string[];
  };
  other_info?: {
    total_payable: string;
    sub_total: string;
    total_tax: string;
  };
}

export interface ICustomApiRequestError {
  message: string;
  status: number;
  custom_code?: CUSTOM_CODES | null;
}

export type DATE_FORMAT_CHOICES = "dd/mm/yy" | "mm/dd/yy" | "yy/mm/dd";

export interface IUserInstitution {
  id: number;
  base_uuid: string;
  institution_email: string;
  institution_owner_id: number;
  institution_name: string;
  institution_logo: string | null;
  theme_color: null | string;
  branches?: Branch[];
  first_phone_number: string;
  second_phone_number: string;
  fiscal_year_start_month: number;
  location: string;
  currency?: Currency;
  maximum_cashbook_topup_amount?: string | null;
  invoice_taxes: {
    id: number;
    scope: "invoice" | "item";
    is_inclusive: boolean;
    tax: {
      id: number;
      base_uuid: string;
      tax_name: string;
    };
  }[];
  default_invoice_due_days: number | null;
  is_sales_person_commission_enabled: boolean;
  commission_percentage: number | null;
  is_tax_filing_automated: boolean;
  user_inactivity_time: number;
  date_format: DATE_FORMAT_CHOICES;
  default_pagination_page_size: string;
  is_integrated_in_peracosoft: boolean;
  tax_identification_number: string;
  industry?: IIndustry;
  accounting_method: "Accrual" | "Cash";
  profit_orientation: "Profit-Oriented" | "Non-Profit";
  supports_multiple_currencies: boolean;
  supported_currencies: ISupportedCurrencyForm[];
  default_stock_valuation_method?: IStockValuationMethod;
  default_stock_movement_strategy?: IStockMovementStrategy;
  supports_sales_returns: boolean;
  minimal_days_for_sales_return?: Number;
  rejection_reason?: string;
  suspension_reason?: string;
  approval_status_display:
    | "Pending Approval"
    | "Approved"
    | "Rejected"
    | "Under Review"
    | "Suspended";
  deposit_distribution_strategy?:
    | "PAY_OLDEST_INVOICE_FIRST"
    | "PAY_LAST_INVOICE_FIRST"
    | "HOLD_AS_CREDIT";
  feature_statuses?: FEATURE_CODES[];
  allow_sales_out_of_stock: boolean;
  enable_cash_refund_for_item_return: boolean;
  auto_depreciation_enabled: boolean;
  should_vendor_payments_go_through_requisitions: boolean;
  require_statement_for_cash_account_reconciliation?: boolean;
  inventory_reduction_timing?: "ON_GIN" | "ON_INVOICE";
  inventory_increment_timing?: "ON_BILL_RECEIPT" | "ON_GRN";
  payment_options?: {
    id: number;
    base_uuid: string;
    is_active: boolean;
    deleted_at: string | null;
    content_type: number;
    object_id: number;
    payment_option: ICashAccount | null;
  }[];
  allow_unit_breakdown: boolean;
  unit_breakdown_strategy: "SMALLEST_ONLY" | "LARGEST_FIRST";
  quotation_default_expiry_days: number | string;
  timezone: string;
  are_notifications_enabled: boolean;
  allow_item_reuse_across_templates: boolean;
  cash_account_reconciliation_automatch_threshold_percent?: string | null;
  has_baisoftpay_configuration: boolean;
}

export interface ISupportedCurrency {
  id: string;
  one_side: {
    value: string;
    currency_id: string;
    currency?: Currency;
  };
  other_side: {
    value: string;
    currency_id: string;
    currency?: Currency;
  };
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  deleted_at: string | null;
  rate: string;
  format: string;
  currency: Currency;
}

export interface ISupportedCurrencyForm {
  currency_id: string;
  one_side: {
    value: string;
    currency_id: string;
    currency?: Currency;
  };
  other_side: {
    value: string;
    currency_id: string;
    currency?: Currency;
  };
}

export interface IIndustryCategory {
  id: string;
  base_uuid: string;
  reference_code: string;
  category_code: string;
  category_name: string;
  category_description?: string;
}
export interface IIndustry {
  base_uuid: string;
  id: string;
  industry_name: string;
  industry_description?: string;
  is_deleted: true;
  is_active: true;
  created_at: string;
  updated_at: string;
  external_base_uuid: string;
  reference_code: string;
  created_by: string;
  updated_by: string;
  industry_category: IIndustryCategory;
}

export interface Role {
  id: number;
  name: string;
  description: string;
  permissions?: IPermission[];
  reference_code: string;
  permissions_details?: IPermission[];
}

export interface IBranchSupportedCurrency {
  id: number;
  branch: Branch;
  currency: Currency;
  rate: string;
  is_default: boolean;
  base_uuid: string;
  created_at: string;
  updated_at: string;
}

export interface IStaffFormData {
  email: string;
  fullname: string;
  branches: string[];
  role: string | null;
  bio?: string;
}

export interface Branch {
  id: number;
  base_uuid: string;
  institution: number;
  reference_code: string;
  branch_name: string;
  branch_phone_number?: string;
  branch_location: string;
  branch_longitude: string;
  branch_latitude: string;
  branch_email?: string;
  branch_opening_time?: string;
  branch_closing_time?: string;
  branch_type: "BRANCH" | "SUBSIDIARY" | "AFFILIATE" | "DIVISION";
  status: "operational" | "suspended" | "closed";
  parent?: Branch;
  children?: Branch[];
  created_at: string;
  updated_at: string;
  admins?: IBranchAdmin[];
  currency?: Currency;
  supported_currencies?: IBranchSupportedCurrency[];
  website?: string;
  ownership_percentage?: string;
  supports_multiple_currencies?: boolean;
  address?: string;
  state_or_region?: string;
  city?: string;
  registration_number?: string;
  tax_identification_number?: string;
  date_incorporated?: string;
  is_active: boolean;
  is_deleted: boolean;
  branch_legal_name?: string;
  default_stock_valuation_method?: IStockValuationMethod;
  default_stock_movement_strategy?: IStockValuationMethod;
  deposit_distribution_strategy?:
    | "PAY_OLDEST_INVOICE_FIRST"
    | "PAY_LAST_INVOICE_FIRST"
    | "HOLD_AS_CREDIT";
  allow_sales_out_of_stock?: boolean;
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
  phone_number: string | null;
  gender: string;
  is_active: boolean;
  is_staff: boolean;
  user_type: string;
  username: string;
  reference_code: string;
  roles: Role[];
  branches: IBranch[];
  groups: any[];
  permissions: string[];
  user_permissions: any[];
  last_login: string | null;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  updated_by: number | null;
}

export interface ICreatedByProfile {
  fullname: string;
  base_uuid: string;
  profile_photo_base64: string | null;
}

export interface UserProfile {
  id: number;
  base_uuid: string;
  bio: string | null;
  signature_base64: string | null;
  reference_code: string;
  institution: number;
  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  profile: {
    id: number;
    user: IUser;
    institutions: number[];
  };
}

export interface Permission {
  id: number;
  base_uuid: string;
  permission_name: string;
  permission_code: string;
  permission_description: string;
  category: {
    id: number;
    base_uuid: string;
    permission_category_name: string;
    permission_category_description: string;
  };
}

export interface StoredColorData {
  colors: string[];
  timestamp: number;
}

// Interface for Permissions
export interface IPermission {
  permission_code: PERMISSION_CODES;
  name: string;
  description: string;
}

// System Group Account Type (from system app)
export interface ISystemGroupAccountType {
  id: number;
  group_type_name: "asset" | "liability" | "equity" | "revenue" | "expense";
  group_type_code: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface IDefaultAccount {
  id: number;
  base_uuid: string;
  is_deleted: boolean;
  default_account_name: string;
  account_balance: string;
  action_type: string;
  created_at: string;
  updated_at: string;
}

export interface IDefaultAccountFormData {
  id: number;
  base_uuid: string;
  is_deleted: boolean;
  default_account_name: string;
  account_balance: string;
}

export interface IAccount {
  id: number;
  base_uuid: string;
  is_deleted: boolean;
  can_be_deleted: boolean;
  can_be_activated: boolean;
  can_change_account_role: boolean;
  can_change_linked_cash_account: boolean;
  can_be_default_for_selected_role: boolean;
  is_default?: boolean;
  account_name: string;
  account_balance?: {
    local_balance?: string;
    foreign_balance?: string;
  };
  parent?: any;
  children?: any[];
  account_setting?: IInstitutionAccountSetting | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  linked_bank_account?: IBank | null;
  reference_code?: string;
  linked_cash_account?: ICashAccount | null;
  account_role: ISystemAccountRole;
  group_account?: {id: number; base_uuid: string; group_account_name: string} | null;
  group_account_name?: string;
  currency: Currency;
  cash_flow_category?: string;
  is_default_for_selected_role: boolean;
}

export interface IAccountFormData {
  account_name: string;
  currency?: string;
  is_active?: boolean;
  group_account?: number;
  parent?: number;
  cash_account_to_link?: {
    content_type: number;
    content_object_uuid: string;
  };
  account_role: number | string;
  account_balance?: string;
  cash_flow_category?: string;
  is_default_for_selected_role: boolean;
  reference_code?: string;
}

export interface IFiscalYear {
  reference_code: string;
  id: number;
  base_uuid: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current?: boolean;
  is_closed?: boolean;
  is_deleted?: boolean;
  created_at: string;
  updated_at: string;
  // created_by?: UserProfile | number | null;
  // updated_by?: UserProfile | number | null;
}

export interface IFiscalYearFormData {
  reference_code?: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current?: boolean;
  is_closed?: boolean;
}

export interface ISystemAccountRole {
  id: number;
  role_code: string;
  role_name: string;
  role_group: ISystemGroupAccountType;
  description?: string;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  reference_code?: string;
}

export interface IInstitutionAccountSetting {
  id: number;
  base_uuid: string;
  institution: IUserInstitution;
  account: IAccount;
  role: ISystemAccountRole;
  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  approval: Approval[];
  approval_status?: string;
}

export interface IInstitutionAccountSettingFormData {
  account: string;
  role: string;
}

export type ITransactionStatus =
  | "draft"
  | "pending"
  | "approved"
  | "posted"
  | "partially_paid"
  | "paid"
  | "overdue"
  | "cancelled"
  | "reversed"
  | "reconciled"
  | "disputed"
  | "refunded"
  | "failed"
  | "closed";

export interface ITransaction {
  id: number;
  base_uuid: string;
  transaction_reference?: string | null;
  transaction_date: string; // ISO datetime
  posting_date: string; // ISO datetime
  fiscal_year: IFiscalYear;
  transaction_title: string;
  description?: string | null;
  transaction_amount: string; // decimal as string
  transaction_amount_in_foreign_currency?: string | null;
  foreign_exchange_rate?: string | null;
  base_currency?: Currency | null;
  transaction_currency?: Currency | null;
  transaction_status: ITransactionStatus;
  approved_by?: UserProfile | number | null;
  posted_by?: UserProfile | number | null;
  is_deleted?: boolean;
  created_at: string;
  updated_at?: string;
  transaction_entries?: ITransactionEntry[]; // Array of transaction entries
  reference_code?: string;
  branch?: IBranch;
  original_transaction?: {id: number; base_uuid: string; reference_code: string} | null;
  reversal_transaction?: {id: number; base_uuid: string; reference_code: string} | null;
  reversed_by?: {
    id: number;
    username: string;
    email: string;
    fullname: string;
    reference_code: string;
  } | null;
}

export interface ITransactionEntry {
  id: number;
  base_uuid: string;
  reference_code: string;
  transaction: ITransaction;
  // optional account fields (models had commented account FKs)
  account?: IAccount | null;
  default_account?: IDefaultAccount | null;
  custom_account?: IAccount | null;
  entry_type: "debit" | "credit";
  entry_amount: string; // decimal as string
  entry_amount_in_foreign_currency?: string | null;
  foreign_exchange_rate?: string | null;
  transaction_currency?: Currency | null;
  base_currency?: Currency | null;
  balance_before: string; // decimal as string
  balance_after: string; // decimal as string
  foreign_balance_before?: string | null;
  foreign_balance_after?: string | null;
  description?: string | null;
  is_cash: boolean;
  cashflow_type: string;
  is_deleted?: boolean;
  is_reconciled: boolean;
  created_at: string;
  transaction_date?: string;
  updated_at?: string;
  created_by?: UserProfile | number | null;
  updated_by?: UserProfile | number | null;
}

export type ICashflowTypeChoice =
  | "OPERATING"
  | "INVESTING"
  | "FINANCING"
  | "CASH"
  | "NON_CASH"
  | "NOT_APPLICABLE";

export interface ITransactionFormData {
  reference_code?: string;
  transaction_date?: string; // ISO datetime
  transaction_title: string;
  description?: string;
  transaction_amount: string; // decimal as string
  content_type?: number;
  object_id?: number;
  transaction_entries: ITransactionEntryFormData[]; // Array of transaction entries
  transaction_reference?: string;
  transaction_status?: string;
  is_originating_from_manual_entry?: boolean;
}

export interface ITransactionEntryFormData {
  account?: string;
  entry_type: "debit" | "credit";
  entry_amount: string;
  description?: string;
  partner?: {
    content_type: number;
    partner_uuid: string;
  };
}

export interface IJournalEntryImportEntry extends ITransactionEntryFormData {
  accountData: IAccount;
  partner_uuid?: string | null;
  partner_content_type?: number | null;
}

export interface IJournalEntryImportResponse {
  count: number;
  total_debit: string;
  total_credit: string;
  entries: IJournalEntryImportEntry[];
}
export interface IItemCategoryAccount {
  id: number;
  base_uuid: string;
  account_name: string;
}
// --- Items (read & form interfaces)
export interface IItemCategory {
  id: number;
  base_uuid: string;
  reference_code?: string;
  name: string;
  description?: string | null;
  institution?: IUserInstitution;
  is_deleted?: boolean;
  created_at?: string;
  updated_at?: string;
  expense_account: IItemCategoryAccount | null;
  revenue_account: IItemCategoryAccount | null;
  inventory_account: IItemCategoryAccount | null;
}

export interface IItemCategoryFormData {
  name: string;
  description?: string;
  expense_account?: string;
  revenue_account?: string;
  inventory_account?: string;
  reference_code?: string;
}

export interface IItemUnitOfMeasure {
  id: number;
  base_uuid: string;
  institution: IUserInstitution;
  unit_name: string;
  unit_abbreviation: string;
  description?: string;
  is_deleted?: boolean;
  created_at: string;
  updated_at?: string;
  created_by?: IUser;
  reference_code?: string;
}

export interface IItemUnitOfMeasureFormData {
  unit_name: string;
  unit_abbreviation: string;
  description?: string;
}

export interface IInventoryItemPriceChange {
  id: number;
  inventory_item: number;
  type_of_price_change: "BUYING_PRICE" | "SELLING_PRICE";
  price_before: string;
  price_after: string;
  created_at: string;
}

export interface IStockLayer {
  id: number;
  base_uuid: string;
  reference_code: string;
  quantity_remaining: number;
  unit_cost: string;
  recieved_date: string;
  reorder_point: number;
  expiry_date: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  description: string | null;
  inventory_item: number;
  unit_of_measure: {
    id: number;
    base_uuid: string;
    unit_name: string;
    unit_abbreviation: string;
    description: string | null;
  };
  general_journal_items?: {
    journal_items: any[];
    total_credits: number;
    total_debits: number;
  };
}

export interface IInventoryItem {
  id: number;
  base_uuid: string;
  external_base_uuid?: string | null;
  reference_code?: string;
  description?: string;
  item_code: string;
  item_name: string;

  item_category?: {
    id: number;
    base_uuid: string;
    name: string;
    description?: string;
  } | null;

  unit_of_measure?: IItemUnitOfMeasure | null;

  inventory_item_units_of_measure: Array<{
    id?: number;
    base_uuid: string;
    inventory_item?: number;
    unit_of_measure: {
      id: number;
      base_uuid: string;
      unit_name: string;
      unit_abbreviation?: string;
      description?: string;
      is_base_unit_of_measure?: boolean;
    };
    conversion_factor: string | number;
    selling_price: string | number;
    is_base_unit_of_measure?: boolean;
    is_default?: boolean;
    other_uom?: {
      id: number;
      base_uuid: string;
      reference_code?: string;
      unit_name: string;
    };
    other_quantity?: string | number;
  }>;

  inventory_account?: IAccount | null;
  revenue_account?: IAccount | null;
  expense_account?: IAccount | null;

  preferred_vendors?: Array<{
    id: number;
    base_uuid: string;
    item: number;
    vendor: {
      vendor_name: string;
      vendor_type: string;
      gender?: string;
      tax_identification_number?: string | null;
      base_uuid?: string;
    };
    unit_prices: Array<{
      id: number;
      base_uuid: string;
      price: string;
      minimum_order_qty: number;
      unit_of_measure: {
        id: number;
        base_uuid: string;
        reference_code: string | null;
        unit_of_measure: {
          base_uuid: string;
          unit_name: string;
          reference_code: string | null;
        };
      };
    }>;
  }> | null;

  general_journal_items?: IJournalEntriesData;
  selling_price: string;
  buying_price?: string;
  quantity_on_hand: number;
  reorder_point: number;
  is_active: boolean;
  is_deleted?: boolean;
  created_at?: string;
  updated_at?: string;
  item_type?: "GOODS" | "SERVICES";
  can_be_sold?: boolean;
  can_be_purchased?: boolean;
  product_stock_valuation_method?: IStockValuationMethod;
  product_stock_movement_strategy?: IStockMovementStrategy;
  sales_tax?: {
    id: number;
    base_uuid: string;
    tax_name: string;
    reference_code: string;
  } | null;
  purchase_tax?: {
    id: number;
    base_uuid: string;
    tax_name: string;
    reference_code: string;
  } | null;
}

export interface IInventoryItemFormData {
  reference_code?: string;
  item_name: string;
  item_category: number;
  unit_of_measure?: number;
  selling_branches?: string[];
  reorder_point?: number;
  item_type?: "GOODS" | "SERVICES" | null;
  preferred_vendors?: PreferredVendorRow[];
  inventory_account?: string;
  revenue_account?: string;
  expense_account?: string;
  stock_layers?: {
    quantity_remaining: number;
    unit_cost: number;
    recieved_date: string;
    unit_of_measure?: string;
  }[];
  product_stock_valuation_method: string;
  product_stock_movement_strategy: string;
  inventory_item_units_of_measure: {
    unit_of_measure: string;
    conversion_factor: number;
    selling_price: number;
    is_base_unit_of_measure?: boolean;
  }[];
  selling_price?: number;
  expiry_date?: string;
  sales_tax?: string | "";
  purchase_tax?: string | "";
  can_be_sold?: boolean;
  can_be_purchased?: boolean;
}

export type IVendorType = "individual" | "business";

export interface IVendor {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  institution: IUserInstitution | number;
  is_deleted: boolean;
  vendor_name: string;
  vendor_type: IVendorType;
  outstanding_payables: string;
  lead_time: number;
  address: string;
  phone_number: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  gender?: "MALE" | "FEMALE" | "OTHER" | "";
  currency: Currency;
  default_account_payable: string;
  reference_code: string;
  opening_balance?: string;
  opening_balance_received_date?: string;
  deposit_balance?: string;
  tax_identification_number?: string | null;
  website?: string | null;
  payment_term?: IPaymentTerm | null;
  payment_options: IBeneficiaryPaymentMethod[];
  branch: {
    base_uuid: string;
    reference_code: string;
    branch_name: string;
  };
}

export type PaymentOptionRow = IBeneficiaryPaymentMethodFormData & {
  clientId: string;
  currencyDetails?: Pick<Currency, "id" | "code" | "name" | "symbol"> | null;
  country: ICountry | null;
  usesContactPhone?: boolean;
};

export interface IVendorFormData {
  vendor_name: string;
  vendor_type: IVendorType;
  address: string;
  phone_number: string;
  email: string;
  gender: "MALE" | "FEMALE" | "OTHER" | "";
  currency: number | "";
  foreign_exchange_rate?: IExchangeRateInput;
  default_account_payable: string | "";
  opening_balance_account: string | "";
  opening_balance: string;
  opening_balance_received_date: string;
  tax_identification_number?: string | null;
  payment_term?: string;
  payment_options?: PaymentOptionRow[];
  website?: string;
  reference_code?: string;
  description?: string;
  external_base_uuid?: string;
  are_initial_transactions_processed?: boolean;
  vendor_payment_options?: number[];
}

export interface IContentType {
  id: number;
  model: string;
  model_display: string;
}

export interface IObject {
  id: number;
  base_uuid: string;
  reference_code: string;
}

export interface IPurchaseOrder {
  can_record_payment_or_invoice?: boolean;
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  quotation: IQuotation;
  reference_code: string;
  issue_date: string;
  status: "draft" | "confirmed" | "shipped" | "delivered" | "canceled" | "approved";
  total_amount?: number;
  total_price?: string | number;
  net_total: string;
  tax_total: string;
  gross_total: string;
  total_discount: string;
  goods_issued_note_status?: "full_issued" | "not_issued" | "partially_issued" | "not_required";
  invoice_status?: "fully_invoiced" | "not_invoiced" | "partially_invoiced";
  line_items?: IPurchaseOrderLineItem[];
  line_items_count?: number;
  created_at: string;
  updated_at: string;
  institution: {
    name: string;
    location: string;
    email: string;
  };
  currency: Currency;
  exchange_rate?: {
    source: "base_currency" | "document_snapshot";
    one_side: {
      currency: Currency;
      value: string;
    };
    other_side: {
      currency: Currency;
      value: string;
    };
    canonical_rate: string;
  } | null;
  exchange_rate_status?: "base_currency" | "document_snapshot" | "missing";
  customer?: ICustomer;
  description?: string;
  payments?: ISalesOrderPayment[];
  branch?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    branch_name: string;
  };
}

export interface ISalesOrderPayment {
  id: number;
  base_uuid: string;
  reference_code: string;
  payment_date: string;
  amount_paid: string;
  amount_applied: string;
  payment_status: "pending" | "approved" | "transferred" | "rejected";
  description?: string | null;
  created_at: string;
  account?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    account_name: string;
  } | null;
  invoice?: {
    id: number;
    base_uuid: string;
    reference_code: string;
  } | null;
}

export interface ISalesOrderPaymentFormData {
  amount_paid: number;
  payment_date: string;
  description?: string;
  cash_account: {
    content_type: number;
    content_object_uuid: string;
  };
}

export interface IPurchaseOrderLineItem {
  quantity_billed: ReactNode;
  id: number;
  base_uuid: string;
  purchase_order: IPurchaseOrder;
  line_item: IBranchInventoryItem;
  quantity: number;
  quantity_billied: number;
  quantity_issued: number;
  quantity_pending: number;
  unit_price: string;
  line_total: string;
  line_item_tax_breakdowns?: IInvoiceLineItemTaxBreakdown[];
  discounts?: ISalesLineDiscount[];
  source_quotation_line?: {
    id: number;
    base_uuid: string;
  } | null;
  created_at: string;
  updated_at: string;
  unit_of_measure?: {
    id: number;
    selling_price: string;
    unit_abbreviation: string;
    unit_name: string;
    is_base_unit_of_measure: boolean;
    base_uuid: string;
  };
}

export interface IPurchaseOrderFormData {
  currency?: number;
  quotation?: number | null;
  issue_date: string;
  line_items: IPurchaseOrderLineItemFormData[];
  description?: string;
  reference_code?: string;
  customer?: number | string;
  exchange_rate?: {
    one_side: {
      currency: number;
      value: string;
    };
    other_side: {
      currency: number;
      value: string;
    };
  } | null;
  payment?: {
    amount_paid: number;
    cash_account: {
      content_type: number;
      content_object_uuid: string;
    };
  };
}

export interface IPurchaseOrderLineItemFormData {
  sales_order_line_item_uuid?: string;
  line_item: string;
  item_name?: string;
  item_category?: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  unit_of_measure: string;
  discounts?: ISalesLineDiscountFormData[];
  should_auto_create_manufacturing_order?: boolean;
  bill_of_material_to_be_used?: string;
  qty_to_be_manufactured?: number;
  manufacturing_order_description?: string;
}

export interface IBill {
  base_uuid: string;
  id: number;
  vendor: IVendor;
  transaction: ITransaction;
  description: string;
  purchase_order: IVendorPurchaseOrder;
  payment_terms: IPaymentTerm;
  due_date: string;
  total_amount: number;
  created_at: string;
  reference_code: string;
}

export type ICustomerType = "individual" | "business";

export interface ICustomer extends IBaseApprovable {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  institution: IUserInstitution;
  customer_name: string;
  customer_type: ICustomerType;
  credit_limit: string;
  deposit_balance: string;
  address: string;
  phone_number: string;
  email: string;
  is_active: boolean;
  payment_term?: IPaymentTerm;
  currency: Currency | null;
  created_at: string;
  updated_at?: string;
  created_by?: IUser;
  gender: "MALE" | "FEMALE" | "OTHER" | "";
  opening_balance?: string;
  opening_balance_received_date?: string;
  deposit_distribution_strategy?:
    | "PAY_OLDEST_INVOICE_FIRST"
    | "PAY_LAST_INVOICE_FIRST"
    | "HOLD_AS_CREDIT";
  outstanding_receivables_balance?: string;
  salesperson?: ISalesPerson | null;
  default_account?: IAccount | null;
  reference_code?: string;
  profile_photo?: string | null;
  tin?: string | null;
  opening_balance_account?: IAccount | null;
}
export interface ICustomerFormData {
  customer_name: string;
  customer_type: ICustomerType;
  credit_limit?: string;
  opening_balance_account: "" | string;
  address: string;
  phone_number: string;
  email: string;
  payment_term?: string | number;
  gender: "MALE" | "FEMALE" | "OTHER" | "";
  currency: string;
  foreign_exchange_rate?: IExchangeRateInput;
  opening_balance: string;
  opening_balance_received_date: string;
  deposit_distribution_strategy?:
    | "PAY_OLDEST_INVOICE_FIRST"
    | "PAY_LAST_INVOICE_FIRST"
    | "HOLD_AS_CREDIT";
  //salesperson?: string | null;
  profile_photo?: FileEntry | null;
  tin?: string;
  reference_code?: string;
  outstanding_receivables_balance: string;
  default_account?: string | null;
}
type CustomerInput = Omit<ICustomerFormData, "profile_photo"> & {
  profile_photo?: File | null;
};
export const buildCustomerPayload = async (input: CustomerInput): Promise<ICustomerFormData> => {
  const {profile_photo, ...rest} = input;
  return withNamedFile("profile_photo", profile_photo ?? null, rest);
};

export interface ISalesLineDiscount {
  id: number;
  base_uuid: string;
  discount_type: "percentage" | "fixed";
  discount_value: string;
  discount_amount: string;
  position: number;
  description?: string;
  source_discount?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ISalesLineDiscountFormData {
  id?: number;
  discount_type: "percentage" | "fixed";
  discount_value: string;
  position: number;
  description?: string;
}

// --- Quotation Types ---
export interface IQuotationLineItem {
  id: number;
  base_uuid: string;
  quotation: number;
  line_item: IBranchInventoryItem;
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item_tax_breakdowns?: IInvoiceLineItemTaxBreakdown[];
  discounts?: ISalesLineDiscount[];
  created_at: string;
  updated_at: string;
  unit_of_measure?: {
    id: number;
    selling_price: string;
    unit_abbreviation: string;
    unit_name: string;
    is_base_unit_of_measure: boolean;
    base_uuid: string;
  };
}

export interface IQuotationLineItemFormData {
  quotation_line_item_uuid?: string;
  type?: VendorLineItemType;
  line_item: string;
  item_name?: string;
  item_category?: string;
  quantity: number;
  unit_price: string;
  line_total?: string;
  unit_of_measure?: string;
  discounts?: ISalesLineDiscountFormData[];
}

export interface IQuotation {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  customer: ICustomer;
  reference_code: string;
  issue_date: string;
  status: "draft" | "sent" | "accepted" | "rejected";
  total_amount: string;
  net_total: string;
  tax_total: string;
  gross_total: string;
  total_discount: string;
  line_items?: IQuotationLineItem[];
  line_items_count: number;
  created_at: string;
  updated_at: string;
  institution: {
    name: string;
    location: string;
    email: string;
  };
  currency: string | Currency | null;
  exchange_rate: {
    source: "base_currency" | "document_snapshot";
    one_side: {
      currency: Currency;
      value: string;
    };
    other_side: {
      currency: Currency;
      value: string;
    };
    canonical_rate: string;
  } | null;
  exchange_rate_status: "base_currency" | "document_snapshot" | "missing";
  expiry_date?: string;
  description?: string;
}

export interface IQuotationFormData {
  customer: string;
  issue_date: string;
  line_items: IQuotationLineItemFormData[];
  exchange_rate?: {
    one_side: {
      currency: number;
      value: string;
    };
    other_side: {
      currency: number;
      value: string;
    };
  } | null;
  expiry_date?: string;
  description?: string;
}

// --- Invoice Types ---
export interface IInvoiceLineItem {
  id: number;
  base_uuid: string;
  reference_code?: string;
  branch_item: {
    id: number;
    item_name: string;
    item_code: string;
    base_uuid: string;
    inventory_item: {
      id: number;
      item_name: string;
      reference_code: string;
      base_uuid: string;
    };
  };
  quantity: number;
  unit_price: string;
  line_total: string;
  taxes?: ITax[];
  created_at: string;
  updated_at: string;
  item_tax_breakdowns?: ITaxBreakdown[];
  line_item_tax_breakdowns?: IInvoiceLineItemTaxBreakdown[];
  discounts?: ISalesLineDiscount[];
  unit_of_measure?: {
    id: number;
    selling_price: string;
    unit_abbreviation: string;
    unit_name: string;
    is_base_unit_of_measure: boolean;
    base_uuid: string;
    inventory_item_unit_of_measure?: {
      id: number;
      base_uuid: string;
    } | null;
  };
  quantity_issued?: string;
  quantity_ordered?: string;
  quantity_pending?: string;
}
export interface IInvoiceLineItemTaxBreakdown {
  id: number;
  base_uuid: string;
  gross_amount: string;
  net_amount: string;
  tax_amount: string;
  is_inclusive: boolean;
  source_breakdown?: number | null;
  tax: {
    id: number;
    base_uuid: string;
    tax_name: string;
    reference_code: string;
    is_inclusive: boolean;
    configured_is_inclusive: boolean;
  };
  content_type: number;
  object_id: number;
}

export interface IInvoiceLineItemFormData {
  invoice_line_item_uuid?: string;
  line_item: string;
  item_name: string;
  item_category?: string;
  quantity: number;
  quantity_issued: number;
  unit_price: string;
  line_total: string;
  unit_of_measure: string;
  tax_base_uuid?: string;
  tax_type?: string;
  type: VendorLineItemType;
  should_auto_create_manufacturing_order?: boolean;
  bill_of_material_to_be_used?: string;
  qty_to_be_manufactured?: number;
  manufacturing_order_description?: string;
  discounts?: ISalesLineDiscountFormData[];
}

export interface IInvoice {
  reference_code: string;
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  credit_note_total: string;
  customer: ICustomer;
  purchase_order: IPurchaseOrder;
  issue_date: string;
  due_date: string;
  invoice_status: "draft" | "not_sent" | "sent" | "paid" | "overdue" | "canceled";
  invoice_payment_status: "unpaid" | "partially_paid" | "paid" | "overdue";
  line_items?: IInvoiceLineItem[];
  total_amount: string;
  adjusted_total?: string;
  invoice?: {
    reference_code: string;
  };
  amount_due: string;
  amount_paid: string;
  created_at: string;
  payment_date?: string;
  funds_source?: string;
  payment_status?: string;
  amount_due_before_payment?: string;
  amount_due_after_payment?: string;
  notes?: string | null;
  updated_at: string;
  tax_summary: {
    total_exclusive_tax: number;
    total_inclusive_tax: number;
    total_tax: number;
    tax_details: {tax_name: string; is_inclusive: boolean; amount: number}[];
  };
  pending_balance?: string;
  tax_application_scope: "item" | "invoice" | "mixed" | "none";
  invoice_tax_breakdowns?: ITaxBreakdown[];
  currency: Currency;
  exchange_rate?: {
    source: "base_currency" | "document_snapshot";
    one_side: {
      currency: Currency;
      value: string;
    };
    other_side: {
      currency: Currency;
      value: string;
    };
    canonical_rate: string;
  } | null;
  exchange_rate_status?: "base_currency" | "document_snapshot" | "missing";
  description: string;
  net_total: string;
  tax_total: string;
  gross_total: string;
  total_discount: string;
  branch?: IBranch;
  goods_issued_note_status: "full_issued" | "partially_issued" | "not_issued" | "not_required";
  related_goods_issued_notes?: {
    base_uuid: string;
    reference_code: string;
    status: "draft" | "pending" | "approved" | "cancelled";
  }[];
  related_invoice_payments?: {
    uuid_value: string;
    ref_code: string;
    payment_date: string;
    type: "prepayment" | "payment";
  }[];
}

export interface ICashAccountFormData {
  content_type: number;
  content_object_uuid: string;
}
export interface IInvoiceFormData {
  purchase_order?: string;
  quotation?: string;
  customer?: string;
  recurring_invoice?: string;
  currency?: number;
  issue_date: string;
  line_items: IInvoiceLineItemFormData[];
  global_tax_ids?: string[];
  sales_person?: number;
  invoice_payment_status: "unpaid" | "partially_paid" | "paid";
  partial_amount_paid?: string | number;
  description?: string;
  cash_account?: ICashAccountFormData;
  payment_term?: string;
  exchange_rate?: {
    one_side: {currency: number; value: string};
    other_side: {currency: number; value: string};
  } | null;
}

export interface IRecurringInvoiceLineItem {
  id: number;
  quantity: string;
  unit_cost?: string;
  recurring_invoice?: number;
  line_item?: {
    id: number;
    item_name: string;
    item_code: string;
    base_uuid: string;
  };
  unit_of_measure?: {
    id: number;
    unit_name: string;
    selling_price?: string;
    unit_abbreviation?: string;
    is_base_unit_of_measure?: boolean;
    base_uuid?: string;
  };
  base_uuid?: string;
  branch_item?: {
    id: number;
    item_name: string;
    item_code: string;
  };
  unit_price?: string;
  line_total?: string;
  taxes?: ITax[];
  created_at?: string;
  updated_at?: string;
  item_tax_breakdowns?: ITaxBreakdown[];
}

export interface IRecurringInvoiceLineItemFormData {
  line_item: string;
  item_name: string;
  item_category?: string;
  quantity: number;
  unit_cost: string;
  line_total: string;
  unit_of_measure: string;
}

export interface IRecurringInvoiceSchedule {
  interval: number;
  days_of_week?: number[];
  days_of_month?: number[];
  weeks_of_month?: number[];
  months_of_year?: number[];
  additional_notes?: string;
}

export interface IRecurringInvoice {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  reference_code?: string;
  name?: string;
  approval_status: ApprovableEntityStatus;
  recurring_frequency: "daily" | "weekly" | "monthly" | "bi-annually" | "annually";
  branch: string;
  next_recurring_date: string;
  start_date: string;
  end_date?: string | null;
  customer: ICustomer;
  recurring_items: IRecurringInvoiceLineItem[];
  total_amount?: string;
  currency?: string;
  rate?: string;
  tax_application_scope?: "item" | "invoice" | "mixed" | "none";
  global_tax_ids?: string[];
  tax_summary?: {
    total_exclusive_tax: number;
    total_inclusive_tax: number;
    total_tax: number;
    tax_details: {tax_name: string; is_inclusive: boolean; amount: number}[];
  };
  created_at: string;
  updated_at: string;
  created_by?: {
    id: number;
    fullname: string;
  };
  updated_by?: any;
  is_deleted: boolean;
  is_active: boolean;
  deleted_at?: string | null;
  external_base_uuid?: string | null;
  original_data?: any;

  notes?: string;
  status?: never;
  frequency?: never;
  next_run_date?: never;
  last_generated_date?: string | null;
  description?: string;
  should_always_use_template_price: boolean;

  schedule?: IRecurringInvoiceSchedule;
}

export interface IRecurringInvoiceFormData {
  customer: string;
  branch: string;
  name?: string;
  recurring_frequency: "daily" | "weekly" | "monthly" | "bi-annually" | "annually";
  start_date: string;
  end_date?: string | null;
  recurring_items: IRecurringInvoiceLineItemFormData[];
  schedule: IRecurringInvoiceSchedule;
  should_always_use_template_price: boolean;
  global_tax_ids?: string[];
  sales_person?: number;
  currency?: string;
  notes?: string;
  description?: string;
  reference_code?: string;
}

export interface ICustomerPaymentRecord extends IBaseApprovable {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  reference_code: string;
  description?: string | null;
  amount: string;
  settlement_amount: string;
  currency: Currency;
  settlement_currency: Currency;
  payment_exchange_rate?: {
    source: "base_currency" | "document_snapshot";
    one_side: {currency: Currency; value: string};
    other_side: {currency: Currency; value: string};
    canonical_rate: string;
  } | null;
  settlement_exchange_rate?: {
    source: "same_currency" | "document_snapshot";
    one_side: {currency: Currency; value: string};
    other_side: {currency: Currency; value: string};
    canonical_rate: string;
  } | null;
  payment_date: string;
  payment_status: "DRAFT" | "APPROVED" | "CANCELLED";
  amount_reconciled: string;
  remaining_balance: string;
  are_initial_journal_entries_made: boolean;
  distribution_strategy?: string | null;
  customer?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    customer_name: string;
  } | null;
  invoice?: {
    id: number;
    base_uuid: string;
    reference_code: string;
  } | null;
  branch?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    branch_name: string;
  } | null;
  coa_cash_account?: IAccount | null;
  general_journal_items?: IJournalEntriesData;
  created_at: string;
  updated_at: string;
}

export interface ICustomerPaymentRecordFormData {
  customer?: string | null;
  invoice?: string | null;
  branch?: string | null;
  coa_cash_account?: string | null;
  amount: string;
  payment_exchange_rate?: {
    one_side: {currency: number; value: string};
    other_side: {currency: number; value: string};
  } | null;
  settlement_exchange_rate?: {
    one_side: {currency: number; value: string};
    other_side: {currency: number; value: string};
  } | null;
  payment_date: string;
  reference_code?: string;
  description?: string;
  distribution_strategy?: string | null;
}

// --- Vendor Purchase Order Types ---
export interface IVendorPurchaseOrderLineItem {
  id: number;
  base_uuid: string;
  line_item: IInventoryItem;
  quantity: number;
  unit_price: string;
  line_total: string;
  created_at: string;
  updated_at: string;
  tax_breakdowns?: ITaxBreakdown[];
  line_item_tax_breakdowns?: ITaxBreakdown[];
}

export interface IVendorPurchaseOrderLineItemFormData {
  line_item: number | string;
  item_name: string;
  item_category?: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface IVendorPurchaseOrderOtherExpense {
  id: number;
  expense_name: string;
  expense_amount: string;
  account_to_record_expense: string;
}

export interface IVendorPurchaseOrder {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  vendor: IVendor;
  vendor_prepayment: IVendorPrepayment;
  reference_code: string;
  issue_date: string;
  description?: string;
  expected_delivery_date?: string | null;
  expected_delivery_time?: string | null;
  status: "draft" | "approved" | "delivered" | "billed" | "canceled";
  line_items: IVendorPurchaseOrderLineItem[];
  expenses: IVendorPurchaseOrderOtherExpense[];
  goods_received_note_status: "not_received" | "partially_received" | "fully_received";
  bill_status: "not_billed" | "partially_billed" | "fully_billed";
  created_at: string;
  updated_at: string;
  total_amount: string;
  payment_mode: string;
  is_inventory_based: boolean;
  request_requisition: {
    id: number;
    base_uuid: string;
    requisition_code: string;
  };
  inventory_items: {
    id: number;
    quantity: number;
    base_uuid: string;
    unit_price: string;
    line_total: string;
    inventory_item: {id: number; base_uuid: string; item_name: string; item_type?: "GOODS" | "SERVICES"};
    unit_of_measure: {id: number; base_uuid: string; unit_name: string};
    line_item_tax_breakdowns?: ITaxBreakdown[];
  }[];
  other_items: {
    id: number;
    base_uuid: string;
    line_item_name: string;
    other_unit_of_measure: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    line_item_tax_breakdowns?: ITaxBreakdown[];
  }[];
  fixed_asset_items: {
    id: number;
    base_uuid: string;
    line_item_name: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    asset_category: {
      id: number;
      base_uuid: string;
      category_name: string;
    } | null;
    line_item_tax_breakdowns?: ITaxBreakdown[];
  }[];
  net_total?: string;
  tax_total?: string;
  gross_total?: string;
  supporting_document_file?: string | null;
  branch?: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string;
  };
  currency: Currency;
  exchange_rate?: {
    rate: string;
    source: string;
  } | null;
  exchange_rate_status?: "base_currency" | "document_snapshot" | "missing";
}

export interface IVendorPurchaseOrderOtherExpenseFormData {
  expense_name: string;
  expense_amount: string;
  account_to_record_expense: string;
}

export type FixedAssetLineItem = {
  line_item: string;
  asset_category?: string;
  quantity: number;
  unit_price: string;
  line_total: string;
};

export interface IVendorPurchaseOrderFormData {
  vendor: number;
  vendor_prepayment?: number;
  reference_code: string;
  issue_date?: string;
  is_inventory_based: boolean;
  inventory_line_items?: VendorLineItem[];
  other_line_items?: VendorLineItem[];
  line_items?: IVendorPurchaseOrderLineItemFormData[];
  expenses?: IVendorPurchaseOrderOtherExpenseFormData[];
  fixed_asset_line_items?: FixedAssetLineItem[];
  status?: "draft" | "approved" | "delivered" | "billed" | "canceled";
  additional_notes?: string;
  description?: string;
  request_requisition?: string;
  supporting_document_file?: FileEntry | null;
  expected_delivery_time?: string;
  expected_delivery_date?: string;
  branch?: string;
  exchange_rate?: IExchangeRateInput | null;
}

type VendorPurchaseOrderInput = Omit<IVendorPurchaseOrderFormData, "supporting_document_file"> & {
  supporting_document_file?: File | null;
};

export const buildVendorPurchaseOrderPayload = async (
  input: VendorPurchaseOrderInput,
): Promise<IVendorPurchaseOrderFormData> => {
  const {supporting_document_file, ...rest} = input;
  return withNamedFile("supporting_document_file", supporting_document_file ?? null, rest);
};

export interface IOrderExpense {
  id: number;
  approvals: any[];
  account_to_record_expense: IAccount;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  expense_name: string;
  amount: string;
  created_by: null;
  updated_by: null;
  bill: number;
  tax_breakdowns?: ITaxBreakdown[];
}

// --- Vendor Bill Types ---
export interface IVendorBillLineItem {
  id: number;
  base_uuid: string;
  line_item: IInventoryItem;
  inventory_item?: {
    id: number;
    base_uuid: string;
    item_name: string;
    reference_code?: string;
  } | null;
  asset_category?: {
    id: number;
    base_uuid: string;
    category_name: string;
  } | null;
  quantity: number;
  unit_price: string;
  total_amount: string;
  created_at: string;
  updated_at: string;
  tax_breakdowns?: ITaxBreakdown[];
  total_net_amount?: string;
  total_tax_amount?: string;
  adjusted_total?: string;
  debit_note_total?: string;
  balance_due?: string;
}

export interface IVendorBillLineItemFormData {
  line_item: number;
  quantity: number;
  unit_price: string;
  total_amount: string;
}

export interface IVendorBillLineItemTaxBreakdown {
  id: number;
  base_uuid: string;
  gross_amount: string;
  net_amount: string;
  tax_amount: string;
  tax: {
    id: number;
    base_uuid: string;
    tax_name: string;
  };
  content_type: number;
  object_id: number;
}

export interface IVendorBillInventoryLineItem {
  id: number;
  base_uuid: string;
  item_type: "inventory";
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item_name: string | null;
  other_asset_unit_of_measure: string | null;
  inventory_item: {
    id: number;
    base_uuid: string;
    item_name: string;
    item_type?: "GOODS" | "SERVICES";
  };
  unit_of_measure: {
    id: number;
    base_uuid: string;
    unit_name: string;
  };
  line_item_tax_breakdowns?: IVendorBillLineItemTaxBreakdown[];
  quantity_ordered: number;
  quantity_received: number;
  quantity_pending: number;
}

export interface IVendorBillOtherLineItem {
  id: number;
  base_uuid: string;
  item_type: "other";
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item_name: string;
  other_asset_unit_of_measure: string | null;
  line_item_tax_breakdowns?: IVendorBillLineItemTaxBreakdown[];
  quantity_ordered: number;
  quantity_received: number;
  quantity_pending: number;
}

export interface IVendorBillFixedAssetLineItem {
  id: number;
  base_uuid: string;
  item_type: "fixed_asset";
  quantity: number;
  unit_price: string;
  line_total: string;
  line_item_name: string;
  other_asset_unit_of_measure: string | null;
  line_item_tax_breakdowns?: IVendorBillLineItemTaxBreakdown[];
  asset_category?: {
    id: number;
    base_uuid: string;
    category_name: string;
  };
  quantity_ordered: number;
  quantity_received: number;
  quantity_pending: number;
}

export interface IVendorBill {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  reference_code: string;
  vendor?: IVendor;
  purchase_order?: IVendorPurchaseOrder;
  requisition?: IRequisition;
  transaction?: ITransaction;
  payment_terms?: IPaymentTerm | null;
  payment_term_name: string | null;
  status: string;
  due_date: string;
  received_date: string;
  description: string | null;
  total_amount: string;
  balance_due: string;
  total_net_amount: string;
  total_tax_amount: string;
  debit_note_total: string;
  adjusted_total: string;
  currency: Currency;
  rate: number;
  inventory_line_items: IVendorBillInventoryLineItem[];
  other_line_items: IVendorBillOtherLineItem[];
  fixed_asset_line_items: IVendorBillFixedAssetLineItem[];
  line_item_tax_breakdowns?: IVendorBillLineItemTaxBreakdown[];
  line_items?: IVendorBillLineItem[];
  order_expenses: IOrderExpense[];
  tax_breakdowns?: ITaxBreakdown[];
  created_at: string;
  updated_at: string;
  institution: number;
  are_initial_journal_entries_made: boolean;
  general_journal_items?: IJournalEntriesData;
  goods_received_note_status: "full_received" | "partially_received" | "not_received";
  payment_status: "unpaid" | "paid" | "partially_paid";
  branch?: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string;
  };
}

export interface IVendorBillFormData {
  vendor?: string;
  purchase_order?: string;
  branch?: string;
  due_date?: string;
  payment_status?: "unpaid" | "paid" | "partially_paid";
  payment_terms?: string;
  description?: string;
  inventory_line_items?: {
    line_item: string;
    unit_of_measure: string;
    quantity: number;
    unit_price: string;
    item_name?: string;
    applicable_taxes?: {tax: string | number; is_inclusive: boolean}[];
  }[];
  other_line_items?: {
    line_item: string;
    unit_of_measure: string;
    quantity: number;
    unit_price: string;
    applicable_taxes?: {tax: string | number; is_inclusive: boolean}[];
  }[];
  fixed_asset_line_items?: {
    line_item?: string;
    asset_category: string;
    quantity: number;
    unit_price: string;
    applicable_taxes?: {tax: string | number; is_inclusive: boolean}[];
  }[];
  other_expenses?: {
    expense_name: string;
    amount: string;
    account_to_record_expense: string;
    applicable_taxes?: {tax: string | number; is_inclusive: boolean}[];
  }[];
  exchange_rate?: IExchangeRateInput | null;
}

// --- Vendor Payment Types ---
export interface IVendorPayment {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  reference_code: string;
  payment_type: "prepayment" | "bill_payment";
  internal_payment_reference: string;
  vendor: IVendor;
  bill?: IVendorBill | null;
  receipt_date: string;
  payment_date: string;
  amount: string;
  settlement_amount: string;
  total_amount: string;
  currency: Currency;
  settlement_currency: Currency;
  payment_exchange_rate?: {
    source: "base_currency" | "document_snapshot";
    one_side: {currency: Currency; value: string};
    other_side: {currency: Currency; value: string};
    canonical_rate: string;
  } | null;
  settlement_exchange_rate?: {
    source: "same_currency" | "document_snapshot";
    one_side: {currency: Currency; value: string};
    other_side: {currency: Currency; value: string};
    canonical_rate: string;
  } | null;
  created_at: string;
  updated_at: string;
  requisition?: IRequisitionListItem | null;
  general_journal_items?: IJournalEntriesData;
  cash_requisition?: {
    id: number;
    base_uuid: string;
    requisition_code: string;
  };
  request_requisition?: {
    id: number;
    base_uuid: string;
    requisition_code: string;
  };
  payment_status: string;
  description?: string;
  cash_account?: {
    base_uuid: string;
    reference_code: string;
    account_name: string;
    account_balance: string;
    currency: Currency | null;
    description?: string;
    model: {
      id: number;
      model_name: string;
    };
  };
  created_by: {
    id: number;
    base_uuid: string;
    fullname: string;
    email: string;
  };
  updated_by: {
    id: number;
    base_uuid: string;
    fullname: string;
  };
  remaining_balance: string;
  amount_reconciled: string;
}
export interface IVendorPaymentFormData {
  vendor?: string;
  bill?: number | string;
  amount: string;
  payment_exchange_rate?: {
    one_side: {currency: number; value: string};
    other_side: {currency: number; value: string};
  } | null;
  settlement_exchange_rate?: {
    one_side: {currency: number; value: string};
    other_side: {currency: number; value: string};
  } | null;
  reference_code?: string;
  payment_date?: string;
  description?: string;
  content_type?: number | null;
  content_object_uuid?: string;
  cash_account_used: {
    content_type: number;
    content_object_uuid: string;
  };
}

// --- Vendor Credit Types ---
export interface IVendorCreditLineItem {
  id: number;
  base_uuid: string;
  bill_item?: IVendorBillLineItem;
  created_at: string;
  updated_at: string;
}

export interface IVendorCredit {
  id: number;
  base_uuid: string;
  bill?: IVendorBill;
  description: string;
  line_items: IVendorCreditLineItem[];
  created_at: string;
  updated_at: string;
}

export interface IVendorCreditFormData {
  bill: number;
  description: string;
}

export type IItemType = "saleable" | "non_saleable";

export interface IItem {
  id: number;
  base_uuid: string;
  is_deleted?: boolean;
  item_name: string;
  item_code?: string;
  item_type: IItemType;
  item_description: string;
  item_unit: string;
  item_selling_price: string;
  item_buying_price: string;
  account: IAccount;
  created_at: string;
  updated_at: string;
  item_category?: {
    id: number;
    base_uuid: string;
    name: string;
    description?: string;
  };
}

export interface IItemFormData {
  is_deleted?: boolean;
  item_name: string;
  item_type: IItemType;
  item_description: string;
  item_unit: string;
  item_selling_price: string;
  item_buying_price: string;
  account: number;
}
export interface IAssetCategoryUser {
  id: number;
  fullname: string;
  base_uuid: string;
  reference_code: string;
  email: string;
}

export interface IAssetCategoryAccount {
  id: number;
  reference_code: string | null;
  account_name: string;
  base_uuid: string;
}

export interface IAssetCategory {
  id: number;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  base_uuid: string;
  external_base_uuid?: string;
  reference_code?: string;
  original_data?: string;
  approval_status: "under_creation" | "under_update" | "under_deletion" | "active";
  approvals?: any;
  created_by: IAssetCategoryUser;
  updated_by: IAssetCategoryUser | null;
  category_description?: string;
  category_name: string;
  description?: string;
  is_capitalizable: boolean;
  is_depreciable: boolean;
  //useful_life: number | null;
  asset_type: "TANGIBLE" | "INTANGIBLE";
  depreciation_frequency: "DAILY" | "WEEKLY" | "MONTHLY" | "ANNUALLY" | null;
  asset_addition_type: "string";

  institution: number;
  asset_class: IAssetClass | null;
  //depreciation_method: IDepreciationMethod | number;
  fixed_asset_account: IAssetCategoryAccount | null;
  depreciation_expense_account: IAssetCategoryAccount | null;
  accumulated_depreciation_account: IAssetCategoryAccount | null;
}

export interface IAssetCategoryFormData {
  category_name: string;
  is_capitalizable: boolean;
  is_depreciable: boolean;
  //useful_life?: number;
  asset_type: "TANGIBLE" | "INTANGIBLE";
  depreciation_frequency: "DAILY" | "WEEKLY" | "MONTHLY" | "ANNUALLY";
  asset_class: string;
  //depreciation_method: number | string;
  fixed_asset_account: string;
  depreciation_expense_account: string;
  accumulated_depreciation_account: string;
  description?: string;
  reference_code?: string;
  external_base_uuid?: string;
  institution?: number;
}
export interface IAssetClass {
  id: number;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  deleted_at: string | null;
  is_active: boolean;
  approval_status: "under_creation" | "under_update" | "under_deletion" | "active";
  asset_class_name: string;
  description: string;
  default_depreciation_method: IDepreciationMethod;
  default_depreciation_percentage: number;
  default_useful_life: number;
  created_by?: {fullname: string; id: number};
  updated_by: {fullname: string; id: number};
  institution: number;
  approvals?: [];
  reference_code?: string;
}

export type IAssetClassFormData = Partial<
  Omit<
    Pick<
      IAssetClass,
      | "asset_class_name"
      | "description"
      | "default_depreciation_method"
      | "default_depreciation_percentage"
      | "default_useful_life"
      | "institution"
      | "is_active"
      | "reference_code"
    >,
    "default_depreciation_method"
  > & {
    default_depreciation_method: number | undefined;
  }
>;

export interface IAssetOpeningBalanceAccount {
  base_uuid: string;
  account_name: string;
}

export interface IFixedAssetItem extends IBaseApprovable {
  id: number;
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
  } | null;
  is_capitalized: boolean;
  depreciation_message: string;
  general_journal_items: {
    journal_items: {
      date: string;
      account: {
        id: number;
        base_uuid: string;
        name: string;
        reference_code: string | null;
      };
      journal_reference_code: string;
      description: string;
      transaction_entry_type: "debit" | "credit";
      amount: number;
      base_uuid: string;
    }[];
    total_credits: number;
    total_debits: number;
  };
  depreciation_history: IDepreciation[];
  current_book_value: string;
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
  asset_addition_type: "EXISTING_ASSET_NO_LIABILITY" | "EXISTING_ASSET_WITH_LIABILITY" | "VIA_BILL";
  asset_name: string;
  purchase_date: string | null;
  depreciation_start_date: string | null;
  purchase_price: string | null;
  salvage_value: string;
  opening_balance_account: IAssetOpeningBalanceAccount | null;
  current_value: string;
  accumulated_depreciation: string;
  disposal_date: string | null;
  disposal_value: string | null;
  are_initial_journal_entries_made: boolean;
  institution: IInstitution;
  category?: IAssetCategory;
  custodian: {
    id: number;
    roles: unknown[];
    branches: unknown[];
    last_login: string | null;
    is_superuser: boolean;
    is_deleted: boolean;
    created_at: string;
    description: string | null;
    updated_at: string;
    base_uuid: string;
    external_base_uuid: string | null;
    reference_code: string;
    deleted_at: string | null;
    internal_user_id: string;
    email: string;
    fullname: string;
    is_active: boolean;
    is_staff: boolean;
    is_email_verified: boolean;
    is_password_verified: boolean;
    user_type: string;
    permissions: unknown[];
    username: string;
    phone_number: string | null;
    gender: string;
    created_by: unknown | null;
    updated_by: unknown | null;
    groups: unknown[];
    user_permissions: unknown[];
  };
  asset_account: {
    id: number;
    reference_code: string | null;
    account_name: string;
    base_uuid: string;
    account_balance: number;
  } | null;
  expense_account: {
    id: number;
    reference_code: string | null;
    account_name: string;
    base_uuid: string;
    account_balance: number;
  } | null;
  accumulated_expense_account: {
    id: number;
    reference_code: string | null;
    account_name: string;
    base_uuid: string;
    account_balance: number;
  } | null;
  useful_life: string | null;
  asset_type: "TANGIBLE" | "INTANGIBLE";
  requisition?: {
    base_uuid: string;
    reference_code: string;
    total_amount: number;
  } | null;
}
export interface IFixedAssetItemFormData {
  asset_name: string;
  //asset_addition_type: "EXISTING_ASSET_NO_LIABILITY" | "EXISTING_ASSET_WITH_LIABILITY" | "VIA_BILL";
  purchase_date?: string | null;
  depreciation_start_date?: string | null;
  acquisition_date?: string | null;
  category: number | string;
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  purchase_price?: string | null;
  salvage_value?: string;
  opening_balance_account?: string | null;
  useful_life?: string | null;
  disposal_date?: string;
  disposal_value?: string;
  institution?: number;
  custodian?: number | null;
  requisition?: string | number;
}
export interface IDepreciationMethod {
  id: number;
  method_name: string;
  method_code: string;
  method_description: string;
  created_at: string;
}

export interface IDepreciationItem {
  id: number;
  fixed_asset_item: IFixedAssetItem;
  depreciation_method: IDepreciationMethod;
  salvage_value: number;
  useful_life: number;
  total_cost: number;
  total_estimated_unites: number;
  unites_produced_period: string;
  macrs_recovery_period: string;
  depreciation_period: string;
  book_value_before: number;
  sum_of_years_digits: number;
  created_at: string;
}

export interface IDepreciationSchedule {
  id: number;
  depreciation_item: IDepreciationItem;
  year: {id: string}; // 'year_id (FK)' not resolved, minimal object assumed
  transaction: ITransaction;
  depreciation_amount_before: number;
  acc_depreciation: number;
  created_at: string;
}

export interface IQuote {
  id: number;
  customer: ICustomer;
  description: string;
  issue_date: string;
  expiry_date: string;
  due_date: string;
  total_amount: number;
  created_at: string;
}

export interface ISimpleInvoice {
  id: number;
  customer: ICustomer;
  transaction: ITransaction;
  description: string;
  issue_date: string;
  due_date: string;
  total_amount: string;
  created_at: string;
}

export interface IPaymentReceived {
  id: number;
  invoice: ISimpleInvoice;
  receipt_date: string;
  payment_mode: string;
  total_amount: number;
  created_at: string;
}

export interface ISalesReceipt {
  id: number;
  customer: ICustomer;
  transaction: ITransaction;
  receipt_date: string;
  payment_mode: string;
  created_at: string;
}

// Requisition Types
// export interface IRequisitionType {
//   id: number;
//   name: string;
//   base_uuid: string;
//   reference_code?: string;
//   description?: string;
//   institution: IUserInstitution;
//   kind: "cash" | "payment" | "item";
//   is_active: boolean;
//   is_allowed_to_all_users: boolean;
//   has_fixed_amount: boolean;
//   fixed_amount: number;
//   is_subjective_to_taxes: boolean;
//   tax_application_mode: TaxApplicationMode;
//   taxes_to_apply?: ITaxType[];
//   allowed_roles: Role[];
//   allowed_users: IUser[];
//   default_spending_account?: IAccount;
//   default_expense_account?: IAccount;
//   cash_account_used?: {
//     base_uuid: string;
//     reference_code: string;
//     account_name: string;
//     account_balance: string;
//     currency: string | null;
//     description: string;
//     model: {id: number; model_name: string};
//     bank_name: string | null;
//   };
//   approvals: any[];
//   created_at: string;
//   updated_at: string;
//   deleted_at: string | null;
//   created_by: IUser | null;
//   updated_by: IUser | null;
//   is_deleted: boolean;
//   content_type: number | null;
//   object_uuid: string | null;
//   original_data: any | null;
// }

export type RequisitionAttachmentLevel = "AT_REQUEST" | "AT_PAYMENT" | "AFTER_PAYMENT";

export interface IRequisitionType {
  id: number;
  base_uuid: string;
  name: string;
  normalized_name: string;
  reference_code?: string;
  description?: string | null;
  credit_account: IAccount | null;
  debit_account: IAccount | null;
  cash_account?: IAccount | null;
  is_active: boolean;
  is_allowed_to_all_users: boolean;
  is_subjective_to_taxes: boolean;
  has_fixed_amount: boolean;
  fixed_amount?: string | null;
  cash_account_used?: any | null;
  allowed_users?: any[];
  allowed_branches?: any[];
  model_content_type_id?: number;
  taxes_that_apply?: any[];
  line_items?: any[];
  schedule_control?:
    | (IScheduleControl & {
        id?: number;
        base_uuid?: string;
        requisition_type?: number;
        reminder_time?: string | null;
      })
    | null;
  approval_levels_detail?: any[];
  approvals?: any[];
  approval_status?: ApprovableEntityStatus;
  allow_decline_to_continue?: boolean;
  required_attachment_levels: RequisitionAttachmentLevel[];
}

export interface IRequisitionItem {
  id: number;
  requisition: number;
  base_uuid: string;
  requisition_item_name: string;
  quantity: number;
  unit_price: string;
  created_at: string;
  updated_at: string;
  gross_amount?: number;
  net_amount?: number;
  tax_breakdowns?: ITaxType[];
  extra_data?: {
    others?: {
      net_salary: string;
      total_gross: string;
      basic_salary: string;
      other_deductions: string;
      other_taxable_allowances: string;
      other_untaxable_allowances: string;
    }[];
    employee_name?: string;
    taxable_amount?: string;
  };
}

export interface IMarkRequisitionAsPaidPayload {
  cash_account: {
    content_type: number;
    content_object_uuid: string;
  };
  additional_attachments?: {
    name: string;
    document: FileEntry;
  }[];
  description?: string;
  external_base_uuid?: string;
  reference_code?: string;
  amount_paid: string;
  payment_exchange_rate?: {
    one_side: {currency: number; value: string};
    other_side: {currency: number; value: string};
  } | null;
  settlement_exchange_rate?: {
    one_side: {currency: number; value: string};
    other_side: {currency: number; value: string};
  } | null;
  payment_date: string;
  beneficiary?: string;
}

export interface IRequisitionListItem {
  base_uuid: string;
  reference_code: string;
  currency: {
    id: number;
    code: string;
    name: string;
    symbol: string;
  };

  branch: string;
  requisition_type: string;
  requested_by: {
    base_uuid: string;
    fullname: string;
    email: string;
    profile_photo_base64: string | null;
  } | null;
  total_payable?: string | null;
  created_at: string;
  status: "pending" | "rejected" | "approved";
  allow_changes?: boolean;
  payment_status?: "unpaid" | "partially_paid" | "fully_paid";
  total_approval_levels?: number;
  finished_approval_levels?: number;
  current_approval_level?: {
    base_uuid: string;
    level: number;
    name: string | null;
    category: {
      base_uuid: string;
      name: string;
      level: number;
    } | null;
  } | null;
}

export interface IRequisition {
  reference_code: string;
  id: number;
  base_uuid: string;
  allow_changes?: boolean;
  allow_line_item_changes?: boolean;
  allow_line_item_add_delete?: boolean;
  external_base_uuid?: string | null;
  requisition_type: {
    id: number;
    base_uuid: string;
    name: string;
    reference_code: string;
    description?: string | null;
    credit_account?: string | null;
    debit_account?: string | null;
    cash_account?: string | null;
    is_subjective_to_taxes?: boolean;
    taxes_that_apply?: Array<{
      base_uuid: string;
      application_mode: "item" | "requisition";
      total_rate_value: string | null;
    }>;
    normalized_name: string;
  };

  branch: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string;
    branch_location?: string;
    branch_email?: string;
  } | null;
  currency?: IInstitutionSupportedCurrency | null;
  exchange_rate?:
    | (IExchangeRateRepresentation & {
        source?: "base_currency" | "document_snapshot";
      })
    | null;
  exchange_rate_status?: "base_currency" | "document_snapshot" | "missing";

  requested_by: {
    id?: number;
    base_uuid: string;
    reference_code?: string;
    profile?: {
      user?: {
        id?: number;
        fullname: string;
        email: string;
      };
    };
  } | null;

  total_tax_amount: string;
  net_amount: string;
  reason?: string;
  status: "pending" | "rejected" | "approved";
  description?: string;
  line_items: IRequisitionItem[];
  additional_attachments: IRequisitionAttachment[];
  created_at: string;
  updated_at: string;
  gross_amount: string;
  total_payable_amount?: string;
  total_paid_amount?: string;
  remaining_payable_amount?: string;
  payment_status?: "unpaid" | "partially_paid" | "fully_paid";
  tax_breakdowns: ITaxBreakdown[];
  is_project_based: boolean;
  project?: IProject;
  general_journal_items?: IJournalEntriesData;
  original_total_amount?: string;
  authorisation: Pick<
    IPublicRequisitionPreview,
    "created_at" | "description" | "requester" | "approval_categories"
  >;
}

export interface IPublicRequisitionPreview {
  institution: {
    institution_name: string;
    institution_legal_name: string | null;
    location: string | null;
    institution_email: string | null;
    first_phone_number: string | null;
    logo_base64: string | null;
  };

  branch: {
    branch_name: string;
    email: string | null;
    phone: string | null;
    reference_code: string | null;
  } | null;

  reference_code: string;
  base_uuid: string;

  req_type_name: string;

  status_text: string;
  status_class: "pending" | "approved" | "rejected";

  watermark_text: string;

  created_at: string;
  generated_at: string;

  payment_status: "unpaid" | "partially_paid" | "fully_paid";

  description: string | null;

  requester: {
    fullname: string;
    email: string;
    signature_base64: string | null;
  } | null;

  line_items: Array<{
    index: number;
    item_name: string;
    description: string | null;
    uom: string;
    quantity: number;

    unit_price: string;
    tax_amount: string;
    line_total: string;

    is_removed: boolean;
  }>;

  approval_categories: Array<{
    category_name: string;
    levels: Array<{
      level: number | string;

      action_name: string;
      workflow_status: string;

      task_status_class:
        | "approved"
        | "rejected"
        | "overridden"
        | "terminated"
        | "pending"
        | "not_started";

      task_status_label: string;

      actioned: boolean;
      is_last_actioned?: boolean;

      actor: null | {
        fullname: string;
        email: string;
        profile_photo_base64: string | null;
        status_class: string;
        status_label: string;
        date: string | null;
        comment: string | null;
        signature_base64: string | null;
      };

      pending_approvers: Array<{
        fullname: string;
        email: string;
        profile_photo_base64: string | null;
      }>;
    }>;
  }>;

  subtotal: string;
  total_tax: string | null;
  net_amount: string | null;
  gross_total: string;

  qr_base64: string;
}

export interface ITaxBreakdown {
  id: number;
  is_deleted: boolean;
  created_at: string;
  base_uuid: string;
  tax_method: "PERCENTAGE" | "PER_UNIT" | "FIXED_AMOUNT";
  tax_rate: string;
  tax_amount: string;
  institution_tax_amount?: string;
  created_by: number | null;
  updated_by: number | null;
  requisition: number;
  tax_type: ITaxType;
  tax: ITax;
  gross_amount?: number;
  net_amount?: number | string;
}

export type RequisitionKind = "cash" | "payment" | "item";
export interface IAllowedRole {
  role: string;
  are_all_users_in_role_allowed: boolean;
  allowed_users?: string[];
}

export interface IApprovalLevel {
  base_uuid?: string;
  category?: string;
  approvers?: string[];
  approver_users?: string[];
  overriders?: string[];
  overrider_users?: string[];
  reference_code?: string;
  description?: string;
  name?: string;
  is_locked?: boolean;
  approval_document?: number;
}

export interface InitiatorRoleEntry {
  role_id: number;
  role_uuid: string;
  role_name: string;
  are_all_users_in_role_allowed: boolean;
  selected_users: string[];
}

export interface IScheduleControl {
  frequency: "daily" | "weekly" | "monthly" | "yearly";
  max_count_per_period?: number;
  limit_scope?: "overall" | "per_branch";
  reminder_enabled?: boolean;
  reminder_time?: string;
}

export interface IRequisitionTaxEntry {
  tax: string;
  withhold_tax_amount: boolean;
}

export interface IRequisitionTypeLineItemBeneficiaryEntry {
  beneficiary: string;
}

export interface IRequisitionTypeLineItem {
  base_uuid?: string;
  item?: string;
  description?: string;
  unit_price: string;
  max_quantity?: number;
  should_unit_price_be_edited: boolean;
  price_change_direction?: "up" | "down" | "both" | null;
  allowable_price_change_threshold_in_percentage?: string | number | null;
  allow_unconfigured_beneficiaries: boolean;
  taxes_that_apply?: IRequisitionTaxEntry[];
  beneficiaries?: IRequisitionTypeLineItemBeneficiaryEntry[];
  _item?: {
    base_uuid: string;
    name: string;
    description?: string;
    unit_price?: string;
    reference_code?: string;
  };
  _taxes?: any[];
  _beneficiaries?: IRequisitionBeneficiary[];
}

export interface IApprovalDocumentCategory {
  id: number;
  base_uuid: string;
  reference_code: string;
  name: string;
  description: string;
  level: number;
}
export interface IRequisitionTypeFormData {
  name: string;
  description?: string;
  reference_code?: string;
  external_base_uuid?: string;
  is_allowed_to_all_users?: boolean;
  allowed_roles?: IAllowedRole[];
  allowed_users?: string[];
  allowed_branches?: string[];
  allowed_currencies?: string[];
  debit_account?: number;
  cash_account?: {
    content_type: number;
    content_object_uuid: string;
  };
  approval_levels?: IApprovalLevel[];
  schedule_control?: IScheduleControl;
  line_items?: IRequisitionTypeLineItem[];
  allow_decline_to_continue?: boolean;
  affect_inflight_approvals?: boolean;
  required_attachment_levels?: RequisitionAttachmentLevel[];
}

export interface IRequisitionGeneralStatistics {
  base_currency: Currency;
  total_requisitions: number;
  approved_requisitions: number;
  pending_requisitions: number;
  rejected_requisitions: number;
  paid_requisitions: number;
  unpaid_requisitions: number;
  approval_rate_percentage: number;
  rejection_rate_percentage: number;
  pending_rate_percentage: number;
  weekly_change_percentage: number;
  total_original_amount: string;
  total_tax_amount: string;
  total_gross_amount: string;
  total_paid_amount: string;
  total_unpaid_amount: string;
}

export interface IRequisitionDashboardSummary {
  awaiting_my_approvals: number;
  sent_back_approvals: number;
  incoming_approvals: number;
  outgoing_approvals: number;
}

export interface IRequisitionPayment {
  id: number;
  base_uuid: string;
  reference_code: string;
  requisition: {
    base_uuid: string;
    reference_code: string;
    requisition_type: {
      base_uuid: string;
      reference_code: string;
      name: string;
    };
  };
  amount_paid: string;
  settlement_amount: string;
  currency: Currency;
  settlement_currency: Currency;
  payment_exchange_rate: IExchangeRateRepresentation | null;
  settlement_exchange_rate: IExchangeRateRepresentation | null;
  payment_date: string;
  status: "pending" | "completed" | "failed";
  created_by: ICreatedByProfile | null;
  beneficiary: {
    base_uuid: string;
    reference_code: string;
    name: string;
  } | null;
  created_at: string;
  updated_at: string;
  at_payment_attachments: IRequisitionAttachment[];
  after_payment_attachments: IRequisitionAttachment[];
  model_content_type_id: number;
}

export interface IRequisitionApprovalActivity {
  id: number;
  action: "approved" | "rejected" | "sent_back" | "reset" | "overridden";
  actor: string;
  timestamp: string;
  comment: string | null;
  from_level: number | null;
  to_level: number | null;
  level: {
    name: string | null;
    category: string | null;
    sequence: number | null;
  };
  requisition: {
    base_uuid: string;
    reference_code: string | null;
    requisition_type_normalized_name: string | null;
  };
}

export type IRequisitionRecentActivityResponse = IPaginatedResponse<IRequisitionApprovalActivity>;

export interface IBudgetApprovalActivity {
  id: number;
  action: "approved" | "rejected" | "sent_back" | "reset" | "overridden";
  actor: string;
  timestamp: string;
  comment: string | null;
  from_level: number | null;
  to_level: number | null;
  level: {
    name: string | null;
    category: string | null;
    sequence: number | null;
  };
  object: {
    model: string;
    base_uuid: string;
    reference_code: string | null;
  };
}

export type IBudgetRecentActivityResponse = IPaginatedResponse<IBudgetApprovalActivity>;

export interface ICommonlyUsedRequisitionType {
  requisition_type_id: number;
  requisition_type_name: string;
  total_requisitions: number;
  approved_requisitions: number;
  pending_requisitions: number;
  rejected_requisitions: number;
  paid_requisitions: number;
  unpaid_requisitions: number;
  total_amount_spent: string;
  total_tax_amount: string;
  average_requisition_amount: string;
  requisition_type_base_uuid: string;
}

export type TaxApplicationMode = "item" | "requisition" | "";

export interface IRequisitionLineItem {
  quantity: number;
  unit_price: string;
  extra_data?: IRequisitionLineItemExtraData;
}

export interface IRequisitionTaxPreview {
  line_item: string;
  original_amount: string;
  net_amount: string;
  tax_amount: string;
  gross_amount: string;
  withheld_tax_amount: string;
  payable_amount: string;
  applied_taxes: {
    tax: string;
    tax_name: string;
    is_inclusive: boolean;
    is_withheld: boolean;
    tax_amount: string;
    institution_tax_amount: string;
    net_amount: string;
    gross_amount: string;
    withheld_tax_amount: string;
    payable_amount: string;
  }[];
}

export interface IRequisitionLineItemExtraData {
  employee_name?: string;
  taxable_amount?: string;
  others?: {
    basic_salary?: string;
    other_taxable_allowances?: string;
    other_untaxable_allowances?: string;
    other_deductions?: string;
    total_gross?: string;
    net_salary?: string;
  }[];
}

export interface IRequisitionItemFormData {
  item: string;
  quantity: number;
  unit_price: string;
  estimate_price?: string;
}

export type IRequisitionAttachmentInput = {
  name: string;
  document: File;
};

export type IRequisitionAttachmentPayload = {
  name: string;
  document: FileEntry;
};

export interface IApproverSelection {
  category: string;
  approver_users: string[];
}

export interface IRequisitionFormData {
  reference_code?: string;
  description?: string;
  requested_by?: string | number;
  requisition_type: string;
  branch?: string;
  currency?: string;
  exchange_rate?: IExchangeRateInput | null;
  additional_attachments?: IRequisitionAttachmentInput[];
  line_items?: IRequisitionLineItem[];
  original_total_amount?: string;
  object_id?: number;
  content_type?: number;
}

export type IRequisitionPayload = Omit<IRequisitionFormData, "additional_attachments"> & {
  additional_attachments?: IRequisitionAttachmentPayload[];
};

export const buildRequisitionPayload = async (
  input: IRequisitionFormData,
): Promise<IRequisitionPayload> => {
  const {additional_attachments, ...rest} = input;

  const convertedAttachments: IRequisitionAttachmentPayload[] | undefined =
    additional_attachments && additional_attachments.length > 0
      ? await Promise.all(
          additional_attachments.map(async ({name, document}) => ({
            name,
            document: await toFileEntry(document),
          })),
        )
      : undefined;

  return {
    ...rest,
    ...(convertedAttachments !== undefined && {additional_attachments: convertedAttachments}),
  };
};

export interface IRequisitionAttachment {
  base_uuid: string;
  id: number;
  name: string;
  document: string;
  created_at: string;
  updated_at: string;
  document_size: number;
  document_type: string;
  level: RequisitionAttachmentLevel;
  payment: string | null;
}

export interface IBalanceSheet {
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  check: boolean;
  detailed: {
    assets: Array<{
      category: string;
      total: string;
      accounts: Array<{account_name: string; balance: string}>;
    }>;
    liabilities: Array<{
      category: string;
      total: string;
      accounts: Array<{account_name: string; balance: string}>;
    }>;
    equity: Array<{
      category: string;
      total: string;
      accounts: Array<{account_name: string; balance: string}>;
    }>;
  };
}

export interface IIncomeStatement {
  date_generated: string;
  revenues: {
    items: Record<string, number>;
    total: number;
  };
  operating_expenses: {
    items: Record<string, number>;
    total: number;
  };
  net_income: number;
}

export interface ITrialBalance {
  report_date: string;
  accounts: Array<{
    account_name: string;
    debit: number;
    credit: number;
  }>;
  grand_total_debits: number;
  grand_total_credits: number;
  is_balanced: boolean;
}

// Placeholder interface
export interface IPaymentTerm extends IBaseApprovable {
  id: number;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  created_by?: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  } | null;
  updated_by?: {
    id: number;
    fullname: string;
    base_uuid: string;
    reference_code: string;
    email: string;
  } | null;
  base_uuid: string;
  term_name: string;
  days_until_due: number;
  institution: number;
  approvals?: Approval[];
  approval_status?: ApprovableEntityStatus;
  reference_code?: string;
  description?: string;
}

export interface IPaymentTermFormData {
  term_name: string;
  days_until_due: number | null;
  reference_code?: string;
  description?: string;
}

export interface ISalePersonFormData {
  name: string;
  email: string;
  profile_photo?: File | string | null;
  address?: string;
  contact?: string;
}

export interface ISalesPerson {
  id: string;
  base_uuid: string;
  name: string;
  email: string;
  created_by: IUser;
  created_at: string;
  updated_at: string;
  is_active?: boolean;
  contact?: string;
  profile_photo?: string | null;
  address?: string | null;
  approval_status?: string;
}

export interface IItemUnitOfMeasure {
  id: number;
  base_uuid: string;
  institution: IUserInstitution;
  unit_name: string;
  unit_abbreviation: string;
  description?: string;
  is_deleted?: boolean;
  created_at: string;
  updated_at?: string;
  created_by?: IUser;
}

export interface IInventoryItemUnitOfMeasure {
  id: number;
  base_uuid: string;
  external_base_uuid?: string | null;
  reference_code?: string | null;
  inventory_item: string;
  unit_of_measure: {
    id: number;
    base_uuid: string;
    unit_name: string;
    unit_abbreviation: string;
    description?: string | null;
    institution?: number;
  };
  is_base_unit_of_measure: boolean;
  is_deleted?: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
  conversion_factor?: string;
  selling_price?: string;
  cost_price?: string;
  margin?: string;
  markup?: string;
  other_quantity?: string | null;
  other_uom?: number | null;
  created_by?: IUser | null;
  updated_by?: IUser | null;
  description?: string | null;
  approval_status?: string;
  unit_name?: string;
  unit_abbreviation?: string;
}

export interface IItemUnitOfMeasureFormData {
  unit_name: string;
  unit_abbreviation: string;
  description?: string;
}

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

export interface ICurrencyFormData {
  id: number;
  code: string;
  name: string;
  symbol: string;
}

export interface CurrenciesResponse {
  currencies: Currency[];
}

export interface IFeature {
  label: string;
  keywords: string[];
  url: string;
}

export interface ICommissionTransaction {
  code: string;
  type: "earned" | "redeemed";
  percentage: number;
  amount: number;
  date: string;
}

export interface ISalesPersonCommission {
  id: number;
  approvals: any[];
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  deleted_at: string | null;
  is_active: boolean;
  approval_status: string;
  amount: string;
  new_commission: string;
  old_commission: string;
  commission_type: string;
  created_by: number | null;
  updated_by: number | null;
  sales_person: number;
}

export interface ITaxType {
  id: number;
  institution: number;
  tax_name: string;
  description: string | null;
  is_active: boolean;
  tax_account: IAccount;
  base_uuid: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  approval_status: string;
  approvals: Approval[];
  tax_application_count: string;
  tax_type_rules: ITaxRule[];
  tax_method: "PERCENTAGE" | "PER_UNIT" | "FIXED_AMOUNT";
  tax: number;
  tax_amount: string;
}

export interface ITaxTypeFormData {
  tax_name: string;
  description: string;
  tax_account: number;
  tax_rules: ITaxRule[];
}

export interface ITaxRule {
  id: number;
  base_uuid?: string;
  tax: number;
  value_min: string | null; // Required field in backend
  value_max: string | null;
  rate_type: "percentage" | "fixed";
  rate_value: string;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
  is_deleted?: boolean;
  is_active?: boolean;
  approval_status?: string;
  created_by?: number | null;
  updated_by?: number | null;
  approvals?: Approval[];
}

export interface ITaxRule {
  id: number;
  tax_type: ITaxType | null;
  tax_method: "PERCENTAGE" | "PER_UNIT" | "FIXED_AMOUNT";
  tax_rate: string;
  created_at?: string;
  updated_at?: string;
  base_uuid?: string;
  deleted_at?: string | null;
  is_active?: boolean;
  value_min: string | null;
  value_max: string | null;
}

export interface ITaxRuleFormData {
  tax: number; // Required field in backend
  value_min: string; // Required field in backend
  value_max: string | null;
  rate_type: "percentage" | "fixed";
  rate_value: string;
}

// Tax Dependency interfaces
export interface ITaxDependency {
  dependency_base_uuid: string;
  independent_taxes: IdependencyContent[];
  computation_mode: "combined" | "sequential";
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  is_deleted: boolean;
  created_by: number | null;
  updated_by: number | null;
}

export interface IdependencyContent {
  id: number;
  name: string;
  base_uuid: string;
}

export interface ITaxDependencyFormData {
  dependant_tax: number;
  independent_taxes: [
    {
      independent_taxes: number[];
    },
  ];
}

// Tax Schedule interfaces
export interface ITaxSchedule {
  id: number;
  base_uuid: string;
  tax: ITax;
  frequency: "monthly" | "quarterly" | "annually" | "biannually" | "one_time";
  tax_body_filing_period: string;
  tax_body_payment_period: string;
  institution_filing_period: string;
  tax_body_filing_day_start: number | null;
  tax_body_filing_day_end: number | null;
  tax_body_payment_day_start: number | null;
  tax_body_payment_day_end: number | null;
  institution_filing_day_start: number | null;
  institution_filing_day_end: number | null;
  institution_payment_deadline_day: number | null;
  additional_notes: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  is_deleted: boolean;
  is_active: boolean;
  approval_status: string;
  created_by: number | null;
  updated_by: number | null;
}

export interface ITaxScheduleFormData {
  frequency: "monthly" | "quarterly" | "annually" | "biannually" | "one_time";
  tax_body_filing_day_start: number | null;
  tax_body_filing_day_end: number | null;
  tax_body_payment_day_start: number | null;
  tax_body_payment_day_end: number | null;
  institution_filing_day_start: number | null;
  institution_filing_day_end: number | null;
  institution_payment_deadline_day: number | null;
  additional_notes: string | null;
}

// New Tax interfaces matching backend taxation models exactly
export interface ITax {
  id: number;
  base_uuid: string;
  institution: number;
  model_content_type_id: number;
  tax_name: string;
  description: string | null;
  tax_account?: IAccount | null;
  rate_type: "percentage" | "fixed";
  institution_contribution: string | null;
  liable_party_contribution: string | null;
  total_rate_value: string | null;
  has_rules: boolean;
  rule_on_tax: ITaxRule[];
  rule_application_type: "progressive" | "non_progressive" | null;
  is_inclusive: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  tax_accounts?: ITaxAccountRead[];
  is_deleted: boolean;
  is_active: boolean;
  approval_status: string;
  created_by: IUser | string;
  updated_by: IUser | string;
  approvals: Approval[];
  depends_on: ITaxDependency[];
  is_statutory_obligation: boolean;
  tax_schedule: ITaxSchedule | null;
  reference_code: string;
  is_applicable_to_invoice_or_bill?: boolean;
  applicability: "INVOICE_ONLY" | "BILL_ONLY" | "BOTH" | null;
}

export interface ITaxAccountRead {
  id?: number;
  base_uuid?: string;
  account: IAccount | string;
  tax_account?: {base_uuid: string; account_name?: string} | string;
  currency?: {id?: number; code?: string; name?: string; symbol?: string} | null;
}

export interface ITaxSummary {
  input: string;
  output: string;
  net: string;
  total_records: number;
}

export interface ITaxAccountPayload {
  account: string;
}

export interface ITaxFormData {
  reference_code?: string;
  tax_name: string;
  description: string;
  tax_account?: string;
  tax_accounts?: ITaxAccountPayload[];
  rate_type: "percentage" | "fixed";
  is_institution_contribution?: boolean;
  institution_contribution: string | null;
  liable_party_contribution: string | null;
  has_rules: boolean;
  rule_application_type: "progressive" | "non_progressive" | null;
  is_inclusive: boolean;
  rules: ITaxRuleFormDataNew[];
  is_statutory_obligation: boolean;
  is_applicable_to_invoice_or_bill?: boolean;
  applicability: "INVOICE_ONLY" | "BILL_ONLY" | "BOTH" | null;
}

export interface ITaxRuleFormDataNew {
  value_min: string; // Required field in backend
  value_max: string | null;
  rate_type: "percentage" | "fixed";
  rate_value: string;
}

export interface IBank {
  id: number;
  base_uuid: string;
  reference_code: string;
  account_name: string;
  account_balance: string;
  account_number: string;
  bank_name: string;
  account_type: string;
  approval_status?: string;
  bank_identifier_code?: string;
  relationship_officer?: string;
  relationship_officer_contact?: string;
  description?: string;
  institution: number;
  currency: {
    id: number;
    base_uuid: string;
    code?: string;
    name?: string;
  } | null;
  charts_of_accounts_reference?: {
    id: number;
    account_name: string;
    base_uuid: string;
  };
  branch?: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string;
  };
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  general_journal_items?: IJournalEntriesData;
}
export interface IBankFormData {
  account_name: string;
  auto_create_ledger_account?: boolean;
  currency?: string;
  account_number: string;
  bank_name: string;
  bank_identifier_code: string;
  description?: string;
  relationship_officer?: string;
  relationship_officer_contact?: string;
  institution?: number;
  account_balance?: string;
  charts_of_accounts_reference?: number | string;
  confirm_financial_mapping_change?: boolean;
  reference_code?: string;
  branch?: string;
}

export type MovementType = "BRANCH_TO_BRANCH" | "MAIN_TO_BRANCH";

export type StockMovementStatus = "ALLOCATED" | "CANCELLED" | "PENDING";

export interface IStockMovementListItem {
  id: number;
  base_uuid: string;
  reference_code: string;
  movement_type: MovementType;
  movement_date: string;
  status: StockMovementStatus;
  branch_from_name: string;
  branch_to_name: string;
  item_count: number;
  created_at: string;
}

export interface IBranchAllocation extends IBaseApprovable {
  id: number;
  reference_code: string;
  base_uuid: string;
  branch: number;
  branch_to?: {
    id: number;
    base_uuid: string;
    reference_code: string;
    branch_name: string;
    branch_location?: string;
    branch_email?: string;
    branch_phone_number?: string;
    branch_type?: string;
    status?: string;
  };
  items?: IAllocatedItem[];
  alloc_status: string;
  allocation_date: string;
  is_stock_moved: boolean;
  approval_status?: ApprovableEntityStatus;
  status?: string;
  created_at: string;
  updated_at: string;
  created_by?: {
    id: number;
    fullname: string;
    email: string;
  };
  updated_by?: {
    id: number;
    fullname: string;
    email: string;
  };
  approvals?: any[];
}

export interface IAllocatedItem {
  item: IItem;
  quantity: string | number;
  unit_of_measure?: {
    id: number;
    base_uuid: string;
    unit_of_measure?: {
      id: number;
      base_uuid: string;
      unit_name: string;
      unit_abbreviation?: string;
    };
  };
}

export interface IBranchAllocationFormData {
  allocation_date: string;
  branch_to: string;
  items: IProductsPayload[];
  description?: string;
  reference_code?: string;
}

export interface IProductsPayload {
  item: string;
  quantity: number;
  unit_of_measure: string;
}

export interface IBranchInventoryItemUnitOfMeasure extends Omit<
  IInventoryItemUnitOfMeasure,
  "inventory_item"
> {
  branch_inventory_item: string;
}

export interface IBranchInventoryItemUOMPayload {
  unit_of_measure: string;
  selling_price: string;
}

export interface IBranchInventoryItemUpdatePayload {
  selling_price?: string;
  price_changes?: IBranchInventoryItemUOMPayload[];
  can_be_returned?: boolean;
}

export interface IBranchInventoryItem extends IBaseApprovable {
  id: number;
  reference_code?: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  deleted_at?: string;
  is_active: boolean;
  can_be_returned: boolean;
  quantity: number;
  selling_price: string;
  created_by?: string;
  updated_by?: string;
  branch: {
    base_uuid: string;
    branch_name: string;
    allow_sales_out_of_stock?: boolean;
  };
  inventory_item: IInventoryItem;
  branch_inventory_item: {
    item_name: string;
    item_code: string;
    item_category: IItemCategory;
    item_type: string;
    unit_of_measure: IItemUnitOfMeasure;
  };
  branch_inventory_item_units_of_measure?: {
    unit_of_measure: IItemUnitOfMeasure;
    conversion_factor: string;
    selling_price: string;
    is_base_unit_of_measure: boolean;
    base_uuid: string;
  }[];
}

export interface IReportField {
  name: string;
  label: string;
}
export interface IReport {
  model: string;
  app_label: string;
  fields: IReportField[];
  filters: IReportFilter[];
}

export interface IReportFilterChoice {
  value: string;
  label: string;
}

export interface IReportFilter {
  name: string;
  type: string;
  required: boolean;
  read_only: boolean;
  label: string;
  choices?: IReportFilterChoice[];
}

export interface IReportDownloadData {
  model: string;
  output_format: "pdf" | "excel";
  heading?: string;
  filters?: Record<string, any>;
  fields?: string[];
}

export interface Role extends IBaseApprovable {}
export interface Branch extends IBaseApprovable {}
export interface IUser extends IBaseApprovable {}

// export interface IPaginatedResponse<T> extends IBaseApprovable {}
export interface ICustomApiRequestError extends IBaseApprovable {}
export interface IUserInstitution extends IBaseApprovable {}
export interface Role extends IBaseApprovable {}
export interface Branch extends IBaseApprovable {}
export interface IUser extends IBaseApprovable {}
export interface UserProfile extends IBaseApprovable {}
export interface Permission extends IBaseApprovable {}
//export interface StoredColorData extends IBaseApprovable {}
export interface IPermission extends IBaseApprovable {}
export interface IAccountGroup extends IBaseApprovable {}
export interface IAccountGroupType extends IBaseApprovable {}
export interface IAccountGroupSubType extends IBaseApprovable {
  group_sub_type_name: string;
  group_sub_type_code: string;
  group_sub_type_description?: string;
}
export interface IDefaultAccount extends IBaseApprovable {}
export interface IAccount extends IBaseApprovable {}
export interface IFiscalYear extends IBaseApprovable {}
export interface ITransaction extends IBaseApprovable {}
export interface ITransactionEntry extends IBaseApprovable {}
export interface ITransactionType extends IBaseApprovable {}
export interface IItemCategory extends IBaseApprovable {}
export interface IInventoryItem extends IBaseApprovable {}
export interface IVendor extends IBaseApprovable {}
export interface IPurchaseOrder extends IBaseApprovable {}
export interface IPurchaseOrderLineItem extends IBaseApprovable {}
export interface IBill extends IBaseApprovable {}
export interface ICustomer extends IBaseApprovable {}
export interface IQuotationLineItem extends IBaseApprovable {}
export interface IQuotation extends IBaseApprovable {}
export interface IInvoiceLineItem extends IBaseApprovable {}
export interface IInvoice extends IBaseApprovable {}
export interface IVendorPurchaseOrderLineItem extends IBaseApprovable {}
export interface IVendorPurchaseOrder extends IBaseApprovable {}
export interface IVendorBillLineItem extends IBaseApprovable {}
export interface IVendorBill extends IBaseApprovable {}
export interface IVendorPayment extends IBaseApprovable {}
export interface IVendorCreditLineItem extends IBaseApprovable {}
export interface IVendorCredit extends IBaseApprovable {}
export interface IItem extends IBaseApprovable {}
export interface IDepreciationMethod extends IBaseApprovable {}

export interface IBalanceAdjustment {
  id: number;
  reference_code: string;
  customer: ICustomer;
  adjustment_date: string;
  amount: number;
  amount_before_adjustment: number;
  amount_after_adjustment: number;
  reason: string;
  balance_adjusted: "OUTSTANDING_RECEIVABLE_BALANCE" | "DEPOSIT_BALANCE";
}

export interface ICreditNoteLineItem {
  id: number;
  base_uuid: string;
  reference_code: string;
  type: "ITEM_RETURN" | "PRICE_ADJUSTMENT" | "GENERAL_ADJUSTMENT" | "REPLACEMENT";
  description: string | null;
  quantity: number | null;
  unit_price: string | null;
  amount_to_deduct: string;
  amount_on_general_adjustment: string | null;
  invoice_line_item: string | null;
  bill_line_item: string | null;
  account_to_credit: number | null;
  account_to_debit: number | null;
  line_item: {
    id: number;
    item_name: string;
    item_code: string;
    base_uuid: string;
  } | null;
  credit_debit_note: number;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface ICreditNote {
  reference_code: string;
  type: string;
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  bill?: IVendorBill;
  invoice?: IInvoice;
  amount: number;
  issue_date: string;
  description: string;
  price_effects: [
    {
      amount_after: number;
      amount_before: number;
    },
  ];
  created_at: string;
  updated_at: string;
  status: string;
  general_journal_items?: IJournalEntriesData;
  line_items?: ICreditNoteLineItem[];
}

export interface ICreditNoteLineItemFormData {
  unit_of_measure: string;
  invoice_line_item: string;
  quantity?: number;
  new_price?: string;
  line_type: "REPLACEMENT" | "PRICE_ADJUSTMENT" | "ITEM_RETURN";
}

export interface ICreditNoteFormData {
  branch?: number;
  invoice?: string;
  bill?: string;
  coa_cash_account?: string | null;
  amount?: number;
  issue_date: string;
  description?: string;
  reference_code?: string;
  line_items?: ICreditNoteLineItemFormData[];
}

export interface IDebitNote {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  reference_code?: string;
  bill?: IVendorBill;
  invoice?: IInvoice;
  amount: number;
  general_journal_items?: IJournalEntriesData;
  issue_date: string;
  description: string;
  price_effects: [
    {
      amount_after: number;
      amount_before: number;
    },
  ];
  created_at: string;
  updated_at: string;
  status: string;
  total_amount: string;
}

export interface IDebitNoteFormData {
  invoice?: number;
  bill?: string;
  amount: number;
  issue_date: string;
  description?: string;
  branch?: number;
}

export interface ICashBookRequisitionFormData {
  amount: number;
  cashbook: string | number;
  description?: string;
  reference_code?: string;
  should_auto_create_requisition?: boolean;
  requisition?: string | null;
}

export interface ICashBookRequisition {
  id: number;
  base_uuid: string;
  amount: number;
  cashbook: ICashbook;
  description?: string;
  created_at: string;
  updated_at: string;
  should_auto_create_requisition: boolean;
  request_status: "PENDING" | "RESPONDED_TO" | "CANCELED";
  requisition: {
    id: number;
    base_uuid: string;
    reference_code: string;
    status: string;
    gross_amount: string;
  } | null;
  custodian_name: string;
  reference_code: string;
}

export interface ICashBookCredit {
  id: number;
  base_uuid: string;
  request?: ICashBookRequisition;
  requisition?:
    | {id: number; base_uuid: string; reference_code: string; gross_amount: string}
    | number
    | null;
  cashbook?: {
    id: number;
    base_uuid?: string;
    reference_code?: string;
    custodian_name?: string;
  };
  amount: number;
  additional_notes?: string;
  description?: string;
  reference_code: string;
  topup_status?: string;
  is_cashbook_transaction_done?: boolean;
  created_at: string;
  updated_at?: string;
  approval_status: ApprovableEntityStatus;
  approvals?: Approval[];
  imprest?: any;
}

export interface ICashBookCreditFormData {
  amount: number;
  cashbook?: string | number;
  requisition?: string | null;
  description?: string;
  reference_code?: string;
  request?: number;
  additional_notes?: string;
}

export interface IDepreciationItemFormData {
  asset: string;
  depreciation_amount: number;
  reference_code?: string;
  entry_date: string;
  description?: string;
}

export interface IDepreciation extends IBaseApprovable {
  are_initial_journal_entries_made: boolean;
  asset: IFixedAssetItem | number;
  fiscal_year: IFiscalYear | string;
  depreciation_amount: number;
  depreciation_date: string;
  description?: string;
  reference_code?: string;
  period_end: string;
  period_start: string;
  book_value?: string;
  accumulated_depreciation?: string;
  created_by: {
    id: number;
    fullname: number;
    base_uuid: string;
    reference_code: string;
    email: string;
  };
  entry_date: string;
  period_key: string;
  general_journal_items?: IJournalEntriesData;
}

export interface IAssetDisposalType {
  id: number;
  disposal_name: string;
  disposal_code: string;
  disposal_description: string;
  base_uuid: string;
}

export interface IAssetDisposal extends IBaseApprovable {
  loss_gain_coa?: number | null;
  loss_gain_account?: Pick<IAccount, "id" | "account_name" | "reference_code"> | null;
  asset: IFixedAssetItem;
  disposal_date: string;
  disposal_reason?: string;
  proceeds: string;
  gain_or_loss: string;
  is_gain: boolean;
  disposal_type: IAssetDisposalType | number;
  created_at: string;
  updated_at: string;
  general_journal_items?: IJournalEntriesData;
  reference_code: string;
  description?: string;
  trade_in_asset?: {
    asset_name: string;
    asset_category: IAssetCategory;
    serial_number?: string | null;
    additional_payment: number;
    cash_received: number;
    new_asset_value: number;
    depreciation_start_date?: string | null;
  };
  cash_account?: {
    base_uuid: string;
    reference_code: string;
    account_name: string;
    account_balance: string;
    currency: string | null;
    description: string;
    model: {
      id: number;
      model_name: string;
    };
    bank_name: string | null;
  };
  are_initial_journal_entries_made: boolean;
  created_by?: number | null;
  updated_by?: number | null;
}

export interface IAssetDisposalFormData {
  loss_gain_coa?: number | null;
  asset: string;
  disposal_date: string;
  disposal_type: number;
  proceeds?: number;
  description?: string;
  reference_code?: string;
  external_base_uuid?: string;
  trade_in?: {
    asset_name: string;
    asset_category: string;
    serial_number?: string | null;
    additional_payment?: number;
    cash_received?: number;
    new_asset_value?: number;
    depreciation_start_date?: string | null;
  };
  cash_account_used?: {
    content_type: number;
    content_object_uuid: string;
  };
}

export interface IBusinessDocument {
  id: number;
  name: string;
  attachment: string | null;
  base_uuid: string;
  reference_code?: string;

  institution: IUserInstitution | null;

  branch: Branch | null;

  issue_date: string | null;
  expiry_date: string | null;

  category: IBusinessDocumentCategory | null;
}

export interface IBusinessDocumentFormData {
  name?: string;
  attachment?: File | null;
  branch?: number | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  category?: number | null;
  reference_code?: string;
}

export interface IBusinessDocumentCategory {
  id: number;
  name?: string;
  category_name?: string;
  category_code: string;
  category_description: string;
  description?: string;
  base_uuid?: string;
}

export interface IBankStatementFormData {
  name: string;
  date_to: string;
  date_from: string;
  issue_date: string;
  bank: number;
  bank_statement_transactions?: IBankStatementTransactionFormData[];
}

export interface IBankStatement extends IBaseApprovable {
  base_uuid: string;
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  issue_date: string;
  date_to: string;
  date_from: string;
  bank_name: string;
  bank: {
    id: number;
    base_uuid: string;
  };
}

export interface IBankStatementTransactionFormData {
  bank_statement?: string;
  amount: string;
  transaction_code: string;
  date: string;
  notes: string;
}

export interface IBankStatementTransaction extends IBaseApprovable {
  id: number;
  base_uuid: string;
  transaction_code: string;
  amount: string;
  notes: string;
  date: string;
  statement: IBankStatement;
  created_at: string;
  updated_at: string;
}

export interface IDocumentCatergory extends IBaseApprovable {
  id: number;
  base_uuid: string;
  name: string;
  system_category: IBusinessDocumentCategory;
  description: string;
  created_at: string;
  updated_at: string;
  reference_code?: string;
}

export interface IDocumentCatergoryFormData {
  reference_code?: string;
  name: string;
  description?: string;
  system_category_code: string;
}

export interface IInventoryItemReturn {
  id: number;
  base_uuid: string;
  model_content_type_id: number;
  goods_issued_note: {
    base_uuid: string;
    reference_code: string;
  };
  return_type: "REPLACEMENT" | "CASH_REFUND";
  return_status: "PENDING" | "APPROVED" | "REJECTED";
  return_date?: string;
  are_initial_journal_entries_made: boolean;
  approval_status: ApprovableEntityStatus;
  approvals: Approval[];
  created_at: string;
  updated_at: string;
  reference_code: string;
  description?: string;
  created_by?: {
    id: number;
    fullname: string;
    email: string;
  };
  updated_by?: {
    id: number;
    fullname: string;
    email: string;
  };
  coa_cash_account?: {
    base_uuid: string;
    account_name: string;
  };
}

export interface IReturnItemFormData {
  goods_issued_note_line: string;
  return_reason: string;
  quantity: number;
  description?: string;
  external_base_uuid?: string;
}
export interface IInventoryItemReturnFormData {
  goods_issued_note: string;
  return_date?: string;
  return_type: "REPLACEMENT" | "CASH_REFUND";
  coa_cash_account?: string | null;
  item_return_items?: IReturnItemFormData[];
  description?: string;
  reference_code?: string;
  external_base_uuid?: string;
}

export interface ReturnedItem {
  id: number;
  base_uuid: string;
  quantity: number;
  description?: string;
  goods_issued_note_line: string;
  item: {
    id: number;
    base_uuid: string;
    inventory_item: {
      item_name: string;
      reference_code: string;
      item_category: string;
    };
  };
  return_reason: {
    id: number;
    base_uuid: string;
    return_reason_name: string;
  };
  unit_of_measure: {
    id: number;
    base_uuid: string;
    unit_name: string;
  };
}

export interface IReturnReason {
  id?: number | string;
  base_uuid?: string;
  return_reason_name: string;
  description: string;
  created_at?: string;
  updated_at?: string;
  reference_code?: string;
}

export interface IReturnReasonFormData {
  return_reason_name: string;
  description: string;
  reference_code: string;
}

export interface ICustomerDepositAllocation {
  id: string;
  base_uuid?: string;
  reference_code: string;
  amount_applied: string;
  invoice: {
    id: string;
    base_uuid: string;
    reference_code: string;
  };
  prepayment?: {
    id: string;
    base_uuid: string;
    reference_code: string;
  } | null;
  deposit?: {
    id: string;
    base_uuid: string;
    reference_code: string;
  } | null;
}

export interface ITaxReturn {
  id: number;
  base_uuid: string;
  institution_name: string;
  tax: ITax;
  tax_name: string;
  fiscal_year: IFiscalYear;
  fiscal_year_name: string;
  start_date: string;
  end_date: string;
  total_taxable_base: number;
  total_tax_liability: number;
  total_tax_paid_to_authority: number;
  net_amount_due: number;
  status: string;
  filing_date: string;
  payment_transaction: number;
  is_active: boolean;
  approval_status: string;
  created_at: string;
  updated_at: string;
}

export interface ITaxReturnFormData {
  tax: number;
  fiscal_year: number;
  start_date: string;
  end_date: string;
  filing_date: string;
}

export interface ITaxPayment {
  id: 0;
  base_uuid: string;
  tax_return: ITaxReturn;
  tax_return_reference_code: string;
  reference_code: string;
  prn: string;
  status: string;
  amount: number;
  other_costs: string;
  approval_status: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ITaxPaymentFormData {
  tax_return: number;
  prn: string;
  amount: number;
  other_costs: number;
  approval_status?: string;
}

export interface IBranchFormData {
  reference_code: string;
  branch_name: string;
  branch_legal_name: string;
  inventory_cost_variance_account?: string;
  branch_email: string;
  branch_phone_number: string;
  website: string;
  branch_type: "BRANCH" | "SUBSIDIARY" | "AFFILIATE" | "DIVISION";
  status: "operational" | "suspended" | "closed";
  ownership_percentage: string;
  supports_multiple_currencies: boolean;
  branch_location: string;
  state_or_region: string;
  city: string;
  address: string;
  branch_opening_time: string;
  branch_closing_time: string;
  registration_number: string;
  tax_identification_number: string;
  date_incorporated: string | null;
  parent: string | number | null;
  default_stock_valuation_method?: string;
  default_stock_movement_strategy?: string;
  deposit_distribution_strategy?:
    | "PAY_OLDEST_INVOICE_FIRST"
    | "PAY_LAST_INVOICE_FIRST"
    | "HOLD_AS_CREDIT";
  allow_sales_out_of_stock?: boolean;
}

export interface ISystemNotification {
  id: number;
  base_uuid: string;
  title: string;
  channel: "EMAIL" | "SMS" | "IN_APP";
  description?: string;
  created_at: string;
}

export interface INotificationTargetUser {
  id: number;
  fullname: string;
  email: string;
  base_uuid: string;
}

export interface IInstitutionNotificationSetting {
  id: number;
  base_uuid: string;
  is_enabled: boolean;
  system_notification: ISystemNotification;
  target_users: INotificationTargetUser[];
  institution: number;
  created_at: string;
  updated_at: string;
}

export interface INotificationSettingInput {
  notification: string;
  is_enabled: boolean;
  target_user_uuids?: string[];
}
export interface IDepreciationItem extends IBaseApprovable {}
export interface IDepreciationSchedule extends IBaseApprovable {}
export interface IQuote extends IBaseApprovable {}
export interface IReturnReason extends IBaseApprovable {}
export interface IPaymentReceived extends IBaseApprovable {}
export interface IItemUnitOfMeasure extends IBaseApprovable {}
export interface ISalesReceipt extends IBaseApprovable {}
export interface ICreditNote extends IBaseApprovable {}
export interface ICreditNoteItem extends IBaseApprovable {}
export interface IDebitNote extends IBaseApprovable {}
export interface IDebitNoteItem extends IBaseApprovable {}
export interface IRequisitionType extends IBaseApprovable {}
export interface IRequisitionItem extends IBaseApprovable {}
export interface IRequisition extends IBaseApprovable {}
export interface IBalanceSheet extends IBaseApprovable {}
export interface IIncomeStatement extends IBaseApprovable {}
export interface ITrialBalance extends IBaseApprovable {}
export interface IBusinessDocument extends IBaseApprovable {}
export interface IInstitutionSupportedBank {
  id: number;
  base_uuid: string;
  reference_code: string | null;
  bank_name: string;
  description: string | null;
  institution: number;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}
export type ExpenseStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface IExpenseTaxTotals {
  net_amount: string;
  tax_amount: string;
  gross_amount: string;
}

export interface IExpenseTaxSelection {
  tax: string;
  is_inclusive: boolean;
}

export interface IExpenseTaxBreakdown extends IExpenseTaxTotals {
  base_uuid: string;
  is_inclusive: boolean;
  tax: {
    base_uuid: string;
    tax_name: string;
    reference_code: string | null;
  };
}

export interface IExpenseListItem {
  base_uuid: string;
  reference_code: string;
  expense_date: string;
  branch: {
    id: number;
    base_uuid: string;
    branch_name: string;
    reference_code: string | null;
    branch_location: string | null;
  } | null;
  currency: number | null;
  total_amount: string;
  tax_totals: IExpenseTaxTotals;
  currency_code: string;
  status: ExpenseStatus;
  is_active: boolean;
  are_initial_journal_entries_made: boolean;
}

export interface IExpense extends IExpenseListItem {
  approval_status: string;
  attachment: string | null;
  model_content_type_id: number;
  description: string | null;
  allow_changes: boolean;
}

export interface IExpenseLineItem {
  expense_account: string;
  cash_account: string;
  applicable_taxes: IExpenseTaxBreakdown[];
  tax_totals: IExpenseTaxTotals;
  payee: string | null;
  payee_name: string | null;
  expense_account_reference_code: string | null;
  cash_account_reference_code: string | null;
  expense_account_name: string;
  cash_account_name: string;
  base_uuid: string;
  reference_code: string;
  description: string | null;
  amount: string;
}

export interface IExpenseFormData {
  attachment?: File | null;
  expense_date: string;
  branch: string | null;
  currency: number;
  description: string;
  exchange_rate?: IExchangeRateInput;
  line_items: {
    applicable_taxes: IExpenseTaxSelection[];
    payee: string | null;
    expense_account?: string | null;
    cash_account: string;
    amount: string;
    description: string;
  }[];
}
