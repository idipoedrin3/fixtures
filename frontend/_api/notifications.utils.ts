import apiRequest from "../_api/api-request";

import {IPaginatedResponse, ITransactionEntryFormData} from "#/_types/api.types";
import {
  IBillOfMaterial,
  IBillOfMaterialFormData,
  IBillOfMaterialLineItem,
  IBOMLineItem,
  IBOMOverheadCost,
  IExecution,
  IExecutionConsumptionGroup,
  IExecutionConsumptionRecord,
  IExecutionFinancials,
  IExecutionFormData,
  IExecutionOutput,
  IExecutionOutputAllocationSuggestion,
  IExecutionRemainingConsumption,
  IOrder,
  IOrderFormData,
  IOverHeadCosts,
  IBeneficiaryPaymentMethod,
  IBeneficiaryPaymentMethodFormData,
  IPotentialConsumption,
  IReconciliationCreateFormData,
  IReconciliationLiveStats,
  IReconciliationMatch,
  IReconciliationSession,
  IReconciliationStrategy,
  IRequisitionBeneficiary,
  IRequisitionBeneficiaryFormData,
  IStatementLine,
} from "../_types/types.utils";
import {IPreferredVendor, IPreferredVendorFormData} from "../_types/email";

export interface INotification {
  id: number;
  user: {
    id: number;
    fullname: string;
    email: string;
    username: string;
  };
  message: string;
  is_read: boolean;
  model_name: string;
  object_id: string;
  object_base_uuid: string;
  requires_acknowledgment: boolean;
  created_at: string;
  updated_at: string;
}

export const NOTIFICATIONS_API = {
  async fetch() {
    const res = await apiRequest.get("/communication/notifications/unread/");

    return res.data as IPaginatedResponse<INotification>;
  },
  markAsRead: async ({notificationId}: {notificationId: number}) => {
    await apiRequest.post(
      `/communication/notifications/read/?notification_id=${notificationId}`,
      {},
    );
  },
};

