/** Render an ISO timestamp as a short localized date ("Aug 14, 2026"), or "" if absent. */
export function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
