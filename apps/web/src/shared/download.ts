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