export const RECONCILIATION_API = {
  fetchBalancePreview: async ({
    accountBaseUuid,
    startDate,
    endDate,
  }: {
    accountBaseUuid: string;
    startDate: string;
    endDate: string;
  }) => {
    const params = new URLSearchParams({
      account_uuid: accountBaseUuid,
      start_date: startDate,
      end_date: endDate,
    });
    const response = await apiRequest.get(
      `/bank_management/reconciliation-balance-preview/?${params.toString()}`,
    );
    return response.data as {
      ledger_opening_balance: string;
      ledger_closing_balance: string;
      balance_difference: string;
    };
  },

  fetchSessions: async ({
    page = 1,
    search,
    status,
    account,
    ordering,
  }: {
    page?: number;
    search?: string;
    status?: string;
    account?: string[];
    ordering?: string;
  }) => {
    const params = new URLSearchParams({page: page.toString()});
    if (search) params.append("search", search);
    if (status && status !== "all") params.append("status", status);
    account?.forEach((accountUuid) => params.append("coa_reference__base_uuid", accountUuid));
    if (ordering) params.append("ordering", ordering);
    const response = await apiRequest.get(
      `/bank_management/reconciliation-sessions/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IReconciliationSession>;
  },

  fetchSessionsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IReconciliationSession>;
  },

  createSession: async ({data}: {data: IReconciliationCreateFormData | FormData}) => {
    const response = await apiRequest.post(`/bank_management/reconciliation-sessions/`, data);
    return response.data as IReconciliationSession;
  },

  updateSession: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IReconciliationCreateFormData> | FormData;
  }) => {
    const response = await apiRequest.patch(
      `/bank_management/reconciliation-sessions/${baseUuid}/`,
      data,
    );
    return response.data as IReconciliationSession;
  },

  fetchSessionById: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`/bank_management/reconciliation-sessions/${baseUuid}/`);
    return response.data as IReconciliationSession;
  },

  deleteSession: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`/bank_management/reconciliation-sessions/${baseUuid}/`);
  },

  submitColumnMapping: async ({
    baseUuid,
    mapping,
  }: {
    baseUuid: string;
    mapping: Record<string, string>;
  }) => {
    const response = await apiRequest.post(`/bank_management/column-mapping/${baseUuid}/`, {
      mappings: Object.entries(mapping).map(([expected_column, statement_column]) => ({
        expected_column,
        statement_column,
      })),
    });
    return response.data;
  },

  fetchStatementLines: async ({
    baseUuid,
    search,
    ordering,
    flow_type,
    is_matched,
  }: {
    baseUuid: string;
    search?: string;
    ordering?: string;
    flow_type?: "INFLOW" | "OUTFLOW";
    is_matched?: boolean;
  }) => {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (flow_type) params.append("flow_type", flow_type);
    if (is_matched !== undefined) params.append("is_matched", String(is_matched));
    const response = await apiRequest.get(
      `/bank_management/reconciliation-statement-lines/${baseUuid}/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IStatementLine>;
  },

  fetchAllStatementLines: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(
      `/bank_management/reconciliation-statement-lines/${baseUuid}/`,
    );
    return response.data as IStatementLine[];
  },

  fetchMatchHint: async ({
    sessionUuid,
    flow_type,
  }: {
    sessionUuid: string;
    flow_type?: "INFLOW" | "OUTFLOW";
  }) => {
    const params = new URLSearchParams();
    if (flow_type) params.append("flow_type", flow_type);

    const response = await apiRequest.get(
      `/bank_management/reconciliation-match-hint/${sessionUuid}/?${params.toString()}`,
    );
    return response.data as {
      internal_record_uuid: string;
      external_record_uuid: string;
      confidence_score: string;
    }[];
  },

  fetchMatches: async ({sessionUuid}: {sessionUuid: string}) => {
    const response = await apiRequest.get(
      `/bank_management/reconciliation-matches/${sessionUuid}/`,
    );
    return response.data as IReconciliationMatch[];
  },

  deleteMatch: async ({matchUuid}: {matchUuid: string}) => {
    await apiRequest.delete(`/bank_management/reconciliation-matches/${matchUuid}/detail/`);
  },

  undoAllMatches: async ({sessionUuid}: {sessionUuid: string}) => {
    const response = await apiRequest.delete(
      `/bank_management/reconciliation-matches/${sessionUuid}/undo-all/`,
    );
    return response.data as {
      message: string;
      matches_removed: number;
      statement_lines_reset: number;
      ledger_entries_reset: number;
    };
  },

  createMatch: async ({
    sessionUuid,
    combinations,
  }: {
    sessionUuid: string;
    combinations: {
      statement_line: string;
      coa_account_entry: string;
      description?: string;
      external_base_uuid?: string;
      reference_code?: string;
      match_type: "auto" | "manual";
      confidence: "high" | "medium" | "low";
    }[];
  }) => {
    const response = await apiRequest.post(
      `/bank_management/reconciliation-matches/${sessionUuid}/`,
      {combinations},
    );
    return response.data;
  },

  autoMatch: async ({sessionUuid}: {sessionUuid: string}) => {
    const response = await apiRequest.get(
      `/bank_management/reconciliation-match-auto-match/${sessionUuid}/?session_uuid=${sessionUuid}`,
    );
    return response.data as IReconciliationMatch[];
  },

  closeSession: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.post(
      `/bank_management/reconciliation-sessions/${baseUuid}/close/`,
      {},
    );
    return response.data;
  },

  reconcileEntries: async ({
    sessionUuid,
    reconciliations,
  }: {
    sessionUuid: string;
    reconciliations: {
      transaction_entry: string;
      is_reconciled: boolean;
      description?: string;
    }[];
  }) => {
    const response = await apiRequest.post(`/transactions/reconcile-transaction-entries/`, {
      reconciliation_session: sessionUuid,
      reconciliations,
    });
    return response.data;
  },

  fetchLiveStats: async ({sessionUuid}: {sessionUuid: string}) => {
    const response = await apiRequest.get(
      `/bank_management/reconciliation-session-live-stats/${sessionUuid}/`,
    );
    return response.data as IReconciliationLiveStats;
  },

  fetchResolutionStrategies: async () => {
    const response = await apiRequest.get("/system/reconciliation-resolution-strategies/");
    const data = response.data;
    return (Array.isArray(data) ? data : (data.results ?? [])) as IReconciliationStrategy[];
  },

  resolveReconciliation: async ({
    sessionUuid,
    payload,
  }: {
    sessionUuid: string;
    payload: {
      statement_lines?: string[];
      ledger_entries?: string[];
      resolution_strategy: string;
      description?: string;
      transaction_entries?: ITransactionEntryFormData[];
    };
  }) => {
    const response = await apiRequest.post(
      `/bank_management/reconciliation-resolutions/${sessionUuid}/`,
      payload,
    );
    return response.data;
  },
};

