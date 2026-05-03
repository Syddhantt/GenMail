// Theme management. Persists choice in localStorage, falls back to system
// preference, applies a `dark` class on <html> for Tailwind's `dark:` variant.
//
// FOUC is prevented by the inline script in index.html which runs before
// React hydrates.

import { useCallback, useEffect, useState } from "react"

export type Theme = "light" | "dark"
const STORAGE_KEY = "genmail-theme"

function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "light"
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === "light" || stored === "dark") return stored
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark")
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    applyTheme(theme)
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // localStorage may be unavailable (private mode); silent fallback.
    }
  }, [theme])

  const setTheme = useCallback((next: Theme) => setThemeState(next), [])
  const toggleTheme = useCallback(
    () => setThemeState((t) => (t === "light" ? "dark" : "light")),
    []
  )

  return { theme, setTheme, toggleTheme }
}
