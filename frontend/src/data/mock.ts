import type { Student } from '../types'
export const demoStudent: Student = {
  name: 'Nino', program: 'Business & Technology · Year 2',
  skills: [
    { name: 'Generative AI', category: 'AI foundations', progress: 85, color: '#E5007D' },
    { name: 'Prompt Engineering', category: 'Applied AI', progress: 72, color: '#7c3aed' },
    { name: 'Data Literacy', category: 'Data & analytics', progress: 64, color: '#22127B' },
    { name: 'Responsible AI', category: 'Ethics & governance', progress: 90, color: '#0f9f94' },
  ],
  credentials: [
    { id: 'DEMO-001', title: 'AI Foundations', issuer: 'BTU AI Academy', date: 'October 18, 2026' },
    { id: 'DEMO-002', title: 'Responsible AI Essentials', issuer: 'BTU AI Academy', date: 'October 10, 2026' },
    { id: 'DEMO-003', title: 'Introduction to Prompt Engineering', issuer: 'BTU AI Academy', date: 'September 28, 2026' },
  ],
}
export async function getDemoStudent(): Promise<Student> { return demoStudent }
