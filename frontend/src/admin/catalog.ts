import type { AdminData, CatalogInput, CatalogSkill, CatalogSubcategory } from './contracts'
export function subcategories(data: AdminData): CatalogSubcategory[] {
  const visit = (nodes: CatalogSubcategory[]): CatalogSubcategory[] => nodes.flatMap(n => [n, ...visit(n.subcategories)])
  return data.categories.flatMap(c => visit(c.subcategories))
}
// Indexes for lookup/selection only; the source tree and preview remain recursive.
export function skills(data: AdminData): CatalogSkill[] { return subcategories(data).flatMap(n => n.skills) }
export function saveCatalog(data: AdminData, input: CatalogInput, newId: string): AdminData {
  const name = input.name.trim()
  if (name.length < 2 || name.length > 100 || input.description.length > 500) throw new Error('INVALID_NAME')
  const next = structuredClone(data)
  const nodes = subcategories(next)
  const existing = input.kind === 'category' ? next.categories.find(n => n.id === input.id) : input.kind === 'subcategory' ? nodes.find(n => n.id === input.id) : skills(next).find(n => n.id === input.id)
  if (input.id && !existing) throw new Error('MISSING_RECORD')
  const allNames = input.kind === 'category' ? next.categories : input.kind === 'subcategory' ? nodes : skills(next)
  if (allNames.some(n => n.id !== input.id && n.name.toLowerCase() === name.toLowerCase())) throw new Error('DUPLICATE_NAME')
  if (existing) {
    existing.name = name
    if ('description' in existing) {
      existing.description = input.description.trim(); existing.status = 'draft'
      next.courses = next.courses.map(c => c.skillIds.includes(existing.id) ? { ...c, mappingStatus: 'draft', approvedBy: null, approvedAt: null } : c)
    }
    // Edits preserve parent relationships and stable IDs. Approval is never invented.
    return next
  }
  const id = `DEMO-${input.kind.toUpperCase()}-${newId}`
  if ([...next.categories, ...nodes, ...skills(next)].some(n => n.id === id)) throw new Error('DUPLICATE_ID')
  if (input.kind === 'category') next.categories.push({ id, name, subcategories: [] })
  else if (input.kind === 'subcategory') {
    const parent = [...next.categories, ...nodes].find(n => n.id === input.parentId)
    if (!parent) throw new Error('MISSING_PARENT')
    parent.subcategories.push({ id, name, subcategories: [], skills: [] })
  } else {
    const parent = nodes.find(n => n.id === input.parentId)
    if (!parent) throw new Error('MISSING_PARENT')
    parent.skills.push({ id, name, description: input.description.trim(), status: 'draft' })
  }
  return next
}
export function saveMapping(data: AdminData, courseId: string, skillIds: string[]): AdminData {
  const course = data.courses.find(c => c.id === courseId)
  if (!course?.approved || !skillIds.length || new Set(skillIds).size !== skillIds.length || skillIds.some(id => !skills(data).some(s => s.id === id && s.status === 'approved'))) throw new Error('INVALID_MAPPING')
  return { ...data, courses: data.courses.map(c => c.id === courseId ? { ...c, skillIds: [...skillIds], mappingStatus: 'draft', approvedBy: null, approvedAt: null } : c) }
}
