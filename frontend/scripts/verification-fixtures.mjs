// Contract fixtures for tests only; application code never imports this module.
export const uuid = n => `00000000-0000-0000-0000-${String(n).padStart(12,'0')}`
export const sources = { credential:'POSTGRESQL_CREDENTIAL_REGISTRY', passport:'POSTGRESQL_PASSPORT_REGISTRY', document:'POSTGRESQL_DOCUMENT_REGISTRY' }
export const credential = (status='VALID', reference=uuid(1)) => ({status,credential_id:reference,verified:status==='VALID',source:sources.credential,private_email:'PRIVATE@example.invalid'})
export function snapshot(status='VALID', overrides={}) {
  const authentic=!['NOT_FOUND','UNVERIFIABLE'].includes(status)
  const credential_status=['VALID','OUTDATED'].includes(status)?'VALID':['REVOKED','EXPIRED','INVALID'].includes(status)?status:'UNVERIFIABLE'
  const credential_counts=authentic?{VALID:0,REVOKED:0,EXPIRED:0,INVALID:0,[credential_status]:1}:{}
  return {status,authentic,is_latest:authentic?status!=='OUTDATED':null,passport_version:authentic?(status==='OUTDATED'?1:2):null,latest_version:authentic?2:null,credential_status,credential_counts,source:sources.passport,private_name:'PRIVATE PERSON',...overrides}
}
export const document = (status='VALID',overrides={}) => snapshot(status,{source:sources.document,message:'PRIVATE SERVER TEXT',...overrides})
