export const UI_THEME_STORAGE_KEY = "corpsite_ui_theme";
export const UI_THEME_CHANGED_EVENT = "corpsite-ui-theme-changed";

export function resetLearningThemeAfterLogin(): void {
  if (process.env.NEXT_PUBLIC_LEARNING_STAND !== "1") return;
  try {
    window.localStorage.setItem(UI_THEME_STORAGE_KEY, "document");
  } catch {
    // The current page still switches to light mode when storage is unavailable.
  }
  document.documentElement.classList.remove("dark");
  window.dispatchEvent(new Event(UI_THEME_CHANGED_EVENT));
}
