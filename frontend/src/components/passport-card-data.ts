import type { PassportCardData, CardSkill, StampType } from './PassportCard'
import type { PassportDocument, PassportSubcategory } from '../contracts/passport'
import type { Passport, Profile } from '../student/contracts'

function stamp(value: unknown): StampType | null { return value === 'FOCUSED' || value === 'APPLIED' || value === 'ADVANCED' ? value : null }
/** Read only fields supplied by the authenticated backend; no sample fallback. */
export function backendPassportCard(passport: Passport, profile?: Profile): PassportCardData {
  const version = passport.latest_version
  return {
    demonstration: false, firstName: profile?.first_name ?? '', lastName: profile?.last_name ?? '', issuer: null,
    reference: passport.public_reference || null, issuedOn: version?.issued_at || null,
    status: passport.lifecycle_status || 'PROOF_NOT_CONFIRMED',
    skills: version?.skills.map(skill => ({ id: skill.skill_id, name: skill.skill_name, description: skill.description || null, stampType: stamp(skill.stamp_type), experience: null, earnedOn: null })) ?? [],
  }
}
export function structuredPassportCard(passport: PassportDocument): PassportCardData {
  const skills: CardSkill[] = []
  function collect(node: PassportSubcategory) {
    for (const skill of node.skills) skills.push({ id: skill.id, name: skill.name, description: skill.description, stampType: stamp(skill.stampType), experience: skill.learningExperiences[0]?.title ?? null, earnedOn: skill.learningExperiences[0]?.earnedOn ?? null, learningExperiences: skill.learningExperiences.map(experience => ({ title: experience.title, earnedOn: experience.earnedOn })) })
    node.subcategories.forEach(collect)
  }
  passport.categories.forEach(collect)
  return { demonstration: passport.provenance === 'demo', firstName: passport.holder.firstName, lastName: passport.holder.lastName,
    issuer: passport.issuer.name, reference: passport.provenance === 'demo' ? null : passport.identity.passportId,
    issuedOn: passport.provenance === 'demo' ? null : passport.identity.issuedAt, status: passport.identity.status, skills }
}