export type BillOfMaterialItemUomCombination = {
  inventory_item_uuid: string;
  inventory_item_unit_of_measure_uuid: string;
};

export const BILL_OF_MATERIAL_API = {
  fetchBillOfMaterials: async ({
    page = 1,
    ordering,
    search = "",
    inventory_item_uuid,
    inventory_item_unit_of_measure_uuid,
    inventory_item_uom_combinations = [],
  }: {
    page?: number;
    ordering?: string;
    search?: string;
    inventory_item_uuid?: string;
    inventory_item_unit_of_measure_uuid?: string;
    inventory_item_uom_combinations?: BillOfMaterialItemUomCombination[];
  }) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (inventory_item_uuid) params.append("inventory_item_uuid", inventory_item_uuid);
    if (inventory_item_unit_of_measure_uuid)
      params.append("inventory_item_unit_of_measure_uuid", inventory_item_unit_of_measure_uuid);
    inventory_item_uom_combinations.forEach(
      ({inventory_item_uuid: itemUuid, inventory_item_unit_of_measure_uuid: uomUuid}) => {
        if (itemUuid && uomUuid) {
          params.append("inventory_item_uom_pair", `${itemUuid}:${uomUuid}`);
        }
      },
    );

    const response = await apiRequest.get(`manufacturing/bill-of-material/?${params.toString()}`);
    return response.data as IPaginatedResponse<IBillOfMaterial>;
  },

  fetchBillOfMaterialsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IBillOfMaterial>;
  },

  createBillOfMaterial: async ({data}: {data: IBillOfMaterialFormData}) => {
    const response = await apiRequest.post(`manufacturing/bill-of-material/`, data);

    return response.data as IBillOfMaterial;
  },

  fetchBillOfMaterialByUuid: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`manufacturing/bill-of-material/${baseUuid}/`);

    return response.data as IBillOfMaterial;
  },

  updateBillOfMaterial: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IBillOfMaterialFormData>;
  }) => {
    const response = await apiRequest.patch(`manufacturing/bill-of-material/${baseUuid}/`, data);

    return response.data as IBillOfMaterial;
  },

  deleteBillOfMaterial: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`manufacturing/bill-of-material/${baseUuid}/`);
  },

  fetchBOMLineItems: async ({
    billOfMaterialUuid,
    branch_uuid,
    page = 1,
    search,
  }: {
    billOfMaterialUuid: string;
    branch_uuid?: string;
    page?: number;
    search?: string;
  }) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    if (branch_uuid) params.append("branch_uuid", branch_uuid);
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `manufacturing/bom-line-items/${billOfMaterialUuid}/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IBOMLineItem>;
  },

  fetchBOMLineItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBOMLineItem>;
  },

  fetchBOMOverheadCosts: async ({
    billOfMaterialUuid,
    page = 1,
  }: {
    billOfMaterialUuid: string;
    page?: number;
  }) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());

    const response = await apiRequest.get(
      `manufacturing/bom-overhead-costs/${billOfMaterialUuid}/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IBOMOverheadCost>;
  },

  fetchBOMOverheadCostsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBOMOverheadCost>;
  },

  createBOMOverheadCost: async ({
    billOfMaterialUuid,
    data,
  }: {
    billOfMaterialUuid: string;
    data: IOverHeadCosts;
  }) => {
    const response = await apiRequest.post(
      `manufacturing/bom-overhead-costs/${billOfMaterialUuid}/`,
      {...data, cost_amount: String(data.cost_amount)},
    );
    return response.data as IBOMOverheadCost;
  },

  fetchBOMOverheadCostByUuid: async ({overheadCostUuid}: {overheadCostUuid: string}) => {
    const response = await apiRequest.get(
      `manufacturing/bom-overhead-costs/${overheadCostUuid}/detail/`,
    );
    return response.data as IBOMOverheadCost;
  },

  updateBOMOverheadCost: async ({
    overheadCostUuid,
    data,
  }: {
    overheadCostUuid: string;
    data: Partial<IOverHeadCosts>;
  }) => {
    const response = await apiRequest.patch(
      `manufacturing/bom-overhead-costs/${overheadCostUuid}/detail/`,
      {...data, ...(data.cost_amount !== undefined ? {cost_amount: String(data.cost_amount)} : {})},
    );
    return response.data as IBOMOverheadCost;
  },

  deleteBOMOverheadCost: async ({overheadCostUuid}: {overheadCostUuid: string}) => {
    await apiRequest.delete(`manufacturing/bom-overhead-costs/${overheadCostUuid}/detail/`);
  },

  createBOMLineItem: async ({
    billOfMaterialUuid,
    data,
  }: {
    billOfMaterialUuid: string;
    data: IBillOfMaterialLineItem;
  }) => {
    const response = await apiRequest.post(
      `manufacturing/bom-line-items/${billOfMaterialUuid}/`,
      data,
    );
    return response.data as IBOMLineItem;
  },

  fetchBOMLineItemByUuid: async ({lineItemUuid}: {lineItemUuid: string}) => {
    const response = await apiRequest.get(`manufacturing/bom-line-items/${lineItemUuid}/detail/`);
    return response.data as IBOMLineItem;
  },

  updateBOMLineItem: async ({
    lineItemUuid,
    data,
  }: {
    lineItemUuid: string;
    data: Partial<IBillOfMaterialLineItem>;
  }) => {
    const response = await apiRequest.patch(
      `manufacturing/bom-line-items/${lineItemUuid}/detail/`,
      data,
    );
    return response.data as IBOMLineItem;
  },

  deleteBOMLineItem: async ({lineItemUuid}: {lineItemUuid: string}) => {
    await apiRequest.delete(`manufacturing/bom-line-items/${lineItemUuid}/detail/`);
  },
};

