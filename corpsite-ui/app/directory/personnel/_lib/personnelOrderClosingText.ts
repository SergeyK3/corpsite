/** Remove only the retired automatic closing, preserving other instructions. */
export function withoutAutomaticOrderClosing(value: string | null | undefined): string | null {
  let text = String(value || "").trim();
  const phrases = [
    "Контроль за исполнением приказа оставляю за собой",
    "Бұйрықты орындалу бақылауын өзімде қалдырамын",
    "Бұйрықтың орындалуын бақылауды өзіме қалдырамын",
  ];
  for (const phrase of phrases) text = text.replace(new RegExp(phrase.replace(/\s+/g, "\\s+") + "[.]?", "giu"), "");
  return text.trim() || null;
}
