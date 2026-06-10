export function fmtScore(value) {
  if (value === null || value === undefined) return '—';
  return `${(Number(value) * 100).toFixed(1)}`;
}

export function fmtParams(value) {
  if (!value) return '—';
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

export function fmtTime(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value));
}