export const ORDERS_API = {
  fetchOrders: async ({
    page = 1,
    search = "",
    ordering,
    without_executions,
    execution_ready,
    invoice_base_uuid,
    customer_purchase_order_base_uuid,
  }: {
    page?: number;
    search?: string;
    ordering?: string;
    without_executions?: boolean;
    execution_ready?: boolean;
    invoice_base_uuid?: string;
    customer_purchase_order_base_uuid?: string;
  }) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (without_executions !== undefined) {
      params.append("without_executions", String(without_executions));
    }
    if (execution_ready !== undefined) {
      params.append("execution_ready", String(execution_ready));
    }
    if (invoice_base_uuid) params.append("invoice_base_uuid", invoice_base_uuid);
    if (customer_purchase_order_base_uuid) {
      params.append("customer_purchase_order_base_uuid", customer_purchase_order_base_uuid);
    }

    const response = await apiRequest.get(`manufacturing/orders/?${params.toString()}`);
    return response.data as IPaginatedResponse<IOrder>;
  },

  fetchOrdersFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IOrder>;
  },

  fetchOrderByUuid: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`manufacturing/orders/${baseUuid}/`);
    return response.data as IOrder;
  },

  createOrder: async ({data}: {data: IOrderFormData}) => {
    const response = await apiRequest.post(`manufacturing/orders/`, [data]);
    const orders = response.data as IOrder[];
    return orders[0];
  },

  createOrders: async ({data}: {data: IOrderFormData[]}) => {
    const response = await apiRequest.post(`manufacturing/orders/`, data);
    return response.data as IOrder[];
  },

  updateOrder: async ({baseUuid, data}: {baseUuid: string; data: Partial<IOrderFormData>}) => {
    const response = await apiRequest.patch(`manufacturing/orders/${baseUuid}/`, data);
    return response.data as IOrder;
  },

  deleteOrder: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`manufacturing/orders/${baseUuid}/`);
  },
};

