/** Exact public account summary returned by Django accounts/views.py::_user_summary. */
export interface AccountSummary {
  email: string
  role: 'STUDENT' | 'ADMIN'
  email_verified: boolean
  student_association: 'linked' | 'unlinked'
  capabilities?: string[]
}
export type Session = { status: 'authenticated'; user: AccountSummary } | { status: 'anonymous' }
export type AccessDecision = 'allow' | 'login' | 'wrong-role' | 'unverified' | 'unlinked' | 'permissions-missing'
export function parseAccountSummary(value: unknown): AccountSummary {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('ACCOUNT_CONTRACT_ERROR')
  const v = value as Record<string, unknown>
  if (typeof v.email !== 'string' || !v.email || v.email.length > 254 || (v.role !== 'STUDENT' && v.role !== 'ADMIN') || typeof v.email_verified !== 'boolean' || (v.student_association !== 'linked' && v.student_association !== 'unlinked')) throw new Error('ACCOUNT_CONTRACT_ERROR')
  const allowed = ['view_student_records', 'manage_student_accounts', 'manage_credentials', 'revoke_credentials', 'sync_classroom', 'import_completions']
  if (v.capabilities !== undefined && (!Array.isArray(v.capabilities) || !v.capabilities.every(c => typeof c === 'string' && allowed.includes(c)))) throw new Error('ACCOUNT_CONTRACT_ERROR')
  return { email: v.email, role: v.role, email_verified: v.email_verified, student_association: v.student_association, ...(v.capabilities === undefined ? {} : { capabilities: v.capabilities as string[] }) }
}
export function accessDecision(session: Session, role: 'student' | 'administrator'): AccessDecision {
  if (session.status !== 'authenticated') return 'login'
  if (session.user.role !== (role === 'student' ? 'STUDENT' : 'ADMIN')) return 'wrong-role'
  if (!session.user.email_verified) return 'unverified'
  if (role === 'student') return session.user.student_association === 'linked' ? 'allow' : 'unlinked'
  // Older backends omit capabilities. A role must never manufacture a grant.
  return session.user.capabilities?.length ? 'allow' : 'permissions-missing'
}
export function normalizeUniversityEmail(value: string): string | null {
  const email = value.trim().toLowerCase()
  return email.length <= 254 && /^[a-z0-9._%+-]+@btu\.edu\.ge$/.test(email) ? email : null
}
