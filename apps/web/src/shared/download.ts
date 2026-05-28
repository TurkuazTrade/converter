export function filenameFromContentDisposition(header: string | undefined, fallback: string) {
  if (!header) return fallback;

  const encoded = header.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    return decodeURIComponent(encoded.replace(/^"|"$/g, ''));
  }

  const plain = header.match(/filename="?([^";]+)"?/i)?.[1];
  if (plain) {
    return decodeURIComponent(plain);
  }

  return fallback;
}

export function downloadBlob(data: Blob, filename: string) {
  const url = URL.createObjectURL(data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function downloadErrorMessage(error: unknown, fallback: string) {
  const data = (error as { response?: { data?: unknown } }).response?.data;
  const detail = await responseDetail(data);
  return detail || fallback;
}

async function responseDetail(data: unknown): Promise<string | null> {
  if (data instanceof Blob) {
    const text = await data.text();
    if (!text.trim()) return null;
    try {
      return detailText(JSON.parse(text));
    } catch {
      return text;
    }
  }
  return detailText(data);
}

function detailText(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object') return null;
  const detail = (value as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => detailText(item) || String(item)).join(', ');
  return null;
}