export const EXECUTIONS_API = {
  fetchPotentialConsumptions: async ({
    billOfMaterialBaseUuid,
    quantityToProduce,
    branchBaseUuid,
    typeOfConsumption,
    page,
  }: {
    billOfMaterialBaseUuid: string;
    quantityToProduce: number;
    branchBaseUuid?: string;
    typeOfConsumption?: "all" | "material" | "overhead";
    page?: number;
  }): Promise<IPaginatedResponse<IPotentialConsumption>> => {
    const response = await apiRequest.get("manufacturing/potential-consumptions/", {
      bill_of_material_base_uuid: billOfMaterialBaseUuid,
      quantity_to_produce: quantityToProduce,
      ...(branchBaseUuid ? {branch_uuid: branchBaseUuid} : {}),
      ...(typeOfConsumption ? {type_of_consumption: typeOfConsumption} : {}),
      ...(page ? {page} : {}),
    });
    return response.data as IPaginatedResponse<IPotentialConsumption>;
  },

  fetchPotentialConsumptionsFromUrl: async ({
    url,
  }: {
    url: string;
  }): Promise<IPaginatedResponse<IPotentialConsumption>> => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IPotentialConsumption>;
  },

  fetchExecutionRemainingConsumptions: async ({
    executionBaseUuid,
    page,
  }: {
    executionBaseUuid: string;
    page?: number;
  }): Promise<IPaginatedResponse<IExecutionRemainingConsumption>> => {
    const response = await apiRequest.get(
      `manufacturing/execution-remaining-consumptions/${executionBaseUuid}/`,
      {
        ...(page ? {page} : {}),
      },
    );
    return response.data as IPaginatedResponse<IExecutionRemainingConsumption>;
  },

  fetchExecutionRemainingConsumptionsFromUrl: async ({
    url,
  }: {
    url: string;
  }): Promise<IPaginatedResponse<IExecutionRemainingConsumption>> => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IExecutionRemainingConsumption>;
  },

  fetchExecutions: async ({
    page = 1,
    search = "",
    ordering,
  }: {
    page?: number;
    search?: string;
    ordering?: string;
  }) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    const response = await apiRequest.get(`manufacturing/executions/?${params.toString()}`);
    return response.data as IPaginatedResponse<IExecution>;
  },

  fetchExecutionsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IExecution>;
  },

  fetchExecutionByUuid: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`manufacturing/executions/${baseUuid}/`);
    return response.data as IExecution;
  },

  createExecution: async ({data}: {data: IExecutionFormData}) => {
    const response = await apiRequest.post(`manufacturing/executions/`, data);
    return response.data as IExecution;
  },

  updateExecution: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IExecutionFormData>;
  }) => {
    const response = await apiRequest.patch(`manufacturing/executions/${baseUuid}/`, data);
    return response.data as IExecution;
  },

  deleteExecution: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`manufacturing/executions/${baseUuid}/`);
  },

  createExecutionConsumption: async ({
    executionBaseUuid,
    data,
  }: {
    executionBaseUuid: string;
    data: {
      component: string;
      unit_of_measure: string;
      quantity_used: string;
      manufacturing_order: string;
      description?: string;
      reference_code?: string;
    }[];
  }) => {
    const response = await apiRequest.post(
      `manufacturing/execution-consumptions/${executionBaseUuid}/`,
      data,
    );
    return response.data;
  },

  fetchExecutionOutputs: async ({
    executionBaseUuid,
    ...params
  }: {
    executionBaseUuid: string;
    [key: string]: any;
  }) => {
    const response = await apiRequest.get(`manufacturing/execution-outputs/${executionBaseUuid}/`, {
      params,
    });
    return response.data as IPaginatedResponse<IExecutionOutput>;
  },

  fetchExecutionOutputsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IExecutionOutput>;
  },

  fetchExecutionConsumptions: async ({
    executionBaseUuid,
    ...params
  }: {
    executionBaseUuid: string;
    [key: string]: any;
  }) => {
    const response = await apiRequest.get(
      `manufacturing/execution-consumptions/${executionBaseUuid}/`,
      params,
    );
    return response.data as IPaginatedResponse<IExecutionConsumptionRecord>;
  },

  fetchExecutionConsumptionsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IExecutionConsumptionRecord>;
  },

  createExecutionOutput: async ({
    executionBaseUuid,
    data,
  }: {
    executionBaseUuid: string;
    data: {
      quantity_produced: string;
      date_of_production: string;
      reference_code?: string;
      description?: string;
      consumption_allocations?: {
        consumption_group: string;
        infer_quantity?: boolean;
        quantity?: string | null;
      }[];
    }[];
  }) => {
    const response = await apiRequest.post(
      `manufacturing/execution-outputs/${executionBaseUuid}/`,
      data,
    );
    return response.data;
  },

  fetchExecutionFinancials: async ({
    baseUuid,
    manufacturing_execution_consumption_group_uuid,
    type,
    search,
  }: {
    baseUuid: string;
    manufacturing_execution_consumption_group_uuid?: string;
    type?: "consumption" | "output";
    search?: string;
  }) => {
    const params = new URLSearchParams();
    if (manufacturing_execution_consumption_group_uuid) {
      params.append(
        "manufacturing_execution_consumption_group_uuid",
        manufacturing_execution_consumption_group_uuid,
      );
    }
    if (type) params.append("type", type);
    if (search) params.append("search", search);

    const response = await apiRequest.get(
      `manufacturing/execution-financials/${baseUuid}/?${params.toString()}`,
    );
    return response.data as IExecutionFinancials;
  },

  fetchExecutionConsumptionByUuid: async ({
    consumptionUuid,
  }: {
    baseUuid: string;
    consumptionUuid: string;
  }) => {
    const response = await apiRequest.get(
      `manufacturing/execution-consumptions/${consumptionUuid}/detail/`,
    );
    return response.data as IExecutionConsumptionRecord;
  },

  fetchExecutionOutputByUuid: async ({outputUuid}: {baseUuid: string; outputUuid: string}) => {
    const response = await apiRequest.get(`manufacturing/execution-outputs/${outputUuid}/detail/`);
    return response.data as IExecutionOutput;
  },
  markAsDone: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.post(`manufacturing/mark-as-done/${baseUuid}/`, {});
    return response.data;
  },
  fetchExecutionConsumptionGroups: async ({
    executionBaseUuid,
    ...params
  }: {
    executionBaseUuid: string;
    [key: string]: any;
  }) => {
    const response = await apiRequest.get(
      `manufacturing/execution-consumption-groups/${executionBaseUuid}/`,
      params,
    );
    return response.data as IPaginatedResponse<IExecutionConsumptionGroup>;
  },

  fetchExecutionConsumptionGroupsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IExecutionConsumptionGroup>;
  },

  fetchExecutionConsumptionGroupByUuid: async ({groupUuid}: {groupUuid: string}) => {
    const response = await apiRequest.get(
      `manufacturing/execution-consumption-groups/${groupUuid}/detail/`,
    );
    return response.data as IExecutionConsumptionGroup;
  },

  fetchExecutionOutputAllocationSuggestions: async ({
    executionBaseUuid,
    quantityProduced,
  }: {
    executionBaseUuid: string;
    quantityProduced: string | number;
  }) => {
    const response = await apiRequest.get(
      `manufacturing/execution-output-allocation-suggestions/${executionBaseUuid}/`,
      {
        quantity_produced: quantityProduced,
      },
    );
    return response.data as IExecutionOutputAllocationSuggestion[];
  },
};

