// Synthetic workbook and intercepted read-only API responses; no real records are changed.
import assert from 'node:assert/strict'
import path from 'node:path'
import os from 'node:os'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { createServer } from 'vite'
const require = createRequire(import.meta.url)
const { zipSync, strToU8 } = require(createRequire(require.resolve('read-excel-file/node')).resolve('fflate'))
const { chromium } = await import(pathToFileURL(path.join(os.tmpdir(),'btu-passport-browser-tests/node_modules/playwright/index.mjs')).href)
const server = await createServer({root:path.resolve(import.meta.dirname,'..'),define:{'import.meta.env.VITE_ENABLE_DEMO':'"false"'},cacheDir:path.join(os.tmpdir(),'btu-import-preview-cache'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}})
await server.listen()
const browser=await chromium.launch({headless:true})
try {
  const page=await browser.newPage(), writes=[]
  await page.route('**/api/**',route=>{
    const request=route.request(), url=new URL(request.url())
    if(request.method()!=='GET')writes.push(url.pathname)
    const data=url.pathname.endsWith('/accounts/me/')?{email:'preview.admin@btu.edu.ge',role:'ADMIN',email_verified:true,student_association:'unlinked',capabilities:['view_student_records','import_completions']}:{results:[],next:null,previous:null}
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)})
  })
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/admin/imports`)
  await page.locator('#completion-workbook').waitFor()
  const columns=['external_student_id','course_id','completion_status','grade','passed','completion_date','source_event_id']
  const values=['SYNTHETIC-STUDENT','SYNTHETIC-COURSE','completed','90','true','2026-10-01','SYNTHETIC-EVENT']
  const row=(cells,index)=>`<row r="${index}">${cells.map((value,col)=>`<c r="${String.fromCharCode(65+col)}${index}" t="inlineStr"><is><t>${value}</t></is></c>`).join('')}</row>`
  const zip=zipSync(Object.fromEntries(Object.entries({
    '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/></Types>',
    '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Evidence" sheetId="1" r:id="rId1"/></sheets></workbook>',
    'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    'xl/worksheets/sheet1.xml':`<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${row(columns,1)}${row(values,2)}</sheetData></worksheet>`,
  }).map(([name,value])=>[name,strToU8(value)])))
  await page.locator('#completion-workbook').setInputFiles({name:'synthetic-evidence.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:Buffer.from(zip)})
  await page.locator('.admin-preview').waitFor()
  assert.match(await page.locator('.admin-preview').innerText(),/SYNTHETIC-STUDENT/)
  assert.equal(await page.getByRole('button',{name:'Import Excel evidence',exact:true}).isEnabled(),true)
  assert.deepEqual(writes,[],'Local preview must not issue server writes')
  await page.locator('#completion-workbook').setInputFiles({name:'unsupported.txt',mimeType:'text/plain',buffer:Buffer.from('not a workbook')})
  assert.equal(await page.locator('.admin-preview').count(),0)
  assert.equal(await page.getByRole('button',{name:'Import Excel evidence',exact:true}).isEnabled(),false)
  console.log('PASS: actual XLSX preview, invalid-file cleanup, disabled submission, zero mutation requests. Synthetic browser fixture only.')
}finally{await browser.close();await server.close()}
