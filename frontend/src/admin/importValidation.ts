import type { AdminData, ImportPreview } from './contracts'
import { skills } from './catalog'
export function validateImportRows(rows: unknown[][], data: AdminData): ImportPreview {
  if (!rows.length) return { rows: [], errors: ['emptyWorkbook'] }
  const headers = rows[0].map(v => String(v ?? '').trim())
  const required = ['student_id', 'course_id', 'skill_id']
  if (headers.length !== 3 || new Set(headers).size !== 3 || required.some(h => !headers.includes(h))) return { rows: [], errors: ['invalidHeaders'] }
  if (rows.length > 1001) return { rows: [], errors: ['tooManyRows'] }
  const seen = new Set<string>()
  const preview = rows.slice(1).map((cells, i) => {
    const [studentId, courseId, skillId] = required.map(h => String(cells[headers.indexOf(h)] ?? '').trim())
    const errors: string[] = []
    if (!studentId || !courseId || !skillId) errors.push('requiredCell')
    if (!data.students.some(s => s.id === studentId)) errors.push('unknownStudent')
    const course = data.courses.find(c => c.id === courseId)
    if (!course?.approved) errors.push('unknownCourse')
    if (!skills(data).some(s => s.id === skillId && s.status === 'approved')) errors.push('unknownSkill')
    if (course && (course.mappingStatus !== 'approved' || !course.skillIds.includes(skillId))) errors.push('unmappedSkill')
    const key = JSON.stringify([studentId,courseId,skillId])
    if (seen.has(key)) errors.push('duplicateRow')
    seen.add(key)
    return { id: `ROW-${i + 2}`, row: i + 2, studentId, courseId, skillId, errors }
  }).filter(row => row.studentId || row.courseId || row.skillId)
  return { rows: preview, errors: preview.length ? [] : ['emptyWorkbook'] }
}
export function isGoogleSheetUrl(value: string): boolean {
  try { const url = new URL(value); return url.protocol === 'https:' && url.hostname === 'docs.google.com' && !url.port && !url.username && !url.password && /^\/spreadsheets\/d\/[a-zA-Z0-9_-]+(?:\/|$)/.test(url.pathname) } catch { return false }
}
