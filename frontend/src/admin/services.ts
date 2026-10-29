// Legacy demo forms cannot execute official actions. Live adapters are in live/service.ts.
import { demoMode } from '../demo/mode'
export type AdminAction =
  | { type: 'issue'; studentId: string; title: string }
  | { type: 'revoke'; credentialId: string; reason: string }
  | { type: 'retry-sync'; eventId: string }
  | { type: 'preview-sheet'; sheetUrl: string }
  | { type: 'commit-import'; source: string }
export async function requestAdminAction(_action: AdminAction): Promise<never> {
  if (demoMode) throw new Error('DEMO_MODE_OFFICIAL_ACTION_DISABLED')
  throw new Error('ADMIN_API_UNAVAILABLE')
}
