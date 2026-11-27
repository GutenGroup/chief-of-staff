// Pure parsing for the Workspace panel: owner actions and COO outcomes from the report files.
// No engine calls here, so it can be tested on its own (tests/test_sidebar_actions.mts).

export type Link = { label: string; kind: 'url' | 'file' | 'session'; target: string }
export type Action = {
  key: string // stable id for Done / Later
  source: string // report name ("Acme_Ops") or "brief" / "session"
  ask: string // the first clause: what the owner does
  details: string // the rest of the line (options, data)
  at: number // when it was written (ms)
  links: Link[]
  sessionId?: string // the session that asked, when known
  options?: { label: string; why: string; recommended?: boolean }[]
  title?: string // brief / session items: who asks
  copy?: string // brief items: text to copy
  packet?: Packet // [legal] / [money] items: the owner-ready packet
}
// The owner-ready packet (docs/AUTONOMY.md section 2): one card the owner can act on without opening anything.
export type Packet = {
  tag: 'legal' | 'money'; recommend: string; agree: string[]; checked: string[]
  verify: { label: string; value: string }[]; link: string; after: string; time: string
}
export type Decided = { id: string; title: string; what: string; why: string; source: string; undo: string }
export type CooLine = { name: string; outcome: string; at: number; forCos?: string } // forCos: an open untagged ask, for the Chief of Staff

const DAY = 24 * 3600 * 1000

// Report files that are not one COO's own report: digests of other reports, protocol notes.
export function isReportFile(name: string): boolean {
  if (!name.endsWith('.md')) return false
  if (/conflicted copy/i.test(name)) return false
  if (/_CoS(\.|$)/i.test(name)) return false // digests that repeat other COOs' lines
  return !/^(README|AWAY_MODE|FleetTest|Chief_of_Staff)\b/i.test(name) // the brief covers the CoS's own asks
}
// "Acme.laptop-2.md" -> "Acme" (a COO's report from another machine)
export const reportName = (file: string) => file.replace(/\.md$/, '').split('.')[0] || file

const ISO = /(20\d\d-\d\d-\d\d)(?:[T ](\d\d:\d\d)(?::(\d\d))?\s*(Z|[+-]\d\d:?\d\d)?)?/
// A date alone counts as the end of that day, so yesterday's dated entries stay in the 24 h window.
export function stamp(m: RegExpExecArray | null, now = Infinity): number {
  if (!m) return 0
  if (!m[2]) return Math.min(Date.parse(`${m[1]}T23:59:00Z`) || 0, now)
  let zone = m[4] || 'Z'
  if (/^[+-]\d{4}$/.test(zone)) zone = `${zone.slice(0, 3)}:${zone.slice(3)}`
  return Date.parse(`${m[1]}T${m[2]}:${m[3] || '00'}${zone}`) || 0
}

