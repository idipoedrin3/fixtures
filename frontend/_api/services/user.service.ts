import {defineEndpoint} from "./_base";

import {Branch, IPaginatedResponse, IUser, Permission, Role, UserProfile} from "#/_types/api.types";
import {IBaseApprovable} from "#/_types/approvals.types";
import apiRequest, {apiGet} from "../api-request";
const BASE = "approval";

export interface IUserRole extends Role {}

export interface IUserRoleForm {
  name: string;
  description?: string;
  permissions: string[];
}

export const USER_ROLE_API = defineEndpoint<IUserRole, IUserRoleForm>("user/role/");

export const ROLE_PERMISSIONS_API = {
  fetchByRole: async (
    roleBaseUuid: string,
    {
      page = 1,
      categoryBaseUuid,
    }: {
      page?: number;
      categoryBaseUuid?: string;
    } = {},
  ): Promise<IPaginatedResponse<Permission>> => {
    const params = new URLSearchParams({page: page.toString()});

    if (categoryBaseUuid) {
      params.append("permission_category_base_uuid", categoryBaseUuid);
    }

    const response = await apiRequest.get(
      `user/role/${roleBaseUuid}/permissions/?${params.toString()}`,
    );
    return response.data;
  },

  fetchFromUrl: async (url: string): Promise<IPaginatedResponse<Permission>> => {
    const response = await apiRequest.get(url);
    return response.data;
  },

  fetchAllByRole: async (roleBaseUuid: string): Promise<Permission[]> => {
    const permissions: Permission[] = [];
    let page = await ROLE_PERMISSIONS_API.fetchByRole(roleBaseUuid);

    permissions.push(...page.results);

    while (page.next) {
      page = await ROLE_PERMISSIONS_API.fetchFromUrl(page.next);
      permissions.push(...page.results);
    }

    return permissions;
  },
};

export const APPROVAL_TASKS = {
  ...defineEndpoint<IBaseApprovable, {}>("approval/approval-tasks/"),
  async approve(baseUuid: string, comment: string) {
    return await this.api.patch(`approval/approval-tasks/${baseUuid}/approve/`, {comment});
  },
  async reject(baseUuid: string, comment: string) {
    return await this.api.patch(`approval/approval-tasks/${baseUuid}/reject/`, {comment});
  },
  async override(comment: string) {
    return await this.api.patch("approval/over-ride/", {comment});
  },
  async analytics() {
    const res = await this.api.get("approval/tasks-analytics/");

    return res.data;
  },
};

export const PROFILES_API = {
  getPaginated: async (args: any) => {
    const params = new URLSearchParams();
    params.append("page", (args.page ?? 1).toString());
    if (args.search) params.append("search", args.search);
    if (args.branch) params.append("branch", args.branch);
    if (args.role) params.append("role", args.role);
    if (args.status) params.append("status", args.status);
    if (args.institution_role_uuid)
      params.append("institution_role_uuid", args.institution_role_uuid);
    if (args.permission_code) params.append("permission_code", args.permission_code);
    if (args.has_ever_initiated_a_requisition !== undefined) {
      params.append(
        "has_ever_initiated_a_requisition",
        String(args.has_ever_initiated_a_requisition),
      );
    }
    if (args.without_requisition_beneficiary !== undefined) {
      params.append(
        "without_requisition_beneficiary",
        String(args.without_requisition_beneficiary),
      );
    }
    const response = await apiRequest.get(`institution/profile/?${params.toString()}`);
    return response.data as IPaginatedResponse<IProfile>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IProfile>;
  },

  getById: async (profileUuid: string): Promise<IProfile> => {
    const response = await apiRequest.get(`institution/profile/${profileUuid}/`);
    return response.data;
  },

  resetSignature: async (profileUuid: string): Promise<void> => {
    await apiRequest.delete(`institution/profile/${profileUuid}/signature/`);
  },

  resetProfilePhoto: async (profileUuid: string): Promise<void> => {
    await apiRequest.delete(`institution/profile/${profileUuid}/profile-photo/`);
  },
};

