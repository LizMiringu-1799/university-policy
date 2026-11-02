// Mirrors backend/app/utils/filetypes.py's ALLOWED_EXTENSIONS. Kept in sync by hand
// rather than fetched from the API: it only drives the upload <input accept> hint and a
// label, neither of which is authoritative — the backend re-validates every upload
// regardless of what the browser's file picker was told to filter for.
export const ACCEPTED_EXTENSIONS =
  ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp";
