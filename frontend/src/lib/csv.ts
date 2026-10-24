/** Parse one CSV line into fields, respecting double-quoted fields (with "" escapes). */
export function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let cur = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        cur += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      result.push(cur)
      cur = ''
    } else {
      cur += ch
    }
  }
  result.push(cur)
  return result.map((s) => s.trim())
}

export interface ParsedCsvProduct {
  name: string
  price: number
  category?: string
  stock_qty: number
  kind: 'product'
}

/** Parse "name, price, category, stock_qty" rows, tolerating a header row and quoted fields. */
export function parseProductCsv(text: string): ParsedCsvProduct[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
  if (lines.length === 0) return []

  let rows = lines.map(parseCsvLine)
  const first = rows[0]
  const firstLooksLikeHeader = first.length >= 2 && Number.isNaN(Number(first[1]))
  if (firstLooksLikeHeader) {
    rows = rows.slice(1)
  }

  return rows
    .filter((r) => r[0])
    .map((r) => ({
      name: r[0],
      price: Number(r[1]) || 0,
      category: r[2] || undefined,
      stock_qty: Number(r[3]) || 0,
      kind: 'product' as const,
    }))
}
