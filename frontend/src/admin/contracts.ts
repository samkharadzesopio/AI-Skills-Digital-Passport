export type RecordStatus = 'active' | 'pending' | 'revoked'
export interface AdminStudent {
  id: string; name: string; email: string; program: string
  skillIds: string[]; credentialIds: string[]; passportStatus: RecordStatus | 'not-issued'
}
export interface CatalogSkill { id: string; name: string; description: string; status: 'draft' | 'approved' }
export interface CatalogSubcategory { id: string; name: string; subcategories: CatalogSubcategory[]; skills: CatalogSkill[] }
export interface CatalogCategory { id: string; name: string; subcategories: CatalogSubcategory[] }
export interface AdminCourse {
  id: string; title: string; approved: boolean; skillIds: string[]
  mappingStatus: 'draft' | 'approved' | 'unmapped'; approvedBy: string | null; approvedAt: string | null
}
export interface AdminCredential {
  id: string; title: string; studentId: string; issuer: string; issuedAt: string | null
  status: 'verified' | 'pending' | 'revoked'; evidence: string[]
}
export interface SyncEvent {
  id: string; courseId: string; timestamp: string; status: 'pending' | 'failed'
  attempts: number; error: string | null; preview: { externalStudentId: string; proposedSkillIds: string[] }[]
}
export interface AuditEntry { id: string; actor: string; action: string; timestamp: string; record: string }
export interface ImportRecord { id: string; source: string; timestamp: string; status: 'pending' | 'failed'; errors: number }
export interface AdminData {
  students: AdminStudent[]; categories: CatalogCategory[]; courses: AdminCourse[]
  credentials: AdminCredential[]; syncEvents: SyncEvent[]; audit: AuditEntry[]; imports: ImportRecord[]
  issuanceTrend: { month: string; count: number }[]
}
export interface CatalogInput { kind: 'category' | 'subcategory' | 'skill'; id?: string; parentId: string; name: string; description: string }
export interface ImportPreviewRow { id: string; row: number; studentId: string; courseId: string; skillId: string; errors: string[] }
export interface ImportPreview { rows: ImportPreviewRow[]; errors: string[] }
