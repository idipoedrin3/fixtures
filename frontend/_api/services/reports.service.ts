import {downloadFile} from "#/_lib/utils";
import {defineEndpoint} from "./_base";

type AgingDetails = {
  currency_code: string;
  base_currency_code: string;
  original_amount: string;
  original_buckets: Record<"current" | "1-30" | "30-60" | "60-90" | "90+", string>;
  due_date: string;
  amount: string;
  days_overdue: number;
  aging_bucket: string;
  current: string;
  "1-30": string;
  "30-60": string;
  "60-90": string;
  "90+": string;
};

export interface IAgingReportDownloadPayload {
  search?: string;
  customer_uuid?: string;
  vendor_uuid?: string;
  customer_uuids?: string;
  vendor_uuids?: string;
  report_type: "receivable" | "payable";
  format: "pdf" | "excel";
  as_of_date?: string;
  start_date: string;
  end_date: string;
}

export interface ICustomerAging extends AgingDetails {
  customer_name: string;
  customer_code: string;
  invoice_number: string;
  invoice_date: string;
}

const customer_api = defineEndpoint<ICustomerAging, {}>("/reports/aging/receivables/");

export const CUSTOMER_AGING_REPORT_API = {
  fetch: customer_api.fetch,
  fetchFromUrl: customer_api.fetchFromUrl,
  download: async (payload: IAgingReportDownloadPayload) => {
    const blob = await customer_api.download("reports/aging-reports/download/", payload, "POST", {
      "Content-Type": "application/json",
    });
    downloadFile(
      window.URL.createObjectURL(blob),
      `${payload.report_type === "receivable" ? "customer" : "vendor"}_aging_report_${payload?.start_date ?? ""}_${payload?.end_date ?? ""}.${payload.format == "pdf" ? "pdf" : "xlsx"}`,
    );
  },
};

export interface IVendorAging extends AgingDetails {
  vendor_name: string;
  vendor_code: string;
  bill_number: string;
  bill_date: string;
}

const vendor_api = defineEndpoint<IVendorAging, {}>("/reports/aging/payables/");

export const VENDOR_AGING_REPORT_API = {
  fetch: vendor_api.fetch,
  fetchFromUrl: vendor_api.fetchFromUrl,
};

export interface IAgingReport {
  summary: {
    currency_code: string;
    total_current: string;
    "total_1-30": string;
    "total_30-60": string;
    "total_60-90": string;
    "total_90+": string;
    total_30_90: string;
    total_amount: string;
    transaction_count: 0;
    [key: string]: string | number;
  };
  activities: IVendorAging[] | ICustomerAging[];
}
