export function newId(prefix: string): string {
  return `${prefix}_${crypto.randomUUID()}`
}

export function dateKey(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}