export const REQUISITION_BENEFICIARIES_API = {
  importRequisitionBeneficiaries: async ({
    vendors = [],
    profileInstitutions = [],
  }: {
    vendors?: string[];
    profileInstitutions?: string[];
  }) => {
    const response = await apiRequest.post("requisitions/beneficiaries/import-from-create/", {
      vendors,
      profile_institutions: profileInstitutions,
    });

    return response.data as {
      created: IRequisitionBeneficiary[];
      created_count: number;
      skipped: {
        vendors: string[];
        profile_institutions: string[];
      };
      skipped_count: number;
    };
  },

  fetchRequisitionBeneficiaries: async ({
    page = 1,
    search,
    ordering,
    requisitionBaseUuid,
  }: {
    page?: number;
    search?: string;
    ordering?: string;
    requisitionBaseUuid?: string;
  }) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (requisitionBaseUuid) {
      params.append("requisition_base_uuid", requisitionBaseUuid);
    }

    const response = await apiRequest.get(`requisitions/beneficiaries/?${params.toString()}`);
    return response.data as IPaginatedResponse<IRequisitionBeneficiary>;
  },

  fetchRequisitionBeneficiariesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IRequisitionBeneficiary>;
  },

  createRequisitionBeneficiary: async ({data}: {data: IRequisitionBeneficiaryFormData}) => {
    const response = await apiRequest.post(`requisitions/beneficiaries/`, data);
    return response.data as IRequisitionBeneficiary;
  },

  fetchRequisitionBeneficiaryByUuid: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`requisitions/beneficiaries/${baseUuid}/`);
    return response.data as IRequisitionBeneficiary;
  },

  updateRequisitionBeneficiary: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IRequisitionBeneficiaryFormData>;
  }) => {
    const response = await apiRequest.patch(`requisitions/beneficiaries/${baseUuid}/`, data);
    return response.data as IRequisitionBeneficiary;
  },

  deleteRequisitionBeneficiary: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`requisitions/beneficiaries/${baseUuid}/`);
  },

  fetchPaymentMethods: async ({
    beneficiaryBaseUuid,
    search,
    currencyId,
  }: {
    beneficiaryBaseUuid: string;
    search?: string;
    currencyId?: number;
  }) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (currencyId !== undefined) params.set("effective_currency_id", String(currencyId));

    const response = await apiRequest.get(
      `requisitions/beneficiaries/${beneficiaryBaseUuid}/payment-methods/?${params.toString()}`,
    );
    return response.data as IBeneficiaryPaymentMethod[];
  },

  createPaymentMethod: async ({
    beneficiaryBaseUuid,
    data,
  }: {
    beneficiaryBaseUuid: string;
    data: IBeneficiaryPaymentMethodFormData;
  }) => {
    const response = await apiRequest.post(
      `requisitions/beneficiaries/${beneficiaryBaseUuid}/payment-methods/`,
      data,
    );
    return response.data as IBeneficiaryPaymentMethod;
  },

  updatePaymentMethod: async ({
    beneficiaryBaseUuid,
    paymentMethodBaseUuid,
    data,
  }: {
    beneficiaryBaseUuid: string;
    paymentMethodBaseUuid: string;
    data: Partial<IBeneficiaryPaymentMethodFormData>;
  }) => {
    const response = await apiRequest.patch(
      `requisitions/beneficiaries/${beneficiaryBaseUuid}/payment-methods/${paymentMethodBaseUuid}/`,
      data,
    );
    return response.data as IBeneficiaryPaymentMethod;
  },

  deletePaymentMethod: async ({
    beneficiaryBaseUuid,
    paymentMethodBaseUuid,
  }: {
    beneficiaryBaseUuid: string;
    paymentMethodBaseUuid: string;
  }) => {
    await apiRequest.delete(
      `requisitions/beneficiaries/${beneficiaryBaseUuid}/payment-methods/${paymentMethodBaseUuid}/`,
    );
  },
};

