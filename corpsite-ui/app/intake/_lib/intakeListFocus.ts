export function focusIntakeListEditor(testId: string): void {
  window.requestAnimationFrame(() => {
    const editors = document.querySelectorAll<HTMLElement>(`[data-testid="${testId}"]`);
    for (const editor of editors) {
      if (!editor.getClientRects().length) continue;
      const control = editor.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
        "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
      );
      if (control) {
        control.focus();
        return;
      }
    }
  });
}
