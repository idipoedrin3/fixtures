import {IBaseApprovable} from "#/_types/approvals.types";
import {defineEndpoint} from "./_base";
import {downloadFileApi} from "../api.helpers";

export interface IStatement extends IBaseApprovable {
  reference: string;
  transaction_type: string;
  credit: string;
  debit: string;
  amount: string;
  balance_before: string;
  balance_after: string;
  activity_type: string;
  date: string;
  running_balance: string;
  description: string;
}

const statementsEndpoint = defineEndpoint<IStatement, {}>("/reports/vendor-customer-statements/");

export const STATEMENTS_API = Object.assign(statementsEndpoint, {
  downloadStatement: async ({
    entityType,
    baseUuid,
    format,
    startDate,
    endDate,
  }: {
    entityType: "customer" | "vendor";
    baseUuid: string;
    format: "pdf" | "excel";
    startDate?: string | null;
    endDate?: string | null;
  }) =>
    downloadFileApi({
      url: "reports/vendor-customer-statements/",
      method: "POST",
      expectedMime:
        format === "pdf"
          ? "application/pdf"
          : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      timeout: 60000,
      body: {
        entity_type: entityType,
        base_uuid: baseUuid,
        format,
        start_date: startDate || null,
        end_date: endDate || null,
      },
    }),
});

export interface IOrderStatement {
  statement_type: "outstanding" | "incoming";
  generated_at: string;
  total_records: string;
  rows: {
    purchase_order: {
      reference_code: string;
      status: string;
      amount: string;
      issue_date: string;
      aging_days?: number;
      days_outstanding?: number;
    };
    vendor?: {
      id: number;
      name: string;
    };
    customer?: {
      id: number;
      name: string;
    };
  }[];
}

export const ORDER_STATEMENTS_API = defineEndpoint<IOrderStatement, {}>(
  "/transactions/incoming-outgoing-statements/",
);

export const TAX_STATEMENTS_API = defineEndpoint<any, any>("taxation/tax-application-statement/");
