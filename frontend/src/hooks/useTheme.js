import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "upman_theme";

/** The theme to render on first paint: the user's saved choice, or their OS preference
 * if they've never toggled it here. */
function getInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Light/dark theme state, persisted to localStorage and mirrored onto
 * `<html data-theme>` so theme.css's selectors pick it up. Read by ThemeToggle.
 */
export function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }, []);

  return { theme, toggleTheme };
}
