import type { Role } from '../types/api'

const ROLE_RANK: Record<Role, number> = {
  warehouse: 0,
  support: 1,
  sales: 1,
  admin: 2,
  super_admin: 3,
}

export function roleAtLeast(role: Role | null | undefined, minimum: Role): boolean {
  if (!role) return false
  return ROLE_RANK[role] >= ROLE_RANK[minimum]
}

export function roleLabel(role: Role): string {
  return role
    .split('_')
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
}
