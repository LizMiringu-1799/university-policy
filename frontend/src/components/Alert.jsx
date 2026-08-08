export default function Alert({ children, variant = "error" }) {
  if (!children) return null;
  return <div className={`alert alert-${variant}`}>{children}</div>;
}
