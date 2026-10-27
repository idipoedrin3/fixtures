import {clsx, type ClassValue} from "clsx";
import {twMerge} from "tailwind-merge";
import {format} from "date-fns";
import {toast} from "sonner";

import {FEATURE_CODES} from "../_constants/features.enum";

import apiRequest from "./api-request";

import {IPaginatedResponse, IPermission, Role} from "#/_types/api.types";
import {ICountry, IInventoryItemImage, IInventoryItemImageFormData} from "#/_types/types.utils";
import {getSliceState} from "@/store/get-slice-state";
import {FileEntry} from "../_lib/file-utils";
import {
  IBudget,
  IBudgetFormData,
  IBudgetProposal,
  IBudgetProposalExpanded,
  IBudgetProposalFormData,
  IBudgetProposalItem,
  IBudgetProposalItemAllocation,
  IBudgetProposalItemAllocationFormData,
  IBudgetProposalItemFormData,
  IBudgetType,
  IBudgetTypeFormData,
} from "../_types/email";

let channel: BroadcastChannel | null = null;

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function capitalizeEachWord(str: string) {
  return str
    ?.replaceAll("_", " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function hexToHSL(hex: string): string {
  hex = hex.replace("#", "");
  const r = Number.parseInt(hex.substring(0, 2), 16) / 255;
  const g = Number.parseInt(hex.substring(2, 4), 16) / 255;
  const b = Number.parseInt(hex.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b),
    min = Math.min(r, g, b);
  let h = 0,
    s,
    l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;

    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      case b:
        h = (r - g) / d + 4;
        break;
    }
    h /= 6;
  } else {
    s = 0;
  }

  h = Math.round(h * 360);
  s = Math.round(s * 100);
  l = Math.round(l * 100);

  return `${h} ${s}% ${l}%`;
}

export function getDefaultInstitutionId() {
  if (typeof window !== "undefined") {
    const selectedInstitution = getSliceState("auth")?.selectedInstitution.value;

    if (selectedInstitution) {
      return selectedInstitution.base_uuid;
    }
    // Fallback to the first Institution in InstitutionsAttached
    const InstitutionsAttached = getSliceState("auth")?.InstitutionsAttached.value;
    const InstitutionBaseUuid = InstitutionsAttached?.length
      ? InstitutionsAttached[0].base_uuid
      : null;
    return InstitutionBaseUuid;
  }
}

export function getCurrentBranchId() {
  const selectedBranches = getSliceState("auth")?.selectedBranches.value;

  if (selectedBranches && selectedBranches.length > 0) {
    return selectedBranches[0].id;
  }

  return null;
}

export const getAllSelectedBranchUUIDs = () =>
  (getSliceState("auth")?.selectedBranches.value ?? [])
    .map((branch) => branch?.base_uuid)
    .filter(Boolean);

export function formatTransactionDate(dateString: any) {
  try {
    const date = new Date(dateString);

    return format(date, "MMMM dd, yyyy h:mm a");
  } catch {
    return dateString;
  }
}

export function isFeatureCode(code: string): code is FEATURE_CODES {
  return Object.values(FEATURE_CODES).includes(code as FEATURE_CODES);
}

export function hasFeature(code: FEATURE_CODES): boolean {
  try {
    const state = getSliceState("auth");
    const ins = state?.selectedInstitution?.value;

    if (!ins) return false;

    const featureStatuses = ins.feature_statuses ?? [];

    return Array.isArray(featureStatuses) && featureStatuses.includes(code);
  } catch (error) {
    console.error(error);

    return false;
  }
}

export function hasPermission(permissionCode: string): boolean {
  try {
    const authState = getSliceState("auth");
    const userData = authState?.user.value;

    if (!userData) return false;

    // Check if user is the Institution owner
    const selectedInstitution = authState.selectedInstitution?.value;

    if (!selectedInstitution) return false;

    if (isFeatureCode(permissionCode)) {
      return hasFeature(permissionCode);
    }

    if (selectedInstitution.institution_owner_id?.toString() === userData?.id?.toString()) {
      return true;
    }

    const temporaryPermissions = authState.temporaryPermissions;

    // Check temporary permissions first
    const hasTemporaryPermission = temporaryPermissions.some(
      (permission: IPermission) => permission.permission_code === permissionCode,
    );

    if (hasTemporaryPermission) {
      return true;
    }

    // Otherwise, check user's own permissions
    return userData.permissions.some((perm: string) => perm === permissionCode) || false;
  } catch (error) {
    // console.error("Error checking permission:", error);

    return false;
  }
}

