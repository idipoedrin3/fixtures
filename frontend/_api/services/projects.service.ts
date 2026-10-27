import {defineEndpoint} from "./_base";

import {IUser} from "#/_types/api.types";
import {IBaseApprovable} from "#/_types/approvals.types";

export interface IProject extends IBaseApprovable {
  base_uuid: string;
  project_name: string;
  description: string;
  start_date: string;
  end_date: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string;
  project_status: "planned";
  created_by: any;
  updated_by: any;
  institution: any;
  branch: any;
  category: any;
  project_client: {
    id: number;
    name: string;
    customer_type: string;
    address: string;
    phone: string;
    email: string;
    gender: string;
  };
  assignees: {
    assignment_id: number;
    assignee: {
      assignee_name: string;
      assignee_id: string;
    };
    role_played: {
      role_id: string;
      role_base_uuid: string;
      role_name: string;
    };
    assigned_at: string;
  }[];
}

export interface IProjectForm {
  project_name: string;
  description: string;
  start_date: string;
  end_date: string;
  project_status: "planned";
  institution: any;
  branch: any;
  category: any;
  project_client: string;
  assignees: {role_played: string; user: string}[];
}

export interface IProjectMetrics {
  total_expense: string;
  total_revenue: string;
  profit_or_loss: string;
  cash_flow_trend: {
    month: string;
    cash_inflow: string;
    cash_outflow: string;
    activity_type: string;
  }[];
  revenue_expense_trend: {
    month: string;
    revenue: string;
    expense: string;
  }[];
}

export interface IProjectRevenue {
  base_uuid: string;
  reference_code: string;
  amount: string;
  net_amount: string;
  tax_amount: string;
  source_type: string;
  description: string;
  transaction_date: string;
}

export interface IProjectLogs {
  id: number;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string;
  action: string;
  metadata: string;
  created_by: IUser;
  updated_by: IUser;
  project: IProject;
  user: IUser;
}

export const PROJECTS_API = {
  ...defineEndpoint<IProject, IProjectForm>("projects/"),
  async getAnalytics(base_uuid: string): Promise<IProjectMetrics> {
    const res = await this.api.get(`projects/analytics/${base_uuid}/`);

    return res.data;
  },
  async fetchRevenueList(project_uuid: string, query: any) {
    const res = await this.api.get(`projects/revenues/${project_uuid}/`, {params: query});

    return res.data;
  },
  async fetchRevenueListFromUrl({url}: {url: string}) {
    const res = await this.api.get(url);

    return res.data;
  },
  async fetchLogsList(project_uuid: string, query: any) {
    const res = await this.api.get(`projects/logs/${project_uuid}/`, {params: query});

    return res.data;
  },
  async fetchLogsListFromUrl({url}: {url: string}) {
    const res = await this.api.get(url);

    return res.data;
  },
  async downloadReport(project_uuid: string) {
    const res = await fetch(`${this.apiURL}/projects/reports/${project_uuid}/`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${this.accessToken}`,
      },
    });

    return res.blob();
  },
};

export interface IProjectCategory {
  id: string;
  base_uuid: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  deleted_at: string;
}

export interface IProjectCategoryForm {
  name: string;
  description: string;
  institution: string | number;
}

export const PROJECT_CATEGORIES_API = defineEndpoint<IProjectCategory, IProjectCategoryForm>(
  "projects/categories/",
);

export interface IProjectRole {
  id: string;
  base_uuid: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  deleted_at: string;
}

export interface IProjectRoleForm {
  name: string;
  description: string;
  institution: string | number;
}

export const PROJECT_ROLES_API = defineEndpoint<IProjectRole, IProjectRoleForm>("projects/roles/");

export interface IProjectAssignee {
  id: number;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string;
  assigned_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  created_by: number;
  updated_by: number;
  project: number;
  user: IUser;
  role_played: IProjectRole;
}

export interface IProjectAssigneeForm {
  project: string;
  role_played: string;
  user: string;
}

export const PROJECT_ASSIGNEES_API = defineEndpoint<IProjectAssignee, IProjectAssigneeForm>(
  "projects/assignments/",
);
