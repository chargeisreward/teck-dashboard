export function formatFinancial(value, decimals = 2) {
  if (value == null || Number.isNaN(value)) return "-";
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatCurrency(value, decimals = 2) {
  if (value == null || Number.isNaN(value)) return "-";
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return `$${formatFinancial(value, decimals)}`;
}