export function extractRequiredPermissions(
  userRoles: Role[],
  requiredPermissionCodes: string[],
): IPermission[] {
  const requiredPermissions: IPermission[] = [];

  userRoles.forEach((role) => {
    const matchingPermissions = role.permissions_details?.filter((permission) =>
      requiredPermissionCodes.includes(permission.permission_code),
    );

    if (matchingPermissions && matchingPermissions.length > 0) {
      // Create a new role object with only the required permissions
      requiredPermissions.push(...matchingPermissions);
    }
  });

  return requiredPermissions;
}

export function hasAnyRequiredPermissions(
  userRoles: Role[],
  requiredPermissionCodes: string[],
): boolean {
  return userRoles.some((role) =>
    role.permissions_details?.some((permission: any) =>
      requiredPermissionCodes.includes(permission.permission_code),
    ),
  );
}

export const fetchAndSetData = async <T>(
  fetchFn: () => Promise<any>,
  setFn: (data: T) => void,
  setErrorFn?: (msg: string) => void,
  errorMsg = "Failed to fetch data",
  extractData: (res: any) => T = (res) => res.data,
) => {
  try {
    const response = await fetchFn();
    const data = extractData(response);

    setFn(data);
  } catch (error) {
    // console.error(errorMsg, error);
    if (setErrorFn) {
      setErrorFn(errorMsg);
    }
  }
};

export const countryAPI = {
  fetchPage: async ({url, search = ""}: {url?: string; search?: string} = {}) => {
    const params = new URLSearchParams({page_size: "20"});

    if (search) params.set("search", search);

    const response = await apiRequest.get(url || `system/countries/?${params.toString()}`);

    return response.data as {
      count: number;
      next: string | null;
      previous: string | null;
      results: ICountry[];
    };
  },
};

export const GEOLOCATION_API = {
  reverse: async ({latitude, longitude}: {latitude: number; longitude: number}) =>
    await fetch(
      `https://api.geoapify.com/v1/geocode/reverse?lat=${latitude}&lon=${longitude}&apiKey=12a8608da7914f4c96cbbc76c7ca954c`,
    ),

  autocomplete: async ({query, limit = 5}: {query: string; limit?: number}) =>
    await fetch(
      `https://api.geoapify.com/v1/geocode/autocomplete?text=${encodeURIComponent(
        query,
      )}&apiKey=12a8608da7914f4c96cbbc76c7ca954c&limit=${limit}`,
    ),

  search: async ({location}: {location: string}) =>
    await fetch(
      `https://api.geoapify.com/v1/geocode/search?text=${encodeURIComponent(
        location,
      )}&apiKey=12a8608da7914f4c96cbbc76c7ca954c&limit=1`,
    ),
};

export const getRoles = async (): Promise<Role[]> => {
  const response = await apiRequest.get("user/role/");

  if (response.data && response.data.results) {
    return response.data.results || [];
  }

  return Array.isArray(response.data) ? response.data : [];
};

export const showSuccessToast = (message: string) => {
  toast.success(message);
};

export function initBroadcastChannel(onMessage: (data: {type: string; payload?: any}) => void) {
  if (typeof window === "undefined") return;

  if (!channel || channel.name !== "MAIN_APP_CHANNEL") {
    channel = new BroadcastChannel("MAIN_APP_CHANNEL");
  }

  channel.onmessage = (event) => onMessage(event.data);

  return channel;
}

