import {defineEndpoint} from "./_base";

import {IUser} from "#/_types/api.types";

export interface INote {
  id: number;
  owner: IUser;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  is_active: boolean;
  base_uuid: string;
  external_base_uuid: string;
  title: string;
  content: string;
  is_pinned: boolean;
  created_by: number;
  updated_by: number;
}

export interface INoteFormData {
  deleted_at?: string | null;
  is_active?: boolean;
  title: string;
  content: string;
  is_pinned?: boolean;
}

export const NOTES_API = defineEndpoint<INote, INoteFormData>("/institution/notes/");
