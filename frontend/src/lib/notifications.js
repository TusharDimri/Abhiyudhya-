/* The signed-in user's notifications: the bell and the Notifications page
   share these. A notification's link opens the page to act on; for an org
   admin it can also carry the school to open (_district / _school). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "./api";
import { setOrgScopeFor } from "./orgScope";

export const NOTIFY_ROLES = ["OA", "PR", "VT"];

export const CATEGORY_ICON = {
  issue: "⚠️", maintenance: "🔧", equipment: "🖥️", verification: "🧑‍🎓",
  attendance: "🗓️", guest_lecture: "🎤", leaving: "📄",
};

export function useMyNotifications({ page = 1, pageSize = 8, unread = false, enabled = true, poll = false } = {}) {
  return useQuery({
    queryKey: ["my-notifications", page, pageSize, unread],
    queryFn: async () => (await api.get(
      `/me/notifications?page=${page}&page_size=${pageSize}${unread ? "&unread=1" : ""}`)).data,
    enabled,
    refetchInterval: poll ? 30000 : false,   // the bell checks every 30 seconds
    refetchOnWindowFocus: true,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["my-notifications"] });
  return {
    one: useMutation({ mutationFn: (id) => api.post(`/me/notifications/${id}/read`), onSuccess: done }),
    all: useMutation({ mutationFn: () => api.post("/me/notifications/read-all"), onSuccess: done }),
  };
}

/* Go where the notification points. School params become the org admin's
   District -> School pick on that one list, so it opens on that school. */
export function openLink(link, navigate) {
  if (!link) return;
  const url = new URL(link, window.location.origin);
  const school = url.searchParams.get("_school");
  const district = url.searchParams.get("_district");
  if (school) {
    const resource = url.pathname.split("/")[2];
    const tab = url.searchParams.get("tab");
    setOrgScopeFor(tab && tab !== "view" ? `${resource}:${tab}` : resource, { district_id: district || "", school_id: school });
  }
  url.searchParams.delete("_school");
  url.searchParams.delete("_district");
  navigate(`${url.pathname}${url.search}`);
}

// "just now", "5 min ago", "3 h ago", "2 days ago", then the date
export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  const s = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} day${s < 2 * 86400 ? "" : "s"} ago`;
  return then.toLocaleDateString("en-GB");
}
