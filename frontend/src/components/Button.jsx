/**
 * Themed button. `variant` selects the CSS class ("primary" | "secondary" | ...);
 * everything else (onClick, type, disabled, ...) passes straight through to <button>.
 */
export default function Button({ variant = "primary", children, ...props }) {
  return (
    <button className={`btn btn-${variant}`} {...props}>
      {children}
    </button>
  );
}