export interface IProfile {
  id: number;
  base_uuid: string;
  institution: number;
  bio: string | null;
  signature_base64: string | null;
  profile_photo_base64: string | null;
  reference_code?: string;
  is_active?: boolean;
  is_deleted?: boolean;
  created_at?: string;
  updated_at?: string;
  profile: {
    id: number;
    institutions: number[];
    user: IUser;
  };
}

// Section information
export interface WorkflowSection {
  id: number;
  base_uuid: string;
  name: string;
  description: string;
}

// Core node coming from the API
export interface WorkflowNode {
  id: number;
  children: WorkflowNode[];
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string | null;
  reference_code: string;
  code: string;
  name: string;
  description: string;
  icon: string;
  created_by: string | null;
  updated_by: string | null;
  section: WorkflowSection;
  item: number | null;
}

export const WORKFLOW_API = {
  async fetchSectionItems(): Promise<WorkflowNode[]> {
    const res = await apiGet("/system/direct-access-section-items/");
    return res.data;
  },
};

export interface IBranchAdmin {
  id: number;
  is_deleted: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  base_uuid: string;
  external_base_uuid: string;
  reference_code: string;
  deleted_at: string;
  is_super_admin: boolean;
  created_by?: IUser;
  updated_by?: IUser;
  branch: Branch;
  admin: IUser;
}

export interface IBranchAdminForm {
  branch: string;
  admin: string;
  is_super_admin: boolean;
}

export const BRANCH_ADMIN_API = defineEndpoint<IBranchAdmin, IBranchAdminForm>(
  "/institution/branch-admin/",
);

export interface IPermissionCategory {
  id: number;
  base_uuid: string;
  permission_category_name: string;
  permission_category_description: string;
}

export const USER_PERMISSIONS_API = defineEndpoint<IPermissionCategory, {}>(
  "user/permission-category/",
);

export const USER_SPECIFIC_PERMISSIONS_API = {
  getByUser: async ({userBaseUuid}: {userBaseUuid: string}) => {
    const response = await apiRequest.get(`user/user-permissions/${userBaseUuid}/`);
    return response.data;
  },

  getFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data;
  },

  updateForUser: async ({
    userBaseUuid,
    permissionIds,
  }: {
    userBaseUuid: string;
    permissionIds: number[];
  }) => {
    const response = await apiRequest.post(`user/user-permissions/${userBaseUuid}/`, {
      permission_ids: permissionIds,
    });
    return response.data;
  },
};

export interface IAllowedUserEntry {
  id: number;
  base_uuid: string;
  content_type: number | string;
  object_id: string;
  content_object?: string;
  user: {
    id: number;
    is_deleted?: boolean;
    is_active?: boolean;
    base_uuid: string;
    bio?: string | null;
    profile?: {
      id: number;
      institutions?: number[];
      user?: any;
    };
    reference_code?: string;
    [key: string]: any;
  };
}

export const ALLOWED_USERS_API = {
  fetchAll: async (params: {
    content_type_id?: number | string;
    object_id?: string;
    model_name?: string;
    ordering?: string;
    search?: string;
    page?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.content_type_id) qs.append("content_type_id", String(params.content_type_id));
    if (params.object_id) qs.append("object_id", params.object_id);
    if (params.model_name) qs.append("model_name", params.model_name);
    if (params.ordering) qs.append("ordering", params.ordering);
    if (params.search) qs.append("search", params.search);
    if (params.page) qs.append("page", String(params.page));

    const res = await apiRequest.get(`${BASE}/allowed-users/?${qs.toString()}`);
    return res.data as IPaginatedResponse<IAllowedUserEntry>;
  },

  fetchFromUrl: async ({url}: {url: string}) => {
    const res = await apiRequest.get(url);
    return res.data as IPaginatedResponse<IAllowedUserEntry>;
  },

  addUsers: async (payload: {content_type: number; users: string[]; object_id?: string}) => {
    const res = await apiRequest.post(`${BASE}/allowed-users/`, payload);
    return res.data as IAllowedUserEntry[];
  },
};
