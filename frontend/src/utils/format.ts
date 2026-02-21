export function formatTime(iso: string | null): string {
  if (!iso) {
    return "-";
  }

  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return "-";
  }

  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