const NONE = /^(none|n\/a|nothing|no\b|resolved|closed|done\b|—|-|\(none)/i
// "none" alone (not "none new", "none yet") means the COO has nothing open: earlier asks are void.
const CLEARS = /^(none|nothing)\.?\s*$/i
export const PER_REPORT = 3

// Only a tagged line reaches the owner: needs-owner[legal]: (sign, accept terms) or needs-owner[money]: (pay, buy,
// move money). An untagged needs-owner line is a question for the Chief of Staff and shows in that COO's row.
export const OWNER_TAGS = /^(legal|money)$/i
export function markerFor(owner: string): RegExp {
  const who = ['owner', owner.trim().toLowerCase()].filter(Boolean).map(w => w.replace(/[^a-z0-9]/g, '')).filter(Boolean)
  return new RegExp(`needs[- ](?:${who.join('|')})(?:\\[([a-z-]+)\\])?\\**\\s*:\\**\\s*`, 'i')
}

export function normKey(text: string): string {
  return text.toLowerCase().replace(/[`*_"'()[\]]/g, '').replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 70)
}

// Links an action carries: web addresses, files, sessions. The first is the main button.
export function linksIn(text: string, dataRoot: string, home: string): Link[] {
  const out: Link[] = []
  const seen = new Set<string>()
  const add = (l: Link) => { if (!seen.has(l.target)) { seen.add(l.target); out.push(l) } }
  const verb = /bank ?id/i.test(text) ? 'BankID' : /\bsubmit/i.test(text) ? 'Submit' : /\bsign\b|signature|docusign/i.test(text) ? 'Sign'
    : /\bapprove/i.test(text) ? 'Approve' : /\binvite/i.test(text) ? 'Invite' : 'Open'
  for (const m of text.matchAll(/https?:\/\/[^\s)\]>`'",|]+/g)) add({ label: verb, kind: 'url', target: m[0].replace(/[.;:]+$/, '') })
  for (const m of text.matchAll(/(?:^|[\s(`])((?:[a-z0-9-]+\.)*(?:claude\.ai|chatgpt\.com|openai\.com|apple\.com|google\.com|github\.com)\/[^\s)\]>`'",|]*)/gi))
    add({ label: verb, kind: 'url', target: `https://${(m[1] || '').replace(/[.;:]+$/, '')}` })
  for (const m of text.matchAll(/(?:^|[\s(`])((?:~|\/Users)\/[^\s`'",|)]+\.[A-Za-z0-9]{1,6})/g))
    add({ label: 'Open file', kind: 'file', target: (m[1] || '').replace(/^~/, home) })
  for (const m of text.matchAll(/(?:^|[\s(`])((?:Context|People|Briefs|fleet|_Brain|Magazine)\/[^\s`'",|)]+\.[A-Za-z0-9]{1,6})/g))
    if (dataRoot && m[1]) add({ label: 'Open file', kind: 'file', target: `${dataRoot}/${m[1]}` })
  for (const m of text.matchAll(/local_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g))
    add({ label: 'Open session', kind: 'session', target: m[0] })
  return out
}

// One report file -> its open owner actions from the last 24 h, and its newest outcome line.
export function parseReport(text: string, file: string, now: number, owner: string, dataRoot = '', home = ''):
  { actions: Action[]; latest: CooLine | null } {
  const name = reportName(file)
  const marker = markerFor(owner)
  const actions: Action[] = []
  let ctx = 0 // date of the nearest heading above
  let latest: CooLine | null = null
  const clears: number[] = []
  const forCos: { ask: string; at: number }[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line) continue
    const head = /^#{1,4}\s/.test(line)
    const lead = /^(?:#{1,4}\s*|[-*]\s*|\**)*\s*(?=20\d\d-)/.exec(line)
    const iso = lead ? ISO.exec(line.slice(lead[0].length, lead[0].length + 32)) : null
    if (iso && iso[2] ? stamp(iso) > now + 3600e3 : iso && Date.parse(`${iso[1]}T00:00:00Z`) > now) continue // a planning date, not when the entry was written
    const own = stamp(iso, now)
    if (head && own) ctx = own
    const at = own || ctx
    if (at && (!latest || at > latest.at) && (head || own)) {
      const body = line.replace(/^#+\s*/, '').replace(/^[-*]\s*/, '').replace(ISO, '').replace(/^\s*[—–:|-]+\s*/, '')
      const done = /\bdone:\s*([^|]+)/i.exec(body)
      latest = { name, outcome: ((done && done[1]) || body).trim().slice(0, 220), at }
    }
    const m = marker.exec(line)
    if (!m || !at || now - at > DAY) continue
    const value = line.slice(m.index + m[0].length).replace(/^[`"]+/, '').trim()
    if (CLEARS.test(value)) { clears.push(at); continue }
    if (!value || NONE.test(value)) continue
    const parts = value.split(/\s+\|\s+/)
    if (!OWNER_TAGS.test(m[1] || '')) { forCos.push({ ask: (parts[0] || '').replace(/[`"]+$/, '').trim(), at }); continue }
    const first = (parts[0] || '').replace(/[`"]+$/, '').trim()
    const pick = recommended(first)
    const pieces = pick ? [pick] : splitAsks(first)
    for (const piece of pieces) {
      if (piece.length < 4) continue
      const details = [pick ? first : '', ...parts.slice(1)].filter(Boolean).join(' | ')
      actions.push({
        key: `${name}:${normKey(piece)}`, source: name, ask: piece, details, at,
        links: linksIn(`${piece} ${parts.slice(1).join(' ')}`, dataRoot, home),
      })
    }
  }
  const lastClear = Math.max(0, ...clears)
  const open = dedupe(actions.filter(a => a.at > lastClear)).slice(0, PER_REPORT)
  const ask = forCos.filter(q => q.at > lastClear).sort((a, b) => b.at - a.at)[0]
  if (latest && ask) latest.forCos = ask.ask
  return { actions: open, latest }
}

// One ask offered as numbered options, "(1, recommended) X; (2) Y; (3) hold": one card, the recommended option as
// the ask (the first option when none is marked) and the whole line as details. Never split it.
export function recommended(ask: string): string {
  const opts = [...ask.matchAll(/\((\d)(,\s*recommended)?\)\s*([^;]+?)(?=;\s*\(\d[,)]|$)/gi)]
  if (opts.length < 2) return ''
  const rec = opts.find(o => o[2]) || opts[0]
  return (rec?.[3] || '').replace(/[;,.\s]+$/, '').trim()
}

// "sign X; delete Y" is two asks. Split on "; " outside brackets, unless the next part continues the first.
export function splitAsks(ask: string): string[] {
  const out: string[] = []
  let depth = 0, start = 0
  for (let i = 0; i < ask.length; i++) {
    const c = ask[i]
    if (c === '(' || c === '[') depth++
    else if ((c === ')' || c === ']') && depth) depth--
    else if (c === ';' && !depth && ask[i + 1] === ' ' && !/^\s*(then|and|or|alt|rec|else|so|but)\b/i.test(ask.slice(i + 1))) {
      out.push(ask.slice(start, i).trim()); start = i + 1
    }
  }
  out.push(ask.slice(start).trim())
  return out.filter(Boolean)
}
// Ids like #380 or GGU-1001 name one thing: two asks that share one are the same ask.
const ids = (t: string) => new Set(t.match(/#\d{2,}|\b[A-Z]{2,}-\d{2,}\b/g) || [])

// Same ask from two reports (or the brief and a report): keep the newest, merge links.
const words = (t: string) => new Set(normKey(t).split(' ').filter(w => w.length > 3))
export function similar(a: string, b: string): boolean {
  const x = words(a), y = words(b)
  for (const i of ids(a)) if (ids(b).has(i)) return true
  if (!x.size || !y.size) return normKey(a) === normKey(b)
  let both = 0
  for (const w of x) if (y.has(w)) both++
  return both / Math.min(x.size, y.size) >= 0.6
}
export function dedupe(actions: Action[]): Action[] {
  const kept: Action[] = []
  for (const a of [...actions].sort((x, y) => y.at - x.at)) {
    const have = kept.find(k => normKey(k.ask).slice(0, 50) === normKey(a.ask).slice(0, 50) || similar(k.ask, a.ask))
    if (!have) { kept.push(a); continue }
    for (const l of a.links) if (!have.links.some(h => h.target === l.target)) have.links.push(l)
    if (!have.sessionId && a.sessionId) have.sessionId = a.sessionId
    if (!have.options && a.options) have.options = a.options
  }
  return kept
}

// Done hides an action for good; Later hides it until `until`.
export type Mark = { state: 'done' | 'later'; at: string; until?: number }
export function visible(actions: Action[], marks: Record<string, Mark>, now: number): Action[] {
  return actions.filter(a => {
    const m = marks[a.key]
    if (!m) return true
    if (m.state === 'done') return false
    return !(m.until && m.until > now)
  })
}

// ── Chief of Staff tick debounce ─────────────────────────────────────────────
// Every open session runs this mod. One of them sends ticks: the lease holder, or any
// session once the holder has gone quiet (closed). And no tick within 5 min of the last.
export const TICK_FLOOR_MS = 5 * 60000
export const LEASE_MS = 3 * 60000
export type Stamp = { by?: string; at?: string }
const sid = (s?: string) => String(s || '').replace(/^local_/, '')
export function holdsLease(lease: Stamp, me: string, now: number): boolean {
  return !lease.by || sid(lease.by) === sid(me) || !(now - Date.parse(lease.at || '') < LEASE_MS)
}
export function tickDue(last: Stamp, now: number): boolean {
  return !(now - Date.parse(last.at || '') < TICK_FLOOR_MS)
}

// ── Decided list, owner-ready packets, permission mode ───────────────────────
export const DECIDED_MAX = 5
const str = (v: unknown) => (typeof v === 'string' ? v.trim() : typeof v === 'number' ? String(v) : '')
const strs = (v: unknown): string[] => (Array.isArray(v) ? v.map(str).filter(Boolean) : [])

// brief.decided -> at most five well-formed items; anything without an id and a title is dropped.
export function shapeDecided(list: unknown): Decided[] {
  if (!Array.isArray(list)) return []
  const out: Decided[] = []
  for (const d of list as any[]) {
    if (!d || typeof d !== 'object') continue
    const id = str(d.id), title = str(d.title) || str(d.what)
    if (!id || !title) continue
    out.push({ id, title, what: str(d.what), why: str(d.why), source: str(d.source), undo: str(d.undo) })
    if (out.length >= DECIDED_MAX) break
  }
  return out
}

// What Undo sends to the Chief of Staff: `undo <id>` (ids never carry whitespace).
export const undoMessage = (id: string): string => `undo ${String(id).trim().split(/\s+/)[0] || ''}`.trim()

// A needsOwner item -> its packet. New shape: item.packet. Old shape: a [legal]/[money] tag in the title or ask, with
// ask/options/details/copy; the recommended option becomes Recommend and the first https link becomes Do it.
export function shapePacket(q: any): Packet | undefined {
  if (!q || typeof q !== 'object') return undefined
  const pk = q.packet && typeof q.packet === 'object' ? q.packet : null
  const text = `${str(q.title)} ${str(q.ask)}`
  const tagged = /\[(legal|money)\]/i.exec(text)
  const tag = String(pk?.tag || tagged?.[1] || '').toLowerCase().replace(/[^a-z]/g, '')
  if (tag !== 'legal' && tag !== 'money') return undefined
  const opts: { label?: string; recommended?: boolean }[] = Array.isArray(q.options) ? q.options : []
  const rec = opts.find(o => o && o.recommended) || opts[0]
  const link = str(pk?.link) || (/https?:\/\/[^\s)\]>`'",|]+/.exec(`${str(q.ask)} ${str(q.details)} ${str(q.copy)}`)?.[0] || '').replace(/[.;:]+$/, '')
  const verify = Array.isArray(pk?.verify)
    ? (pk.verify as any[]).map(v => ({ label: str(v?.label), value: str(v?.value) })).filter(v => v.label || v.value).slice(0, 6)
    : []
  return {
    tag, recommend: str(pk?.recommend) || str(rec?.label), agree: strs(pk?.agree).slice(0, 5), checked: strs(pk?.checked),
    verify, link: /^https:\/\//i.test(link) ? link : '', after: str(pk?.after), time: str(pk?.time),
  }
}

// One line when the Chief of Staff session runs with prompts. Nothing when the file or the entry is missing.
export const PROMPTS_LINE = 'running with prompts: the system will stop for approvals; switch to bypass for full autonomy'
export function permissionLine(modes: unknown, cosSessionId: string): string {
  if (!modes || typeof modes !== 'object' || !cosSessionId) return ''
  const want = sid(cosSessionId)
  for (const [k, v] of Object.entries(modes as Record<string, any>)) {
    if (sid(k) !== want) continue
    const mode = str(v?.mode)
    return mode && mode !== 'bypassPermissions' ? PROMPTS_LINE : ''
  }
  return ''
}
