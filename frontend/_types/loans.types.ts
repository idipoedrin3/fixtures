import type {Approval, ApprovableEntityStatus} from "./approvals.types";
import type {IPaginatedResponse} from "./api.types";

export interface ILender {
  base_uuid: string;
  name: string;
  reference_code: string | null;
  description: string | null;
  is_active: boolean;
  approval_status: ApprovableEntityStatus;
  approvals: Approval[];
  allow_changes: boolean;
  model_content_type_id: number;
  created_at: string;
  updated_at: string;
}

export interface ILoan {
  base_uuid: string;
  reference_code: string | null;
  direction: "inflow" | "outflow";
  principal: string;
  annual_interest_rate: string;
  disbursement_date: string;
  maturity_date: string;
  status: "pending" | "approved" | "rejected";
  approval_status: ApprovableEntityStatus;
  allow_changes: boolean;
}

export interface ILenderFormData {
  name: string;
  description: string;
  reference_code?: string;
}

export interface ILoanDetail extends ILoan, Omit<ILoanCreateData, keyof ILoan | "description"> {
  party_name: string | null;
  currency_code: string;
  branch_name: string | null;
  cash_account_name: string;
  loan_account_name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  model_content_type_id: number;
  initial_journal: string | null;
  are_initial_journal_entries_processed: boolean;
}

export interface ILoanSchedulePreviewResponse extends IPaginatedResponse<ILoanSchedulePreviewRow> {
  currency: string;
  totals: {
    principal: string;
    interest: string;
    payment: string;
  };
}

export interface ILoanSchedulePreviewRow {
  number: number;
  due_date: string;
  opening_principal: string;
  principal: string;
  interest: string;
  payment: string;
  closing_principal: string;
}

export interface ILoanCreateData {
  reference_code?: string;
  direction: "inflow" | "outflow";
  party_object_uuid: string;
  branch: string | null;
  currency: string;
  principal: string;
  annual_interest_rate: string;
  interest_method: "flat" | "reducing";
  interest_type: "simple" | "compound";
  day_count_convention: "actual_365" | "actual_360" | "actual_actual_isda";
  repayment_structure: "periodic" | "single";
  repayment_frequency: string | null;
  repayment_method: "equal_installments" | "equal_principal" | null;
  repayment_timing: "beginning" | "end" | null;
  disbursement_date: string;
  first_repayment_date: string;
  maturity_date: string;
  cash_account: string;
  liability_receivable_account: string;
  description: string;
  initial_accounting_treatment: LoanInitialAccountingTreatment;
  initial_accounting_reference: string;
  opening_principal: string | null;
  opening_balance_account: string | null;
}

export type LoanAccountingTreatment = "cash" | "historical_cash" | "already_recorded";

export interface ILoanPaymentAllocation {
  repayment_schedule: string;
  installation_number: number | null;
  due_date: string | null;
  principal_amount: string;
  interest_amount: string;
  fee_amount: string;
  amount: string;
}

export interface ILoanRepayment {
  base_uuid: string;
  reference_code: string | null;
  loan: string;
  date: string;
  amount: string;
  status: "pending" | "completed" | "rejected";
  approval_status: string;
  allow_changes?: boolean;
  accounting_treatment: LoanAccountingTreatment | null;
  accounting_reference: string;
  allocations: ILoanPaymentAllocation[];
  created_at: string;
}

export interface ILoanRepaymentCreateData {
  date: string;
  amount: string;
  accounting_treatment: LoanAccountingTreatment;
  accounting_reference: string;
  allocations: {
    repayment_schedule: string;
    principal_amount: string;
    interest_amount: string;
    fee_amount: string;
  }[];
}

export interface IAllocationSuggestion {
  repayment_schedule: string;
  installation_number: number;
  due_date: string;
  principal_outstanding: string;
  interest_outstanding: string;
  fees_outstanding: string;
  principal_amount: string;
  interest_amount: string;
  fee_amount: string;
}

export interface IAllocationPreviewResponse {
  allocations: IAllocationSuggestion[];
  unallocated: string;
}

export interface ILoanPaymentAllocation {
  repayment_schedule: string;
  installation_number: number | null;
  due_date: string | null;
  principal_amount: string;
  interest_amount: string;
  fee_amount: string;
  amount: string;
}

export interface ILoanRepayment {
  base_uuid: string;
  reference_code: string | null;
  loan: string;
  date: string;
  amount: string;
  status: "pending" | "completed" | "rejected";
  approval_status: string;
  allow_changes?: boolean;
  accounting_treatment: LoanAccountingTreatment | null;
  accounting_reference: string;
  allocations: ILoanPaymentAllocation[];
  created_at: string;
}

export interface ILoanRepaymentCreateData {
  date: string;
  amount: string;
  accounting_treatment: LoanAccountingTreatment;
  accounting_reference: string;
  allocations: {
    repayment_schedule: string;
    principal_amount: string;
    interest_amount: string;
    fee_amount: string;
  }[];
}

export interface IAllocationSuggestion {
  repayment_schedule: string;
  installation_number: number;
  due_date: string;
  principal_outstanding: string;
  interest_outstanding: string;
  fees_outstanding: string;
  principal_amount: string;
  interest_amount: string;
  fee_amount: string;
}

export interface IAllocationPreviewRequest {
  amount?: string;
  repayment_schedule?: string;
  payment?: string;
}

export interface IAllocationPreviewResponse {
  allocations: IAllocationSuggestion[];
  unallocated: string;
}

export interface ILoanSchedulePayment {
  base_uuid: string;
  reference_code: string | null;
  date: string;
  status: string;
  principal_amount: string;
  interest_amount: string;
  fee_amount: string;
  amount: string;
}

export interface ILoanScheduleRow {
  base_uuid: string | null;
  installation_number: number;
  due_date: string;
  status: string | null;
  record_state: string;
  opening_principal: string;
  principal_due: string;
  interest_due: string;
  fees_due: string;
  total_due: string;
  total_paid: string;
  outstanding: string;
  payable: string;
  can_pay: boolean;
  payments: ILoanSchedulePayment[];
}

export interface ILoanScheduleTotals {
  principal: string;
  interest: string;
  fees: string;
  total_due: string;
  paid: string;
  outstanding: string;
}

export interface ILoanScheduleResponse extends IPaginatedResponse<ILoanScheduleRow> {
  currency: string;
  notice: string;
  totals: ILoanScheduleTotals;
}

export type LoanInitialAccountingTreatment =
  | "new_cash"
  | "historical_cash"
  | "opening_balance"
  | "already_recorded";
