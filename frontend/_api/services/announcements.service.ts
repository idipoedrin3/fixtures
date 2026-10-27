import {defineEndpoint} from "./_base";

import {IBaseApprovable} from "#/_types/approvals.types";

export interface IAnnouncement extends IBaseApprovable {
  base_uuid: string;
  id: number;
  title: string;
  content: string;
  requires_acknowledgment: boolean;
  created_at?: string;
  is_targetted_to_all_users: boolean;
  is_role_targetted: boolean;
  target_users: {id: number; name: string}[];
  target_roles: {id: number; name: string}[];
}

export interface IAnnouncementFormData {
  title: string;
  content: string;
  requires_acknowledgment: boolean;
  is_targetted_to_all_users: boolean;
  is_role_targetted: boolean;
  target_users_ids: (number | string)[];
  target_roles_ids: (number | string)[];
}

export const ANNOUNCEMENTS_API = defineEndpoint<IAnnouncement, IAnnouncementFormData>(
  "institution/announcements/",
);

export interface IAcknowledgment {
  id: number;
  user: number;
  announcement: IAnnouncement;
  acknowledged: boolean;
  acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface IAcknowledgmentFormData {
  acknowledged: boolean;
  user: number;
  announcement: number;
}

export const ACKNOWLEDGMENTS_API = defineEndpoint<IAcknowledgment, IAcknowledgmentFormData>(
  "institution/acknowledgments/",
);
