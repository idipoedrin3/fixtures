import {Branch, IBusinessDocument, ITax} from "#/_types/api.types";
import {IBaseApprovable} from "#/_types/approvals.types";
import {defineEndpoint} from "./_base";

export interface ITaxRegistration extends IBaseApprovable {
  branch: Branch;
  tax: ITax;
  registration_number: string;
  reference_code: string;
  effective_from_date: string;
  effective_to_date: string;
  documents: IBusinessDocument[];
}

export interface ITaxRegistrationForm {
  branch: number | string;
  tax: number | string;
  registration_number: string;
  effective_from_date: string;
  effective_to_date: string;
  documents?: string[];
}

export const TAX_REGISTRATIONS_API = defineEndpoint<ITaxRegistration, ITaxRegistrationForm>(
  "/taxation/tax-registration/",
);
