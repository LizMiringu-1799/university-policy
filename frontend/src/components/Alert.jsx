/** Inline banner for an error/status message. Renders nothing when `children` is falsy,
 * so callers can pass an empty-string error state directly without an `{error && ...}` guard. */
export default function Alert({ children, variant = "error" }) {
  if (!children) return null;
  return <div className={`alert alert-${variant}`}>{children}</div>;
}
