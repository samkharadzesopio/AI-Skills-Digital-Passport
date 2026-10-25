/** Proposed JSON-serializable contract. Confirm against the approved PDF and Django
 * serializer before production use. Never derive verified claims in the browser. */
export interface PassportIssuer {
  id: string
  reference: string | null
  name: string
  organizationUrl: string | null
}
export interface PassportEvidence {
  id: string
  title: string
  description: string | null
  reference: string | null
  issuedAt: string | null
}
export interface PassportCredential {
  id: string
  publicReference: string | null
  title: string
  issuer: PassportIssuer
  issuedAt: string | null
  expiresAt: string | null
  status: 'draft' | 'issued' | 'revoked' | 'unavailable'
  revokedAt: string | null
  revocationReason: string | null
  evidenceIds: string[]
}
export interface PassportSkill {
  id: string
  name: string
  description: string | null
  // Template learning-format stamps are independent of proficiency assessments.
  stampType: 'FOCUSED' | 'APPLIED' | 'ADVANCED' | null
  proficiency: { code: string; label: string; framework: string | null }
  learningExperiences: { credentialId: string; title: string | null; earnedOn: string | null }[]
  credentialIds: string[]
  evidenceIds: string[]
}
export interface PassportSubcategory {
  id: string
  name: string
  subcategories: PassportSubcategory[]
  skills: PassportSkill[]
}
export interface PassportCategory {
  id: string
  name: string
  subcategories: PassportSubcategory[]
  skills: PassportSkill[]
}
export interface PassportDocument {
  schemaVersion: '2.0'
  provenance: 'demo' | 'backend'
  identity: {
    // These are public references, never internal passport/version row UUIDs.
    passportId: string | null
    passportVersionId: string | null
    versionNumber: number | null
    templateVersion: string | null
    templateSha256: string | null
    status: 'draft' | 'issued' | 'revoked' | 'unavailable'
    issuedAt: string | null
    revokedAt: string | null
  }
  holder: {
    internalStudentUuid: string | null
    externalStudentId: string | null
    firstName: string; lastName: string; displayName: string
    program: string | null; educationLevel: string | null
  }
  issuer: PassportIssuer
  verification: {
    status: 'unverified' | 'verified' | 'revoked' | 'expired' | 'unavailable'
    reference: string | null
    checkedAt: string | null
  }
  categories: PassportCategory[]
  credentials: PassportCredential[]
  evidence: PassportEvidence[]
}
