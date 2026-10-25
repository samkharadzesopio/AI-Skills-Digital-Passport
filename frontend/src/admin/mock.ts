import type { AdminData } from './contracts'
// All names, approvals, verification states and totals below are fictional demo records.
export const adminFixture: AdminData = {
  categories: [
    { id: 'CAT-AI', name: 'AI foundations', subcategories: [
      { id: 'SUB-GEN', name: 'Generative AI', subcategories: [], skills: [
        { id: 'SK-PROMPT', name: 'Prompt engineering', description: 'Design and evaluate structured prompts.', status: 'approved' },
        { id: 'SK-EVAL', name: 'Model evaluation', description: 'Evaluate model outputs and limitations.', status: 'approved' },
      ] },
      { id: 'SUB-ETHICS', name: 'Responsible AI', subcategories: [], skills: [
        { id: 'SK-ETHICS', name: 'AI ethics', description: 'Recognize bias, privacy and governance concerns.', status: 'approved' },
      ] },
    ] },
    { id: 'CAT-DATA', name: 'Data & analytics', subcategories: [
      { id: 'SUB-DATA', name: 'Data literacy', subcategories: [
        { id: 'SUB-VIS', name: 'Data communication', subcategories: [], skills: [
          { id: 'SK-VIS', name: 'Data visualization', description: 'Communicate evidence through charts.', status: 'draft' },
        ] },
      ], skills: [{ id: 'SK-DATA', name: 'Data analysis', description: 'Explore and interpret datasets.', status: 'approved' }] },
    ] },
  ],
  students: Array.from({ length: 18 }, (_, i) => ({
    id: `DEMO-ST-${String(i + 1).padStart(3, '0')}`, name: `Demo student ${String(i + 1).padStart(2, '0')}`,
    email: `student${i + 1}@example.invalid`, program: i % 2 ? 'Information Technology' : 'Business Administration',
    skillIds: i % 3 ? ['SK-PROMPT', 'SK-ETHICS'] : ['SK-DATA'],
    credentialIds: i < 8 ? [`DEMO-CR-${i + 1}`] : [],
    passportStatus: i < 10 ? 'active' : i < 15 ? 'pending' : 'not-issued',
  })),
  courses: [
    { id: 'COURSE-AI', title: 'AI for business', approved: true, skillIds: ['SK-PROMPT', 'SK-ETHICS'], mappingStatus: 'approved', approvedBy: 'Demo academic reviewer', approvedAt: '2026-10-12T09:00:00Z' },
    { id: 'COURSE-DATA', title: 'Data-driven decisions', approved: true, skillIds: ['SK-DATA'], mappingStatus: 'draft', approvedBy: null, approvedAt: null },
    { id: 'COURSE-ML', title: 'Applied machine learning', approved: false, skillIds: [], mappingStatus: 'unmapped', approvedBy: null, approvedAt: null },
  ],
  credentials: Array.from({ length: 8 }, (_, i) => ({ id: `DEMO-CR-${i + 1}`, title: i % 2 ? 'Responsible AI essentials' : 'AI foundations', studentId: `DEMO-ST-${String(i + 1).padStart(3, '0')}`, issuer: 'BTU (fictional demonstration record)', issuedAt: i < 6 ? `2026-10-${String(10 + i).padStart(2, '0')}T09:00:00Z` : null, status: i < 5 ? 'verified' : i === 5 ? 'revoked' : 'pending', evidence: ['Example assessment reference (demo)'] })),
  syncEvents: [
    { id: 'DEMO-SYNC-01', courseId: 'COURSE-AI', timestamp: '2026-10-25T09:30:00Z', status: 'failed', attempts: 2, error: 'Example: classroom authorization expired.', preview: [{ externalStudentId: 'DEMO-ST-001', proposedSkillIds: ['SK-PROMPT'] }] },
    { id: 'DEMO-SYNC-02', courseId: 'COURSE-DATA', timestamp: '2026-10-25T10:00:00Z', status: 'pending', attempts: 0, error: null, preview: [{ externalStudentId: 'DEMO-ST-002', proposedSkillIds: ['SK-DATA'] }] },
  ],
  audit: [
    { id: 'DEMO-LOG-1', actor: 'Demo academic reviewer', action: 'Course mapping reviewed (demo)', timestamp: '2026-10-25T09:00:00Z', record: 'COURSE-AI' },
    { id: 'DEMO-LOG-2', actor: 'Demo administrator', action: 'Student record reviewed (demo)', timestamp: '2026-10-24T13:15:00Z', record: 'DEMO-ST-001' },
    { id: 'DEMO-LOG-3', actor: 'Demo classroom connector', action: 'Synchronization failure recorded (demo)', timestamp: '2026-10-24T11:20:00Z', record: 'DEMO-SYNC-01' },
  ],
  imports: [
    { id: 'DEMO-IMPORT-1', source: 'Example cohort.xlsx', timestamp: '2026-10-23T10:00:00Z', status: 'failed', errors: 3 },
    { id: 'DEMO-IMPORT-2', source: 'Example Google Sheet', timestamp: '2026-10-24T10:00:00Z', status: 'pending', errors: 0 },
  ],
  issuanceTrend: [{ month: 'May', count: 1 }, { month: 'Jun', count: 0 }, { month: 'Jul', count: 1 }, { month: 'Aug', count: 2 }, { month: 'Sep', count: 1 }, { month: 'Oct', count: 3 }],
}
export async function getAdminDemoData(): Promise<AdminData> { return structuredClone(adminFixture) }