/* -------------------- INVENTORY ITEM IMAGES -------------------- */
export const INVENTORY_ITEM_IMAGES_API = {
  fetchAll: async ({inventoryItemUuid, page = 1}: {inventoryItemUuid: string; page?: number}) => {
    const params = new URLSearchParams();

    params.append("inventory_item_uuid", inventoryItemUuid);
    params.append("page", page.toString());
    const response = await apiRequest.get(`items/inventory-item-images/?${params.toString()}`);

    return response.data as IPaginatedResponse<IInventoryItemImage>;
  },

  fetchAllFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);

    return response.data as IPaginatedResponse<IInventoryItemImage>;
  },

  create: async ({
    inventoryItemUuid,
    payload,
  }: {
    inventoryItemUuid: string;
    payload: IInventoryItemImageFormData[];
  }) => {
    const params = new URLSearchParams();

    params.append("inventory_item_uuid", inventoryItemUuid);
    const response = await apiRequest.post(
      `items/inventory-item-images/?${params.toString()}`,
      payload,
    );

    return response.data as IInventoryItemImage[];
  },

  fetchById: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`items/inventory-item-images/details/${baseUuid}/`);

    return response.data as IInventoryItemImage;
  },

  update: async ({
    baseUuid,
    payload,
  }: {
    baseUuid: string;
    payload: Partial<{image_name: string; image: FileEntry; is_default: boolean}>;
  }) => {
    const response = await apiRequest.patch(
      `items/inventory-item-images/detail/${baseUuid}/`,
      payload,
    );

    return response.data as IInventoryItemImage;
  },

  delete: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`items/inventory-item-images/detail/${baseUuid}/`);
  },
};

