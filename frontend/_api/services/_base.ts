import apiRequest from "../api-request";
import {getAllSelectedBranchUUIDs} from "../helpers";

import {IPaginatedResponse} from "#/_types/api.types";
import {getSliceState} from "@/store/get-slice-state";
import {toParams} from "#/_lib/utils";

export function defineEndpoint<Result, Payload>(baseURL: string = "") {
  return {
    api: apiRequest,
    apiURL: process.env.NEXT_PUBLIC_API_URL || "",
    get accessToken() {
      const token = getSliceState("auth")?.accessToken;

      return token || "";
    },
    getPaginated({query, page}: {query?: Record<string, any>; page?: number} = {}) {
      return this.fetch({...query, page});
    },

    getPaginatedFromUrl({url}: {url: string}) {
      return this.fetchFromUrl({url});
    },

    fetch: async (query: Record<string, any> = {}) => {
      const params = toParams({
        ...query,
      });

      const response = await apiRequest.get(`${baseURL}?${params.toString()}`);
      return response.data;
    },

    fetchFromUrl: async ({url}: {url: string}) => {
      const response = await apiRequest.get(url);

      return response.data as IPaginatedResponse<Result>;
    },

    create: async (data: Payload, useFormData = true) => {
      let formdata: any = data;

      if (useFormData) {
        formdata = new FormData();
        Object.keys(data as any).forEach((key) => {
          // @ts-ignore
          formdata.append(key, data[key] || ("" as any));
        });
      }
      const response = await apiRequest.post(`${baseURL}`, formdata);

      return response.data as Result;
    },

    update: async (base_uuid: string, data: Partial<Payload>) => {
      const response = await apiRequest.patch(`${baseURL}${base_uuid}/`, data);

      return response.data as Result;
    },

    deleteByUUID: async (base_uuid: string = "") => {
      const response = await apiRequest.delete(`${baseURL}${base_uuid}/`);

      return response.data;
    },

    fetchOne: async (base_uuid: string) => {
      const response = await apiRequest.get(`${baseURL}${base_uuid}/`);

      return response.data as Result;
    },

    async download(
      url: string,
      data: Record<string, any>,
      method: "POST" | "GET" = "POST",
      headers: Record<string, string> = {},
    ) {
      const res = await fetch(`${this.apiURL}/${url}`, {
        method,
        body: method === "POST" ? JSON.stringify(data) : null,
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          ...headers,
        },
      });
      return await res.blob();
    },
  };
}
