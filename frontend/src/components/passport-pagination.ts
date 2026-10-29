import type { CardSkill } from './PassportCard'

export const PASSPORT_WIDTH = 1000
export const PASSPORT_HEIGHT = PASSPORT_WIDTH * 595.276 / 841.89
export const sectionTitles = ['Cover', 'About the Passport', 'Verified AI Skillset', 'AI Skill Supplement']
export const stampNames = { FOCUSED: 'AI Skill', APPLIED: 'AI Applied Skill', ADVANCED: 'AI Advanced Skill' }
export interface SkillTile { skill: CardSkill; name: string[]; experience: string[]; continued: boolean }
export interface SupplementRow { skill: CardSkill; experienceIndex: number; cells: string[][]; continued: boolean; height: number }
export interface PassportPage { section: number; title: string; tiles: SkillTile[]; rows: SupplementRow[]; part: number; parts: number }

/** Conservative em-width wrapping, independent of viewport, fonts loading, and render timing.
 * Every input character is retained. Non-Latin graphemes reserve two ems. */
export function wrapPassportText(text: string, capacity: number): string[] {
  const graphemes = [...new Intl.Segmenter('en', { granularity: 'grapheme' }).segment(text)].map(item => item.segment)
  const lines: string[] = []
  let line = '', units = 0
  for (const character of graphemes) {
    const width = Array.from(character).some(point => point.codePointAt(0)! > 255) ? 2 : 1
    if (units + width > capacity && line) { lines.push(line); line = ''; units = 0 }
    line += character; units += width
    if (character.includes('\n')) { lines.push(line); line = ''; units = 0 }
  }
  if (line || !lines.length) lines.push(line)
  return lines
}

export function fitCoverText(text: string, width: number, height: number, maximum = 28) {
  for (let size = maximum; size >= 6; size--) {
    const lines = wrapPassportText(text, Math.max(2, Math.floor(width / size)))
    if (lines.length * size * 1.15 <= height) return { lines, size }
  }
  return { lines: wrapPassportText(text, Math.floor(width / 6)), size: 6 }
}

export function paginatePassport(skills: CardSkill[]): PassportPage[] {
  const pages: PassportPage[] = [0, 1].map(section => ({ section, title: sectionTitles[section], tiles: [], rows: [], part: 1, parts: 1 }))
  const tiles: SkillTile[] = [], rows: SupplementRow[] = []
  for (const skill of skills) {
    const name = wrapPassportText(skill.name || 'Not supplied', 14)
    const learning = skill.learningExperiences?.length ? skill.learningExperiences : [{ title: skill.experience, earnedOn: skill.earnedOn }]
    const experience = wrapPassportText(learning.map(item => item.title || 'Learning experience not supplied').join(' / '), 17)
    const fragments = Math.max(Math.ceil(name.length / 2), Math.ceil(experience.length / 2))
    for (let fragment = 0; fragment < fragments; fragment++) tiles.push({ skill, name: name.slice(fragment * 2, fragment * 2 + 2), experience: experience.slice(fragment * 2, fragment * 2 + 2), continued: fragment > 0 })
    learning.forEach((experience, experienceIndex) => {
      const cells = [
        skill.stampType ? stampNames[skill.stampType] : 'Not supplied', skill.name || 'Not supplied',
        skill.description || 'Not supplied', experience.title || 'Not supplied', experience.earnedOn || 'Not supplied',
      ].map((value, index) => wrapPassportText(value, [7, 10, 20, 12, 8][index]))
      const count = Math.max(...cells.map(cell => cell.length))
      for (let offset = 0; offset < count; offset += 8) {
        const part = cells.map(cell => cell.slice(offset, offset + 8))
        rows.push({ skill, experienceIndex, cells: part, continued: offset > 0, height: 32 + Math.max(2, ...part.map(cell => cell.length)) * 16 })
      }
    })
  }
  for (let offset = 0; offset < Math.max(1, tiles.length); offset += 6) pages.push({ section: 2, title: sectionTitles[2], tiles: tiles.slice(offset, offset + 6), rows: [], part: 0, parts: 0 })
  let page: PassportPage = { section: 3, title: sectionTitles[3], tiles: [], rows: [], part: 0, parts: 0 }, used = 0
  for (const row of rows) {
    if (used + row.height > 360 && page.rows.length) { pages.push(page); page = { ...page, rows: [] }; used = 0 }
    page.rows.push(row); used += row.height
  }
  pages.push(page)
  for (const section of [2, 3]) {
    const members = pages.filter(item => item.section === section)
    members.forEach((item, index) => { item.part = index + 1; item.parts = members.length })
  }
  return pages
}