export const BUDGETS_API = {
  // ─── Budgets ────────────────────────────────────────────────

  fetchBudgets: async ({
    page = 1,
    search = "",
    ...rest
  }: {
    page?: number;
    search?: string;
    [key: string]: any;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      search,
    });
    Object.entries(rest).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      params.append(key, String(value));
    });

    const response = await apiRequest.get(`budget/?${params.toString()}`);
    return response.data as IPaginatedResponse<IBudget>;
  },

  fetchBudgetsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBudget>;
  },

  createBudget: async ({data}: {data: IBudgetFormData}) => {
    const response = await apiRequest.post(`budget/`, data);
    return response.data as IBudget;
  },

  fetchBudgetById: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`budget/budgets/${baseUuid}/`);
    return response.data as IBudget;
  },

  updateBudget: async ({baseUuid, data}: {baseUuid: string; data: Partial<IBudgetFormData>}) => {
    const response = await apiRequest.patch(`budget/budgets/${baseUuid}/`, data);
    return response.data as IBudget;
  },

  deleteBudget: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`budget/budgets/${baseUuid}/`);
  },

  // ─── Budget Proposals ────────────────────────────────────────────────

  fetchBudgetProposals: async ({
    page = 1,
    search = "",
    ...rest
  }: {
    page?: number;
    search?: string;
    [key: string]: any;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      search,
    });
    Object.entries(rest).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      params.append(key, String(value));
    });

    const response = await apiRequest.get(`budget/budget-proposals/?${params.toString()}`);
    return response.data as IPaginatedResponse<IBudgetProposal>;
  },

  fetchBudgetProposalsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBudgetProposal>;
  },

  createBudgetProposal: async ({data}: {data: IBudgetProposalFormData}) => {
    const response = await apiRequest.post(`budget/budget-proposals/`, data);
    return response.data as IBudgetProposal;
  },

  fetchBudgetProposalById: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`budget/budget-proposals/${baseUuid}/`);
    return response.data as IBudgetProposal;
  },

  fetchBudgetProposalForEdit: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`budget/budget-proposals/${baseUuid}/`, {
      include: "items.allocations",
    });
    const proposal = response.data as IBudgetProposalExpanded;
    if (
      proposal.base_uuid !== baseUuid ||
      !Array.isArray(proposal.items) ||
      proposal.items.some((item) => !Array.isArray(item.allocations))
    ) {
      throw new Error("The complete proposal could not be loaded. Please try again.");
    }
    return proposal;
  },

  updateBudgetProposal: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IBudgetProposalFormData>;
  }) => {
    const response = await apiRequest.patch(`budget/budget-proposals/${baseUuid}/`, data);
    return response.data as IBudgetProposal;
  },

  deleteBudgetProposal: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`budget/budget-proposals/${baseUuid}/`);
  },

  // ─── Budget Proposal Items ────────────────────────────────────────────────

  fetchBudgetProposalItems: async ({
    page = 1,
    search = "",
    ...rest
  }: {
    page?: number;
    search?: string;
    [key: string]: any;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      search,
    });
    Object.entries(rest).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      params.append(key, String(value));
    });

    const response = await apiRequest.get(`budget/proposal-items/?${params.toString()}`);
    return response.data as IPaginatedResponse<IBudgetProposalItem>;
  },

  fetchBudgetProposalItemsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBudgetProposalItem>;
  },

  createBudgetProposalItem: async ({data}: {data: IBudgetProposalItemFormData}) => {
    const response = await apiRequest.post(`budget/proposal-items/`, data);
    return response.data as IBudgetProposalItem;
  },

  fetchBudgetProposalItemById: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`budget/proposal-items/${baseUuid}/`);
    return response.data as IBudgetProposalItem;
  },

  updateBudgetProposalItem: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IBudgetProposalItemFormData>;
  }) => {
    const response = await apiRequest.patch(`budget/proposal-items/${baseUuid}/`, data);
    return response.data as IBudgetProposalItem;
  },

  deleteBudgetProposalItem: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`budget/proposal-items/${baseUuid}/`);
  },

  // ─── Budget Proposal Item Allocations ────────────────────────────────────────────────

  fetchBudgetProposalItemAllocations: async ({
    baseUuid,
    page = 1,
    search = "",
    ...rest
  }: {
    baseUuid: string;
    page?: number;
    search?: string;
    [key: string]: any;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      search,
    });
    Object.entries(rest).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      params.append(key, String(value));
    });

    const response = await apiRequest.get(
      `budget/proposal-items/${baseUuid}/allocations/?${params.toString()}`,
    );
    return response.data as IPaginatedResponse<IBudgetProposalItemAllocation>;
  },

  fetchBudgetProposalItemAllocationsFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBudgetProposalItemAllocation>;
  },

  createBudgetProposalItemAllocation: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: IBudgetProposalItemAllocationFormData;
  }) => {
    const response = await apiRequest.post(`budget/proposal-items/${baseUuid}/allocations/`, data);
    return response.data as IBudgetProposalItemAllocation;
  },

  fetchBudgetProposalItemAllocationById: async ({
    baseUuid,
    allocationUuid,
  }: {
    baseUuid: string;
    allocationUuid: string;
  }) => {
    const response = await apiRequest.get(
      `budget/proposal-items/${baseUuid}/allocations/${allocationUuid}/`,
    );
    return response.data as IBudgetProposalItemAllocation;
  },

  updateBudgetProposalItemAllocation: async ({
    baseUuid,
    allocationUuid,
    data,
  }: {
    baseUuid: string;
    allocationUuid: string;
    data: Partial<IBudgetProposalItemAllocationFormData>;
  }) => {
    const response = await apiRequest.patch(
      `budget/proposal-items/${baseUuid}/allocations/${allocationUuid}/`,
      data,
    );
    return response.data as IBudgetProposalItemAllocation;
  },

  deleteBudgetProposalItemAllocation: async ({
    baseUuid,
    allocationUuid,
  }: {
    baseUuid: string;
    allocationUuid: string;
  }) => {
    await apiRequest.delete(`budget/proposal-items/${baseUuid}/allocations/${allocationUuid}/`);
  },

  // ─── Budget Types ────────────────────────────────────────────────

  fetchBudgetTypes: async ({
    page = 1,
    search = "",
    ...rest
  }: {
    page?: number;
    search?: string;
    [key: string]: any;
  }) => {
    const params = new URLSearchParams({
      page: page.toString(),
      search,
    });
    Object.entries(rest).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      params.append(key, String(value));
    });

    const response = await apiRequest.get(`budget/types/?${params.toString()}`);
    return response.data as IPaginatedResponse<IBudgetType>;
  },

  fetchBudgetTypesFromUrl: async ({url}: {url: string}) => {
    const response = await apiRequest.get(url);
    return response.data as IPaginatedResponse<IBudgetType>;
  },

  createBudgetType: async ({data}: {data: IBudgetTypeFormData}) => {
    const response = await apiRequest.post(`budget/types/`, data);
    return response.data as IBudgetType;
  },

  fetchBudgetTypeById: async ({baseUuid}: {baseUuid: string}) => {
    const response = await apiRequest.get(`budget/types/${baseUuid}/`);
    return response.data as IBudgetType;
  },

  updateBudgetType: async ({
    baseUuid,
    data,
  }: {
    baseUuid: string;
    data: Partial<IBudgetTypeFormData>;
  }) => {
    const response = await apiRequest.patch(`budget/types/${baseUuid}/`, data);
    return response.data as IBudgetType;
  },

  deleteBudgetType: async ({baseUuid}: {baseUuid: string}) => {
    await apiRequest.delete(`budget/types/${baseUuid}/`);
  },
};
