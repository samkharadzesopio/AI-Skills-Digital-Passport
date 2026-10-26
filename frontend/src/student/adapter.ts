import type { Passport, SnapshotSkill, Version } from './contracts'
/** Only classification actually present in Django: category and one subcategory.
 * Snapshot serializers do not supply skill-to-credential/evidence links or a current
 * verification verdict. Do not fabricate any of them for the preview. */
export function adaptPassport(passport: Passport, version: Version) {
  const categories = new Map<string, { name: string; skills: SnapshotSkill[]; subcategories: Map<string, SnapshotSkill[]> }>()
  for (const skill of version.skills) {
    let category = categories.get(skill.category)
    if (!category) { category = { name: skill.category, skills: [], subcategories: new Map() }; categories.set(skill.category, category) }
    if (skill.subcategory) category.subcategories.set(skill.subcategory, [...(category.subcategories.get(skill.subcategory) ?? []), skill])
    else category.skills.push(skill)
  }
  return { passportReference: passport.public_reference, versionReference: version.public_reference, versionNumber: version.version_number, issuedAt: version.issued_at, issuanceStatus: version.status, currentVersion: passport.latest_version?.id === version.id, verificationReference: `passport-version:${version.public_reference}`, categories: [...categories.values()].map(c => ({ name: c.name, skills: c.skills, subcategories: [...c.subcategories].map(([name, skills]) => ({ name, skills })) })), credentials: version.credentials }
}
export type IssuedPassport = ReturnType<typeof adaptPassport>
