import type { PassportDocument } from '../contracts/passport'

// Structural fixture only; neither the taxonomy nor the proficiency scale is approved.
export const demoPassport: PassportDocument = {
  schemaVersion: '2.0', provenance: 'demo',
  identity: { passportId: 'DEMO-PASSPORT-001', passportVersionId: 'DEMO-VERSION-001', versionNumber: null, templateVersion: null, templateSha256: null, status: 'draft', issuedAt: null, revokedAt: null },
  holder: { internalStudentUuid: null, externalStudentId: 'DEMO-STUDENT-001', firstName: 'Nino', lastName: 'Beridze', displayName: 'Nino Beridze (demo)', program: 'Example program', educationLevel: null },
  issuer: { id: 'DEMO-ISSUER', reference: null, name: 'Example issuer (not an official record)', organizationUrl: null },
  verification: { status: 'unverified', reference: null, checkedAt: null },
  categories: [{
    id: 'demo-category', name: 'Example competency category', skills: [],
    subcategories: [{
      id: 'demo-subcategory', name: 'Example subcategory', skills: [],
      subcategories: [{
        id: 'demo-nested-subcategory', name: 'Example nested subcategory', subcategories: [],
        skills: [{ id: 'demo-skill', name: 'Example AI skill', description: 'Example learning outcome; not an official assessment.', stampType: null,
          proficiency: { code: 'example', label: 'Example proficiency level', framework: null },
          learningExperiences: [{ credentialId: 'DEMO-CREDENTIAL', title: 'Example workshop', earnedOn: null }],
          credentialIds: ['DEMO-CREDENTIAL'], evidenceIds: ['DEMO-EVIDENCE'],
        }],
      }],
    }],
  }],
  credentials: [{ id: 'DEMO-CREDENTIAL', publicReference: null, title: 'Example supporting credential',
    issuer: { id: 'DEMO-ISSUER', reference: null, name: 'Example issuer', organizationUrl: null },
    issuedAt: null, expiresAt: null, status: 'draft', revokedAt: null, revocationReason: null, evidenceIds: ['DEMO-EVIDENCE'],
  }],
  evidence: [{ id: 'DEMO-EVIDENCE', title: 'Example assessment evidence', description: 'Illustrative evidence only.', reference: null, issuedAt: null }],
}
