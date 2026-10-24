/** Extract a media/API path from a payment/expense note blob. */
export function extractProofUrl(note: string | null | undefined): string | null {
  if (!note) return null
  const match = note.match(/(\/api\/v1\/media\/files\/[^\s|]+)/)
  return match?.[1] ?? null
}

export function proofLabel(note: string | null | undefined): string {
  if (!note) return '—'
  const url = extractProofUrl(note)
  if (!url) return note
  return note.replace(url, '').replace(/\s*\|\s*$/, '').replace(/^\s*\|\s*/, '').trim() || 'Proof attached'
}
