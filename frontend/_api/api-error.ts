import {toast} from "sonner";
import z from "zod";

import {capitalizeEachWord} from "#/_api/helpers";
import {capitalize} from "#/_lib/utils";

let tid: number | undefined;

export default function handleError(error: any) {
  if (error && (typeof error === "object" || typeof error === "function")) {
    error.__globalToastHandled = true;
  }

  window.clearTimeout(tid);

  tid = window.setTimeout(() => {
    const payload = error?.response?.data ?? error;

    if (payload?.code === "session_expired") {
      toast.error("Session expired", {
        id: "session-expired",
        description: "Your session has expired. Please log in again.",
      });
      return;
    }

    const backendErrorSchema = z.object({
      success: z.boolean(),
      error_summary: z.string(),
      errors: z.array(
        z.object({
          field: z.string().nullable().optional(),
          message: z.string(),
        }),
      ),
      trace_id: z.string().optional(),
    });

    const parsed = backendErrorSchema.safeParse(payload);

    if (parsed.success) {
      const {error_summary, trace_id, errors} = parsed.data;

      const title = (trace_id ? `${trace_id} - ` : "") + capitalizeEachWord(error_summary);

      if (!errors || errors.length === 0) {
        toast.error(title);
        return;
      }

      errors.forEach((e) => {
        const field = e.field ? capitalizeEachWord(e.field) : null;
        const description = field ? `${field} - ${e.message}` : e.message;

        toast.error(title, {
          description: () =>
            capitalize(description.startsWith("{") ? "Something went wrong." : description),
        });
      });

      return;
    }

    if (typeof payload === "object" && payload !== null) {
      const isError = Object.entries(payload).every(([_, v]) => {
        return Array.isArray(v) && v.every((x) => typeof x === "string");
      });

      if (isError) {
        Object.entries(payload).forEach(([k, v]) => {
          toast.error(capitalize(k), {
            description: () => capitalize(v.join(" ")),
          });
        });
        return;
      }
    }

    toast.error("Something went wrong");

    if (process.env.NODE_ENV === "development") {
      console.error("Unhandled error:", error);
    }
  });
}
