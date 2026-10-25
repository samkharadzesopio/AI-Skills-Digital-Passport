import type { PassportDocument, PassportSkill, PassportSubcategory } from '../contracts/passport'

function SkillList({ skills, passport }: { skills: PassportSkill[]; passport: PassportDocument }) {
  return <ul>{skills.map(skill => <li key={skill.id}>
    <strong>{skill.name}</strong> — {skill.proficiency.label}
    <p>Level code: {skill.proficiency.code} · Framework: {skill.proficiency.framework ?? 'Not supplied'}</p>
    <p>{skill.description}</p>
    <p>Learning-format stamp: {skill.stampType ?? 'Not assigned'} (independent of proficiency)</p>
    <ul>{skill.learningExperiences.map((experience, index) => <li key={`${experience.credentialId}-${index}`}>{experience.title ?? 'Learning experience not supplied'} · {experience.earnedOn ?? 'Date not supplied'} · {experience.credentialId}</li>)}</ul>
    <ul>{skill.credentialIds.map(id => <li key={id}>Credential: {passport.credentials.find(c => c.id === id)?.title ?? `Missing credential: ${id}`}</li>)}</ul>
    <ul>{skill.evidenceIds.map(id => <li key={id}>Evidence: {passport.evidence.find(e => e.id === id)?.title ?? `Missing evidence: ${id}`}</li>)}</ul>
  </li>)}</ul>
}
function Subcategory({ category, passport }: { category: PassportSubcategory; passport: PassportDocument }) {
  return <li><details open><summary>{category.name} <small>({category.id})</small></summary>
    <SkillList skills={category.skills} passport={passport}/>
    <ul>{category.subcategories.map(child => <Subcategory key={child.id} category={child} passport={passport}/>)}</ul>
  </details></li>
}
/** Shared semantic renderer. It does not invent an HTML replacement for the PDF. */
export function PassportPreview({ passport, showTemplate = false }: { passport: PassportDocument; showTemplate?: boolean }) {
  const status = passport.provenance === 'demo' ? 'unverified (demo)' : passport.verification.status
  return <section className="passport-structure" aria-label="Passport structured data preview">
    <p className="notice">Structured data preview only. The supplied four-page BTU PDF is the visual reference; populated PDF alignment and missing-field placement require approval. {passport.provenance === 'demo' ? 'All values below are illustrative and are not official credentials. No official reference, stamp or signature has been issued.' : 'Verified information is supplied by the university backend.'}</p>
    {showTemplate && <details className="passport-template-reference"><summary>View supplied blank BTU template (unfilled reference)</summary><p>The template artwork contains verification and issuer wording. That artwork is not evidence of issuance, blockchain anchoring, or authenticity. Sample data below has not been written into this PDF.</p><object data={`${import.meta.env.BASE_URL}templates/btu-passport-blank.pdf`} type="application/pdf" aria-label="Unfilled supplied BTU passport template"><p>PDF embedding is unavailable.</p></object><a className="button" href={`${import.meta.env.BASE_URL}templates/btu-passport-blank.pdf`} target="_blank" rel="noopener noreferrer">Open unfilled template PDF</a></details>}
    <details><summary>Inspect passport data and hierarchy</summary>
      <dl>
        <dt>Holder</dt><dd>{passport.holder.displayName}</dd>
        <dt>Internal Student UUID (private identity)</dt><dd>{passport.holder.internalStudentUuid ?? 'Not supplied'}</dd>
        <dt>External student ID</dt><dd>{passport.holder.externalStudentId ?? 'Not supplied'}</dd>
        <dt>Program / education level</dt><dd>{passport.holder.program ?? 'Not supplied'} / {passport.holder.educationLevel ?? 'Not supplied'}</dd>
        <dt>Passport ID (public reference)</dt><dd>{passport.identity.passportId ?? 'Not issued'}</dd>
        <dt>Passport Version ID (public reference)</dt><dd>{passport.identity.passportVersionId ?? 'Not issued'}</dd>
        <dt>Version number</dt><dd>{passport.identity.versionNumber ?? 'Not issued'}</dd>
        <dt>Issue / revocation status</dt><dd>{passport.provenance === 'demo' ? 'draft (demo only)' : passport.identity.status} / {passport.identity.revokedAt ?? 'No revocation timestamp supplied'}</dd>
        <dt>Schema / template version</dt><dd>{passport.schemaVersion} / {passport.identity.templateVersion ?? 'No published template version supplied'}</dd>
        <dt>Template SHA-256</dt><dd>{passport.identity.templateSha256 ?? 'Not bound to an issued version'}</dd>
        <dt>Issued at</dt><dd>{passport.identity.issuedAt ?? 'Not issued'}</dd>
        <dt>Issuer</dt><dd>{passport.issuer.name} ({passport.issuer.id}) · {passport.issuer.organizationUrl ?? 'No organization URL supplied'}</dd>
        <dt>Verification status</dt><dd>{status}</dd>
        <dt>Verification reference / checked at</dt><dd>{passport.provenance !== 'demo' && (passport.identity.status === 'issued' || passport.identity.status === 'revoked') ? passport.verification.reference ?? 'Not supplied' : 'Not issued'} / {passport.provenance === 'demo' ? 'Not checked' : passport.verification.checkedAt ?? 'Not checked'}</dd>
      </dl>
      <h3>Competency categories</h3>
      {passport.categories.length ? <ul>{passport.categories.map(category => <li key={category.id}>
        <strong>{category.name}</strong> <small>({category.id})</small>
        <SkillList skills={category.skills} passport={passport}/>
        <ul>{category.subcategories.map(child => <Subcategory key={child.id} category={child} passport={passport}/>)}</ul>
      </li>)}</ul> : <p>No competency categories supplied.</p>}
      <h3>Supporting credentials</h3>
      <ul>{passport.credentials.map(c => <li key={c.id}><strong>{c.title}</strong> ({c.id})<p>Issuer: {c.issuer.name} ({c.issuer.id}) · {c.issuer.reference ?? 'No issuer reference supplied'} · {c.issuer.organizationUrl ?? 'No URL supplied'}</p><p>Status: {passport.provenance === 'demo' ? 'draft (demo)' : c.status} · Public reference: {passport.provenance === 'demo' ? 'Not issued' : c.publicReference ?? 'Not supplied'}</p><p>Issued: {c.issuedAt ?? 'Not issued'} · Expires: {c.expiresAt ?? 'Not supplied'} · Revoked: {c.revokedAt ?? 'Not supplied'} · Reason: {c.revocationReason ?? 'Not supplied'}</p><ul>{c.evidenceIds.map(id => <li key={id}>Evidence: {passport.evidence.find(e => e.id === id)?.title ?? `Missing evidence: ${id}`}</li>)}</ul></li>)}</ul>
      {!passport.credentials.length && <p>No supporting credentials supplied.</p>}
      <h3>Evidence</h3>
      <ul>{passport.evidence.map(e => <li key={e.id}><strong>{e.title}</strong> ({e.id})<p>{e.description}</p><p>Reference: {e.reference ?? 'Not supplied'} · Issued: {e.issuedAt ?? 'Not supplied'}</p></li>)}</ul>
      {!passport.evidence.length && <p>No evidence supplied.</p>}
    </details>
  </section>
}
