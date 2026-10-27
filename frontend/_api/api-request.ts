import axios, {
  InternalAxiosRequestConfig,
  AxiosRequestConfig,
  AxiosHeaders,
  RawAxiosRequestHeaders,
} from "axios";

import handleError from "./api-error";

import {store} from "@/store";
import {logoutStart, setAccessToken, setRefreshToken} from "@/store/auth/actions";
import {ILoginResponse} from "#/_types/types.utils";

import {setOfflineAfterRequest} from "@/store/miscellaneous/actions";
import {getSliceState} from "@/store/get-slice-state";
import {getModuleAuthContext} from "@/platform/v1/utils/auth.utils";

const isSystemStandalone = process.env.NEXT_PUBLIC_SUPRALEDGER_SYSTEM_MODE === "STANDALONE";

export const baseURL = isSystemStandalone
  ? process.env.NEXT_PUBLIC_API_URL!
  : process.env.NEXT_PUBLIC_SUPRALEDGER_BASE_API_URL!;

const axiosJsonInstance = axios.create({
  baseURL,
  timeout: 30000,
  validateStatus: (status) => status !== 401,
});

type BuildHeadersParams = {
  initialHeaders?:
    | InternalAxiosRequestConfig["headers"]
    | AxiosRequestConfig["headers"]
    | RawAxiosRequestHeaders;
};

type ModuleAccessState = {
  supraledgerExternalUserId?: string | null;
  hostProfileId?: string | null;
};

const resolveModuleAuthFromHost = () => {
  const authState = getSliceState("auth");
  const {moduleAuth, moduleAccess} = getModuleAuthContext<typeof authState, ModuleAccessState>(
    "supraledger",
    {
      moduleAuth: authState,
    },
  );

  return {
    accessToken: moduleAuth?.accessToken ?? "",
    refreshToken: moduleAuth?.refreshToken ?? "",
    supraledgerExternalUserId: moduleAccess?.supraledgerExternalUserId ?? null,
    hostProfileId: moduleAccess?.hostProfileId ?? null,
  };
};

export const buildHeaders = ({initialHeaders}: BuildHeadersParams = {}): AxiosHeaders => {
  const headers = AxiosHeaders.from(initialHeaders as any);

  if (isSystemStandalone) {
    const token = getSliceState("auth")?.accessToken;

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  } else {
    const supraledgerAPIKey = process.env.NEXT_PUBLIC_ACCOUNTING_API_KEY;
    const supraledgerExternalUserId = resolveModuleAuthFromHost()?.supraledgerExternalUserId;
    const hostProfileId = resolveModuleAuthFromHost()?.hostProfileId;

    if (!supraledgerAPIKey || !supraledgerExternalUserId || !hostProfileId) {
      console.error(supraledgerAPIKey, supraledgerExternalUserId, hostProfileId);
      throw new Error("Missing Supraledger authentication credentials");
    }

    headers.set("x-api-key", supraledgerAPIKey);
    headers.set("x-external-user-uuid", supraledgerExternalUserId);
    headers.set("x-internal-user-uuid", hostProfileId);
  }

  return headers;
};

axiosJsonInstance.interceptors.request.use((config) => {
  config.headers = buildHeaders({
    initialHeaders: config.headers,
  });

  return config;
});
let isRefreshing = false;

type Subscriber = (token: string) => void;
let subscribers: Subscriber[] = [];

function onRefreshed(token: string) {
  subscribers.forEach((callback) => callback(token));
  subscribers = [];
}

function addSubscriber(callback: Subscriber) {
  subscribers.push(callback);
}

