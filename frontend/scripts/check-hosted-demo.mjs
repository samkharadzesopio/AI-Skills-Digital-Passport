import assert from 'node:assert/strict'
import { build } from 'vite'
const original = {...process.env}
async function compile() {
  const output = await build({ logLevel:'silent', build:{ssr:'src/demo/mode.ts',write:false,minify:false,emptyOutDir:false} })
  const chunk=output.output.find(x=>x.type==='chunk'&&x.isEntry)
  return chunk.code
}
try {
  process.env.VITE_ENABLE_DEMO='true'
  process.env.BTU_DEMO_BUILD='true'
  let code=await compile()
  assert.equal((await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).demoMode,false)
  Object.assign(process.env,{BTU_HOSTED_DEMO:'true',VERCEL:'1',BTU_DEMO_PROJECT_ID:'prj_synthetic',VERCEL_PROJECT_ID:'prj_synthetic',VERCEL_GIT_COMMIT_REF:'demo/hosted-passport',BTU_DEMO_HOSTNAME:'btu-synthetic-demo.vercel.app',VITE_GOOGLE_CLIENT_ID:'',VITE_API_BASE_URL:''})
  for(const [key,bad] of [['VERCEL_GIT_COMMIT_REF','main'],['VERCEL_PROJECT_ID','prj_live'],['BTU_DEMO_HOSTNAME','live.example.org'],['VITE_API_BASE_URL','https://live.example.org/api/'],['VITE_GOOGLE_CLIENT_ID','real-client']]) {
    const previous=process.env[key];process.env[key]=bad
    await assert.rejects(compile(),/Hosted demo requires/)
    process.env[key]=previous
  }
  code=await compile()
  globalThis.window={location:{hostname:'btu-synthetic-demo.vercel.app'}}
  const load=async suffix=>import('data:text/javascript;base64,'+Buffer.from(code+'\n//'+suffix).toString('base64'))
  const allowed=await load('allowed');assert.equal(allowed.demoMode,true);assert.equal(allowed.demoHostAllowed,true)
  window.location.hostname='live.example.org';assert.equal((await load('blocked')).demoHostAllowed,false)
  console.log('Hosted demo: default off, legacy flag ignored, project/branch/API/Google/host build guards and runtime promotion guard passed.')
} finally {
  delete globalThis.window
  for(const key of Object.keys(process.env))if(!(key in original))delete process.env[key]
  Object.assign(process.env,original)
}
