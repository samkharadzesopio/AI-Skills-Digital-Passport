export type Session =
  | { status: 'authenticated'; userId: string; roles: Array<'student' | 'administrator'> }
  | { status: 'anonymous' }
  | { status: 'unavailable' }

// Replace only after confirming the Django session and permissions contract.
// Never read roles from localStorage, URL parameters, or demo records.
export async function getSession(): Promise<Session> { return { status: 'unavailable' } }
