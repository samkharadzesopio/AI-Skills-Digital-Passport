import { useState } from 'react'
import type { FormEvent } from 'react'
import { FolderTree, Plus, Pencil } from 'lucide-react'
import { Card, EmptyState } from '../components/ui'
import { useAdminData } from './store'
import { useAdminText } from './i18n'
import { Dialog, PageTitle, Status } from './components'
import { saveCatalog, subcategories } from './catalog'
import type { CatalogInput, CatalogSubcategory } from './contracts'

function CatalogForm({ input, onClose, onSaved }: { input: CatalogInput; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState(input), [error, setError] = useState(''), { data, update } = useAdminData(), t = useAdminText()
  const parents = input.kind === 'skill' ? subcategories(data) : [...data.categories, ...subcategories(data)]
  function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    try { update(current => saveCatalog(current, form, crypto.randomUUID())); onSaved(); onClose() }
    catch (e) { const code = e instanceof Error ? e.message : ''; setError(t(code === 'DUPLICATE_NAME' ? 'duplicateName' : code === 'MISSING_PARENT' ? 'parentInvalid' : 'nameInvalid')) }
  }
  return <Dialog title={`${input.id ? t('edit') : t('save')} · ${t(input.kind)}`} onClose={onClose}><form onSubmit={submit}><label htmlFor="catalog-name">{t('name')}</label><input id="catalog-name" autoComplete="off" required minLength={2} maxLength={100} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}/>{input.id && <><label htmlFor="catalog-id">{t('stableId')}</label><input id="catalog-id" readOnly value={input.id}/></>}{form.kind !== 'category' && <><label htmlFor="catalog-parent">{t('parent')}</label><select id="catalog-parent" required disabled={!!input.id} value={form.parentId} onChange={e => setForm({ ...form, parentId: e.target.value })}><option value="">{t('selectParent')}</option>{parents.map(p => <option key={p.id} value={p.id}>{p.name} · {p.id}</option>)}</select></>}{form.kind === 'skill' && <><label htmlFor="catalog-description">{t('description')}</label><textarea id="catalog-description" maxLength={500} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}/></>}{error && <p role="alert" className="error">{error}</p>}<p className="notice">{t('localOnly')}</p><div className="admin-form-actions"><button type="button" className="button" onClick={onClose}>{t('cancel')}</button><button className="button primary">{t('save')}</button></div></form></Dialog>
}
function SubcategoryNode({ node, parentId, edit }: { node: CatalogSubcategory; parentId: string; edit: (input: CatalogInput) => void }) {
  const t = useAdminText()
  return <li><details open><summary><FolderTree size={17}/><strong>{node.name}</strong><small>{node.id}</small></summary><div className="admin-tree-actions"><button className="button" onClick={() => edit({ kind: 'subcategory', id: node.id, parentId, name: node.name, description: '' })}><Pencil size={13}/>{t('edit')}</button><button className="button" onClick={() => edit({ kind: 'skill', parentId: node.id, name: '', description: '' })}><Plus size={13}/>{t('addSkill')}</button><button className="button" onClick={() => edit({ kind: 'subcategory', parentId: node.id, name: '', description: '' })}>{t('addSubcategory')}</button></div><ul>{node.skills.map(skill => <li className="admin-skill-node" key={skill.id}><div><strong>{skill.name}</strong><small>{skill.id}</small><p>{skill.description}</p></div><Status value={skill.status}/><button className="button" onClick={() => edit({ kind: 'skill', id: skill.id, parentId: node.id, name: skill.name, description: skill.description })} aria-label={`${t('edit')} ${skill.name}`}><Pencil size={13}/>{t('edit')}</button></li>)}{node.subcategories.map(child => <SubcategoryNode key={child.id} node={child} parentId={node.id} edit={edit}/>)}</ul></details></li>
}
export function CatalogPage() {
  const { data } = useAdminData(), t = useAdminText(), [form, setForm] = useState<CatalogInput | null>(null), [notice, setNotice] = useState(''), [search, setSearch] = useState('')
  // Keep full ancestors/descendants visible rather than flattening search results.
  const matches = (node: CatalogSubcategory): boolean => `${node.name} ${node.id}`.toLowerCase().includes(search.trim().toLowerCase()) || node.skills.some(s => `${s.name} ${s.id}`.toLowerCase().includes(search.trim().toLowerCase())) || node.subcategories.some(matches)
  const categories = data.categories.filter(c => `${c.name} ${c.id}`.toLowerCase().includes(search.trim().toLowerCase()) || c.subcategories.some(matches))
  return <><PageTitle title={t('catalog')} description={t('catalogHint')} action={<button className="button primary" onClick={() => { setNotice(''); setForm({ kind: 'category', parentId: '', name: '', description: '' }) }}><Plus size={16}/>{t('addCategory')}</button>}/>{notice && <p className="notice" role="status">{notice}</p>}<Card><label className="sr-only" htmlFor="catalog-search">{t('search')}</label><input id="catalog-search" type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder={t('search')}/><ul className="admin-catalog-tree">{categories.map(category => <li key={category.id}><div className="admin-category-title"><div><h2>{category.name}</h2><small>{category.id}</small></div><div className="admin-row-actions"><button className="button" onClick={() => setForm({ kind: 'category', id: category.id, parentId: '', name: category.name, description: '' })}>{t('edit')}</button><button className="button" onClick={() => setForm({ kind: 'subcategory', parentId: category.id, name: '', description: '' })}>{t('addSubcategory')}</button></div></div><ul>{category.subcategories.map(node => <SubcategoryNode key={node.id} node={node} parentId={category.id} edit={setForm}/>)}</ul></li>)}</ul>{!categories.length && <EmptyState title={t(data.categories.length ? 'noRecords' : 'noCategories')}>{t('noRecordsHint')}</EmptyState>}</Card>{form && <CatalogForm input={form} onClose={() => setForm(null)} onSaved={() => setNotice(t('saved'))}/>}</>
}