export const PREFERRED_VENDORS_API = {
  fetchPreferredVendors: async ({
    itemBaseUuid,
    search,
    ordering,
  }: {
    itemBaseUuid: string;
    search?: string;
    ordering?: string;
  }) => {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);

    const query = params.toString();
    const response = await apiRequest.get(
      `items/${itemBaseUuid}/preferred-vendors/${query ? `?${query}` : ""}`,
    );
    return response.data as IPreferredVendor[];
  },

  createPreferredVendor: async ({
    itemBaseUuid,
    data,
  }: {
    itemBaseUuid: string;
    data: IPreferredVendorFormData;
  }) => {
    const response = await apiRequest.post(`items/${itemBaseUuid}/preferred-vendors/`, data);
    return response.data as IPreferredVendor;
  },

  fetchPreferredVendorByUuid: async ({
    itemBaseUuid,
    preferredVendorBaseUuid,
  }: {
    itemBaseUuid: string;
    preferredVendorBaseUuid: string;
  }) => {
    const response = await apiRequest.get(
      `items/${itemBaseUuid}/${preferredVendorBaseUuid}/preferred-vendors/`,
    );
    return response.data as IPreferredVendor;
  },

  updatePreferredVendor: async ({
    itemBaseUuid,
    preferredVendorBaseUuid,
    data,
  }: {
    itemBaseUuid: string;
    preferredVendorBaseUuid: string;
    data: Partial<IPreferredVendorFormData>;
  }) => {
    const response = await apiRequest.patch(
      `items/${itemBaseUuid}/${preferredVendorBaseUuid}/preferred-vendors/`,
      data,
    );
    return response.data as IPreferredVendor;
  },

  deletePreferredVendor: async ({
    itemBaseUuid,
    preferredVendorBaseUuid,
  }: {
    itemBaseUuid: string;
    preferredVendorBaseUuid: string;
  }) => {
    await apiRequest.delete(`items/${itemBaseUuid}/${preferredVendorBaseUuid}/preferred-vendors/`);
  },
};
