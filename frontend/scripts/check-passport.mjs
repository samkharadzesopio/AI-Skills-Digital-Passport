import assert from 'node:assert/strict'
import fs from 'node:fs'
import crypto from 'node:crypto'
import { createServer } from 'vite'
const server=await createServer({define:{'import.meta.env.VITE_ENABLE_DEMO':'false'},server:{middlewareMode:true},appType:'custom'})
try {
 const manifest=JSON.parse(fs.readFileSync('src/contracts/passport-template.json','utf8'))
 const hash=path=>crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex')
 for(const path of ['../templates/Passport_Blank.pdf','../backend/templates/Passport_Blank.pdf','public/templates/btu-passport-blank.pdf'])assert.equal(hash(path),manifest.sha256)
 assert.equal(hash('../templates/Passpor_Filled Form.pdf'),hash('../backend/templates/Passpor_Filled Form.pdf'))
 const {demoPassport}=await server.ssrLoadModule('/src/data/passport.ts')
 const {PassportPreview}=await server.ssrLoadModule('/src/components/PassportPreview.tsx')
 const React=await import('react'),{renderToString}=await import('react-dom/server')
 const render=(passport,showTemplate=false)=>renderToString(React.createElement(PassportPreview,{passport,showTemplate}))
 assert.equal(demoPassport.schemaVersion,'2.0')
 assert.equal(demoPassport.holder.internalStudentUuid,null)
 assert.notEqual(demoPassport.holder.externalStudentId,demoPassport.identity.passportId)
 assert.notEqual(demoPassport.identity.passportId,demoPassport.identity.passportVersionId)
 const ids=new Set(),credentialIds=new Set(demoPassport.credentials.map(c=>c.id)),evidenceIds=new Set(demoPassport.evidence.map(e=>e.id))
 let maxDepth=0,skillCount=0
 function visit(node,depth){assert.ok(!ids.has(node.id));ids.add(node.id);maxDepth=Math.max(maxDepth,depth);for(const skill of node.skills){skillCount++;assert.ok(!ids.has(skill.id));ids.add(skill.id);for(const id of skill.credentialIds)assert.ok(credentialIds.has(id));for(const id of skill.evidenceIds)assert.ok(evidenceIds.has(id));for(const experience of skill.learningExperiences)assert.ok(credentialIds.has(experience.credentialId))}for(const child of node.subcategories)visit(child,depth+1)}
 for(const category of demoPassport.categories)visit(category,0)
 assert.ok(maxDepth>=2);assert.ok(skillCount>0)
 const html=render(demoPassport,true)
 for(const text of ['Example competency category','Example subcategory','Example nested subcategory','Example AI skill','Example proficiency level','Example workshop','External student ID','Passport ID (public reference)','Passport Version ID (public reference)','unverified (demo)','templates/btu-passport-blank.pdf'])assert.ok(html.includes(text),text)
 assert.doesNotMatch(render(demoPassport),/<object/)
 const corrupted=structuredClone(demoPassport)
 corrupted.identity.status='issued';corrupted.verification.status='verified';corrupted.verification.reference='never-show-demo-reference';corrupted.credentials[0].publicReference='never-show-demo-credential';corrupted.credentials[0].status='issued'
 const safe=render(corrupted)
 assert.match(safe,/unverified \(demo\)/);assert.doesNotMatch(safe,/never-show-demo-reference|never-show-demo-credential/)
 const schema=JSON.parse(fs.readFileSync('src/contracts/passport.schema.json','utf8'))
 assert.equal(schema.properties.schemaVersion.const,'2.0')
 for(const key of ['passportId','passportVersionId','versionNumber','status','revokedAt'])assert.ok(schema.properties.identity.required.includes(key))
 assert.equal(schema.$defs.category.properties.subcategories.items.$ref,'#/$defs/category')
 assert.ok(schema.$defs.skill.required.includes('learningExperiences'))
 console.log('Passport checks passed: exact template hashes, distinct identities, schema v2 fields, recursive hierarchy, evidence/credential references, shared template viewer and suppression of official demo references.')
} finally {await server.close()}