// Handle protocol correction (optional)
axiosJsonInstance.interceptors.request.use(
  (config) => {
    if (config.url && config.url.startsWith("http")) {
      let protocol;
      if (process.env.NEXT_PUBLIC_USE_HTTP) {
        protocol = "http:";
      } else if (process.env.NODE_ENV === "production") {
        protocol = "https:";
      } else {
        protocol = window.location.protocol;
      }
      const [_, currentHref] = config.url.split("//");
      config.url = `${protocol}//${currentHref}`;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

axiosJsonInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error: any) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Handle NO INTERNET connection
    if (!navigator.onLine || error.message === "Network Error") {
      console.warn("[Network] Offline detected after API request", error);
      store.dispatch(setOfflineAfterRequest(true));

      return Promise.reject(error);
    }

    // Handle 401 token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = getSliceState("auth")?.refreshToken;

      if (!refreshToken || originalRequest.url?.endsWith("/user/token/refresh")) {
        if (typeof window !== "undefined") {
          store.dispatch(logoutStart());
        }

        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve) => {
          addSubscriber((token: string) => {
            if (!originalRequest.headers) {
              originalRequest.headers = new axios.AxiosHeaders();
            }
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(axiosJsonInstance(originalRequest));
          });
        });
      }

      isRefreshing = true;
      try {
        const response = await getNewRefreshToken(refreshToken);

        const {access, refresh} = (response.data as ILoginResponse).tokens;

        store.dispatch(setAccessToken(access));
        store.dispatch(setRefreshToken(refresh));

        axiosJsonInstance.defaults.headers.common["Authorization"] = `Bearer ${access}`;
        originalRequest.headers["Authorization"] = `Bearer ${access}`;
        onRefreshed(access);

        return axiosJsonInstance(originalRequest);
      } catch (err) {
        store.dispatch(logoutStart());

        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }

    console.error("API request error:", error);

    const errorMessage = error.response?.data?.detail || "Unknown error occurred";

    return Promise.reject(new Error(errorMessage));
  },
);

export async function getNewRefreshToken(refreshToken: string) {
  const response = await axios.post(
    `${process.env.NEXT_PUBLIC_API_URL}/user/token/refresh/`,
    {refresh: refreshToken},
    {headers: {"Content-Type": "application/json"}},
  );

  return response;
}

export const apiRequest = async (
  endpoint: string,
  method: string,
  data: any = null,
  customHeaders: object = {},
  extraConfig: object = {},
): Promise<any> => {
  try {
    const normalizedEndpoint = endpoint.startsWith("/") ? endpoint.slice(1) : endpoint;
    const isFormData = data instanceof FormData;

    const config: any = {
      url: normalizedEndpoint,
      method: method.toUpperCase(),
      headers: {
        ...customHeaders,
        ...(isFormData ? {} : {"Content-Type": "application/json"}),
      },
      data: ["POST", "PUT", "PATCH"].includes(method.toUpperCase()) ? data : undefined,
      params: method.toUpperCase() === "GET" && data && !isFormData ? data : undefined,
      ...extraConfig,
    };

    const response = await axiosJsonInstance(config);

    if (getSliceState("miscellaneous")?.offlineAfterRequest) {
      store.dispatch(setOfflineAfterRequest(false));
    }

    if (response.status >= 200 && response.status < 300) {
      return response;
    }

    throw response.data;
  } catch (error) {
    if (!navigator.onLine || (error as any)?.message === "Network Error") {
      store.dispatch(setOfflineAfterRequest(true));
    }

    handleError(error);
    throw error;
  }
};

export const apiGet = (
  endpoint: string,
  params: Record<string, unknown> | string | null | undefined = null,
  customHeaders = {},
  extraConfig = {},
) => apiRequest(endpoint, "GET", params, customHeaders, extraConfig);

export const apiPost = (endpoint: string, data: any, customHeaders = {}, extraConfig = {}) =>
  apiRequest(endpoint, "POST", data, customHeaders, extraConfig);

export const apiPut = (endpoint: string, data: any, customHeaders = {}) =>
  apiRequest(endpoint, "PUT", data, customHeaders);

export const apiPatch = (endpoint: string, data: any, customHeaders = {}) =>
  apiRequest(endpoint, "PATCH", data, customHeaders);

export const apiDelete = (endpoint: string, customHeaders = {}) =>
  apiRequest(endpoint, "DELETE", null, customHeaders);

export default {
  get: apiGet,
  post: apiPost,
  put: apiPut,
  patch: apiPatch,
  delete: apiDelete,
};
