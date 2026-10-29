export interface Skill { name: string; category: string; progress: number; color: string }
export interface Credential { id: string; title: string; issuer: string; date: string }
export interface Student { name: string; program: string; skills: Skill[]; credentials: Credential[] }
