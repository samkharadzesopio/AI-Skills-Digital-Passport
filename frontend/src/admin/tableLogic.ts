export function filterSortRows<T>(rows: T[], search: string, text: (row: T) => string, value: (row: T) => string | number, descending: boolean): T[] {
  const term = search.trim().toLocaleLowerCase()
  return rows.filter(row => text(row).toLocaleLowerCase().includes(term)).toSorted((a, b) => {
    const left = value(a), right = value(b)
    const result = typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right), undefined, { numeric: true })
    return descending ? -result : result
  })
}
