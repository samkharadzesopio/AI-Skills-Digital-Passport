import type { PassportCardData, CardSkill, StampType } from './PassportCard'
import type { PassportDocument, PassportSubcategory } from '../contracts/passport'
import { object, rows, text } from '../services/product'
import type { RecordData } from '../services/product'

function stamp(value: unknown): StampType | null { return value === 'FOCUSED' || value === 'APPLIED' || value === 'ADVANCED' ? value : null }
/** Read only fields supplied by the authenticated backend; no sample fallback. */
export function backendPassportCard(passport: RecordData, profile?: RecordData): PassportCardData {
  const version = passport.latest_version ? object(passport.latest_version) : null
  return {
    demonstration: false, firstName: text(profile?.first_name), lastName: text(profile?.last_name), issuer: null,
    reference: text(passport.public_reference) || null, issuedOn: text(version?.issued_at) || null,
    status: text(passport.lifecycle_status) || (passport.status === 'BLOCKCHAIN_VERIFIED' ? 'PROOF_NOT_CONFIRMED' : text(passport.status)),
    skills: Array.isArray(version?.skills) ? rows(version.skills).map(skill => ({ id: text(skill.skill_id) || text(skill.skill_code), name: text(skill.skill_name), description: text(skill.description) || null, stampType: stamp(skill.stamp_type), experience: null, earnedOn: null })) : [],
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
