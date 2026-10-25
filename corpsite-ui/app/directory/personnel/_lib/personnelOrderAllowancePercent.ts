export function allowancePercentError(value: string): string | null {
  const text = value.trim();
  if (!/^\d+$/.test(text) || Number(text) < 1 || Number(text) > 100) {
    return "Укажите целый процент доплаты от 1 до 100.";
  }
  return null;
}
