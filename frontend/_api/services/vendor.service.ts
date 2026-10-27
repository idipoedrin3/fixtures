import {IUser, IVendor, IVendorBill, IVendorPurchaseOrder} from "#/_types/api.types";
import {IBaseApprovable} from "#/_types/approvals.types";
import {defineEndpoint} from "./_base";

export interface IVendorPrepayment extends IBaseApprovable {
  reference_code: string;
  vendor: IVendor;
  amount: string;
  status: string;
  created_at: string;
  additional_notes: string;
  is_requisition_created: boolean;
}

export interface IVendorPrepaymentForm {
  vendor: string;
  amount: string;
  additional_notes: string;
  reference_code: string;
}

export interface IOrderBillReceipt extends IBaseApprovable {
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  external_base_uuid: string;
  reference_code: string;
  created_by?: IUser;
  updated_by?: IUser;
  purchase_order?: IVendorPurchaseOrder;
  bill?: IVendorBill;
}

export interface IOrderBillReceiptForm {
  purchase_order?: string;
  bill?: string;
}

export const VENDOR_ORDER_BILL_RECEIPT_API = defineEndpoint<
  IOrderBillReceipt,
  IOrderBillReceiptForm
>("/vendors/order-bill-reciept");
