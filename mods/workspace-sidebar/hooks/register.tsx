import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Brief, Row, Snapshot, Waiting } from '../types'
import { dedupe, holdsLease, isReportFile, parseReport, reportName, tickDue, visible } from './actions'
import type { Action, CooLine, Mark } from './actions'

// The Workspace panel shows two things only (owner's order 2026-11-26: "your actions only"):
//   1. every action waiting on the owner, each with one-click buttons (open the link, Done, Later);
//   2. one line per COO with its latest outcome and how fresh it is.
// Sources: the Chief of Staff brief (needsOwner), sessions that asked a question (index.json),
// and every `needs-owner:` / `needs-<owner name>:` line from the last 24 h in the COO report files.
const PANE = 'workspace-sidebar'
const TITLE = 'Workspace'
const STALE_MS = 60 * 60000 // a COO report older than this shows red
const LATER_MS = 3 * 3600e3 // "Later" hides an action for 3 hours
// The Chief of Staff session is found by title (it may carry stars or bold letters).
const plainTitle = (t: string) => t.normalize('NFKD').replace(/[^A-Za-z ]/g, '').replace(/\s+/g, ' ').trim().toLowerCase()
// Title is "⭐ 𝐂𝐇𝐈𝐄𝐅 𝐎𝐅 𝐒𝐓𝐀𝐅𝐅 ⭐" (NFKD turns the bold letters into 'chief of staff'); the older plain "Chief of Staff" and
// "CoS · Chief of Staff" still match. A session id stored in cos-state.json (cosSessionId) matches too.
let storedCosId = ''
const isCos = (r: Row) => (!!storedCosId && r.id === storedCosId) || ['chief of staff', 'cos chief of staff'].includes(plainTitle(r.title))
const cosRow = (rows: Row[]) => rows.filter(isCos).sort((a, b) => (a.at < b.at ? 1 : -1))[0]

const snap = atom({ plugin: 'workspace-sidebar', key: 'snap' } as const,
  { rows: [], error: '', fetchedAt: 0, waiting: [], flagNote: '', actions: [], coos: [] } as Snapshot, { shape: 'snap-4' })

// Panel settings, written by `cos.py sidebar` from the config: where the reports are and whose actions count.
type Settings = { reportsDir: string; dataRoot: string; ownerName: string; projects: string[]; tickGate: string[] }
let settings: Settings = { reportsDir: '', dataRoot: '', ownerName: '', projects: [], tickGate: [] }
async function loadSettings($: any) {
  try {
    const j = JSON.parse(String(await $.fs.read(`${flagDir($)}/sidebar.json`)))
    settings = {
      reportsDir: String(j.reportsDir || ''),
      dataRoot: String(j.dataRoot || ''),
      ownerName: String(j.ownerName || ''),
      projects: Array.isArray(j.projects) ? j.projects.map(String) : (j.tiers?.[0]?.sections || []).map(String),
      tickGate: Array.isArray(j.tickGate) ? j.tickGate.map(String) : [],
    }
  } catch {}
}

const textOf = (content: unknown): string =>
  Array.isArray(content) ? content.map((c: any) => (c && c.type === 'text' ? c.text : '')).join('') : ''

function parseSnap(content: unknown): Partial<Snapshot> {
  try {
    const text = textOf(content)
    let raw: unknown
    try {
      raw = JSON.parse(text || '[]')
    } catch {
      return { error: text.slice(0, 400) || 'Empty reply from the session list' }
    }
    const rows: Row[] = (Array.isArray(raw) ? raw : []).map((s: any) => ({
      id: String(s.sessionId),
      title: String(s.title || s.name || 'Untitled'),
      link: String(s.link || ''),
      group: s.group?.name ? String(s.group.name) : '',
      running: !!s.isRunning,
      at: String(s.lastActivityAt || ''),
      parent: s.startedBy && !s.detached ? String(s.startedBy) : '', // detached = moved to top level
    }))
    return { rows, error: '', fetchedAt: Date.now() }
  } catch (err) {
    return { error: String((err as Error)?.message || err) }
  }
}

// The app spills a large list to a file and returns its path; read it from there.
async function loadSessions($: any): Promise<Partial<Snapshot>> {
  try {
    const res = await $.mcp.call('ccd_session_mgmt', 'list_sessions', { limit: 1000 })
    const text = textOf(res.content)
    const spilled = /saved to (\S+?\.txt)/.exec(text)
    if (spilled && spilled[1]) {
      if (!home) home = spilled[1].split('/.claude/')[0] || ''
      const body = await $.fs.read(spilled[1])
      return parseSnap([{ type: 'text', text: body }])
    }
    return parseSnap(res.content)
  } catch (err) {
    return { error: `Couldn't reach the session list: ${String((err as Error)?.message || err)}` }
  }
}

// "Needs your input": each session flags itself in a shared folder when it asks
// the user something, and clears the flag when the user answers.
// HOME from the environment; else learned from the app's own spill-file path.
let home = ''
// $.env.get is async: String() of it was "[object Promise]", which became a
// folder of that name in the working directory. Await it before any flagDir use.
async function ensureHome($: any) {
  if (home) return
  try { home = String((await $.env.get('HOME')) || '') } catch {}
}
const flagDir = (_$: any) => `${home}/.claude/needs-input`
let flagged = false

// This session's own sidebar facts (parent, group, pin), read once.
type SelfInfo = { parent: string; detached: boolean; group: string; pinned: boolean }
let selfInfo: SelfInfo | null = null
async function getSession($: any, id: string): Promise<any> {
  const res = await $.mcp.call('ccd_session_mgmt', 'get_session', { session_id: id })
  return JSON.parse(textOf(res.content) || '{}')
}
async function readSelf($: any): Promise<SelfInfo> {
  if (selfInfo) return selfInfo
  try {
    const s = await getSession($, 'self')
    selfInfo = {
      parent: s.parentSessionId ? String(s.parentSessionId) : '',
      detached: !!s.detached,
      group: s.group?.id ? String(s.group.id) : '',
      pinned: !!s.pinned,
    }
  } catch {
    selfInfo = { parent: '', detached: false, group: '', pinned: false }
  }
  return selfInfo
}
const isChild = (i: SelfInfo) => !!i.parent && !i.detached

// Auto-pinning is OFF: detached COOs and workers were pinning themselves
// whenever they asked something. Needs-input shows in the Workspace panel and the Chief of Staff
// brief instead. Pins are only ever set by you. Never re-enable without the Chief of Staff's say-so.
async function pinForAttention(_$: any, _waiting: boolean) {}

// Left sidebar: a child session files itself under its coordinator's section.
async function fileUnderParent($: any) {
  try {
    const me = await readSelf($)
    if (!isChild(me) || me.group) return
    const parent = await getSession($, me.parent)
    const section = parent?.group?.id
    if (section) await $.mcp.call('ccd_sidebar', 'move_sessions', { session_ids: ['self'], section_id: String(section) })
  } catch {}
}

async function readIndex($: any): Promise<Record<string, Waiting>> {
  await ensureHome($)
  try {
    const j = JSON.parse(String(await $.fs.read(`${flagDir($)}/index.json`)))
    return j && typeof j === 'object' ? j : {}
  } catch {
    return {}
  }
}

// One index file holds every waiting session: a single read, no folder listing.
async function setFlag($: any, reason: string | null) {
  await ensureHome($)
  if (!reason && !flagged) return
  try {
    const id = await $.session.id()
    const idx = await readIndex($)
    if (reason) idx[id] = { id, reason, at: new Date().toISOString() }
    else delete idx[id]
    await $.fs.write(`${flagDir($)}/index.json`, JSON.stringify(idx))
    flagged = !!reason
    await pinForAttention($, !!reason)
  } catch (err) {
    flagError = `write: ${String((err as Error)?.message || err)}`
  }
}

let flagError = ''
// A flag is live only while its session still exists and hasn't moved on since asking:
// activity more than 3 minutes after the flag means the question was answered (or the
// session ran on without a reply) and the flag was never cleared, e.g. it was written
// before this mod loaded in that session.
const FLAG_GRACE_MS = 3 * 60000
function liveFlags(flags: Waiting[], rows: Row[]): Waiting[] {
  if (!rows.length) return flags
  const byId = new Map(rows.map(r => [r.id.replace(/^local_/, ''), r]))
  return flags.filter(w => {
    const r = byId.get(String(w.id).replace(/^local_/, ''))
    return !!r && !(Date.parse(r.at) > Date.parse(w.at) + FLAG_GRACE_MS)
  })
}

// The Chief of Staff session writes cos-brief.json; the panel shows it as-is.
async function readCos($: any): Promise<Brief | null> {
  try { return JSON.parse(String(await $.fs.read(`${flagDir($)}/cos-brief.json`))) } catch { return null }
}

async function readFlags($: any, rows: Row[]): Promise<Waiting[]> {
  await ensureHome($)
  flagError = ''
  try {
    const raw = await $.fs.read(`${flagDir($)}/index.json`)
    const idx = JSON.parse(String(raw))
    return liveFlags(Object.values(idx || {}) as Waiting[], rows)
  } catch (err) {
    flagError = `Couldn't read ${flagDir($)}/index.json: ${String((err as Error)?.message || err)}`
    return []
  }
}

// Opens a session in the app through its claude:// link (a Pane Link only takes https).
async function openSession($: any, link: string) {
  if (!link) return
  try { await $.process.run(['open', link]) } catch {}
}

// A brief's session id → its claude:// link: an exact row, else a row whose id starts with
// it (old 8-char ids), else the app's link built from a full id the list didn't load.
function linkFor(rows: Row[], id: string): string {
  const bare = String(id || '').replace(/^local_/, '')
  if (!bare) return ''
  const r = rows.find(x => x.id.replace(/^local_/, '') === bare) || rows.find(x => x.id.replace(/^local_/, '').startsWith(bare))
  if (r?.link) return r.link
  return /^[0-9a-f-]{36}$/.test(bare) ? `claude://claude.ai/epitaxy/local_${bare}` : ''
}


// ── External relay (optional, OFF by default) ────────────────────────────────
// Out: every refresh writes sessions.json (what's open, what waits on you) for any
// outside tool (a phone bot, a script) to read. In: only when the file relay-on exists in
// the needs-input folder, it also delivers relay/<any>.json = {"to": "local_…", "text": "…"}
// to that session (one session claims each file with an atomic `mv`). Anything that can
// write that folder can then message your sessions: turn it on only for a tool you trust.
const EXPORT_COUNT = 40
async function relayOn($: any): Promise<boolean> {
  try { return !!(await $.fs.exists(`${flagDir($)}/relay-on`)) } catch { return false }
}
async function exportSessions($: any, rows: Row[], waiting: Waiting[]) {
  await ensureHome($)
  try {
    const ids = new Set(rows.map(r => r.id))
    const top = rows.filter(r => !(r.parent && ids.has(r.parent)))
    const byId = new Map(rows.map(r => [r.id, r]))
    const pick = (r: Row) => ({ id: r.id, title: r.title, section: r.group.replace(/^\S+\s/, '') || 'Ungrouped', running: r.running, lastActivity: r.at })
    const out = {
      generatedAt: new Date().toISOString(),
      ...((await relayOn($)) ? { howToReply: `Write ${flagDir($)}/relay/<unique>.json as {"to":"<session id>","text":"<message>"}; delivered within ~60s, result lands in relay/sent/.` } : {}),
      needsInput: (waiting || []).map(w => ({ ...(byId.get(w.id) ? pick(byId.get(w.id)!) : { id: w.id }), asks: w.reason, since: w.at })),
      recent: top.sort((a, b) => (a.at < b.at ? 1 : -1)).slice(0, EXPORT_COUNT).map(pick),
    }
    await $.fs.write(`${flagDir($)}/sessions.json`, JSON.stringify(out, null, 1))
  } catch {}
}

async function drainRelay($: any) {
  await ensureHome($)
  if (!(await relayOn($))) return
  const dir = `${flagDir($)}/relay`
  let entries: any[] = []
  try { entries = await $.fs.list(dir) } catch { return }
  const me = await $.session.id()
  for (const f of entries) {
    if (f.kind !== 'file' || !String(f.name).endsWith('.json')) continue
    const src = `${dir}/${f.name}`
    let job: { to?: string; text?: string } = {}
    try { job = JSON.parse(String(await $.fs.read(src))) } catch { continue }
    if (!job.to || !job.text || job.to.replace(/^local_/, '') === String(me).replace(/^local_/, '')) continue // a session can't message itself; another one takes it
    const claimed = `${dir}/sent/${Date.now()}-${f.name}`
    try {
      await $.process.run(['mkdir', '-p', `${dir}/sent`])
      const mv = await $.process.run(['mv', '-n', src, claimed])
      if ((mv as any)?.exitCode !== 0 || (await $.fs.exists(src))) continue // another session won
    } catch { continue }
    let result = ''
    try {
      const res = await $.mcp.call('ccd_session_mgmt', 'send_message', { session_id: job.to, message: `[via relay] ${job.text}` })
      result = textOf(res.content)
    } catch (err) {
      result = `error: ${String((err as Error)?.message || err)}`
    }
    await $.fs.write(claimed, JSON.stringify({ ...job, deliveredBy: me, at: new Date().toISOString(), result }, null, 1))
  }
}


// ── Chief of Staff ticker ────────────────────────────────────────────────────
// The loop inside the CoS session dies when it closes or after 7 days. This is the
// durable wake: every refresh, if the brief is older than COS_STALE_MS and the session
// titled "⭐ 𝐂𝐇𝐈𝐄𝐅 𝐎𝐅 𝐒𝐓𝐀𝐅𝐅 ⭐" (or the older plain title) is idle, the first mod instance to write cos-tick.json
// (a 25-min guard stops repeats) sends it a one-line wake sentence. Never a bare
// "/chief-of-staff": peer-bare-command-drop.sh blocks bare slash commands and shows you an error card.

// ── Owner actions and COO lines from the report files ───────────────────────
// Parsed files are cached by modification time, so a minute tick reads only what changed.
const cache = new Map<string, { mtime: number; actions: Action[]; latest: CooLine | null }>()
let reportNote = ''
async function readReports($: any): Promise<{ actions: Action[]; coos: CooLine[] }> {
  const dir = settings.reportsDir
  if (!dir) { reportNote = 'No reports folder set: run cos.py sidebar'; return { actions: [], coos: [] } }
  let entries: any[] = []
  try { entries = await $.fs.list(dir) } catch (err) {
    reportNote = `Couldn't list ${dir}: ${String((err as Error)?.message || err)}`
    return { actions: [], coos: [] }
  }
  reportNote = ''
  const now = Date.now()
  const actions: Action[] = []
  const newest = new Map<string, CooLine>()
  for (const f of entries) {
    if (f.kind !== 'file' || !isReportFile(String(f.name))) continue
    const name = String(f.name)
    let hit = cache.get(name)
    if (!hit || hit.mtime !== f.mtimeMs) {
      try {
        const text = String(await $.fs.read(`${dir}/${name}`))
        const p = parseReport(text, name, now, settings.ownerName, settings.dataRoot, home)
        hit = { mtime: f.mtimeMs, ...p }
        cache.set(name, hit)
      } catch { continue }
    }
    // Actions are re-dated on every tick only through a fresh parse; drop ones past 24 h here.
    actions.push(...hit.actions.filter(a => now - a.at <= 24 * 3600e3))
    if (hit.latest) {
      // Freshness = when the COO last wrote the file.
      const line = { ...hit.latest, at: Math.min(f.mtimeMs, now) }
      const was = newest.get(line.name)
      if (!was || line.at > was.at) newest.set(line.name, line)
    }
  }
  const wanted = new Set([...settings.projects, 'Production', 'Communication_VP'])
  const coos = [...newest.values()].filter(l => !settings.projects.length || wanted.has(l.name)).sort((a, b) => b.at - a.at)
  return { actions, coos }
}

async function readMarks($: any): Promise<Record<string, Mark>> {
  try { return JSON.parse(String(await $.fs.read(`${flagDir($)}/owner-actions.json`))) || {} } catch { return {} }
}
async function mark($: any, a: Action, state: 'done' | 'later') {
  try {
    const marks = await readMarks($)
    marks[a.key] = { state, at: new Date().toISOString(), ...(state === 'later' ? { until: Date.now() + LATER_MS } : {}) }
    // Keep the file small: forget marks older than a week.
    for (const [k, m] of Object.entries(marks)) if (Date.now() - Date.parse(m.at) > 7 * 24 * 3600e3) delete marks[k]
    await $.fs.write(`${flagDir($)}/owner-actions.json`, JSON.stringify(marks, null, 1))
    if (state === 'done') {
      const cos = cosRow((await read($, snap)).rows)
      const me = String(await $.session.id()).replace(/^local_/, '')
      if (cos && cos.id.replace(/^local_/, '') !== me)
        await $.mcp.call('ccd_session_mgmt', 'send_message', { session_id: cos.id, message: `The owner marked done on the Workspace panel [${a.source}]: "${a.ask}"` })
    }
    if (a.source === 'brief' || a.source === 'session') {
      const dir = flagDir($)
      if (a.source === 'brief') {
        const brief = JSON.parse(String(await $.fs.read(`${dir}/cos-brief.json`)))
        brief.needsOwner = (brief.needsOwner || []).filter((x: any) => `brief:${x.id}:${x.ask}` !== a.key)
        await $.fs.write(`${dir}/cos-brief.json`, JSON.stringify(brief, null, 1))
      } else if (state === 'done' && a.sessionId) {
        const idx = JSON.parse(String(await $.fs.read(`${dir}/index.json`)))
        delete idx[a.sessionId]
        await $.fs.write(`${dir}/index.json`, JSON.stringify(idx))
      }
    }
  } catch {}
  await refresh($)
}

// Every open action, newest first: brief items, then waiting sessions, then report lines.
function collect(rows: Row[], waiting: Waiting[], cos: Brief | null | undefined, fromReports: Action[]): Action[] {
  const now = Date.now()
  const byId = new Map(rows.map(r => [r.id, r] as [string, Row]))
  const brief: Action[] = (cos?.needsOwner || []).map(q => ({
    key: `brief:${q.id}:${q.ask}`, source: 'brief', ask: q.ask, details: q.details || '', at: Date.parse(cos!.generatedAt) || now,
    links: [], sessionId: q.id, options: q.options, title: q.title, copy: q.copy,
  } as Action))
  const asks: Action[] = (waiting || [])
    .map(w => ({ w, r: byId.get(w.id) }))
    // a child whose coordinator is still active routes through that coordinator
    .filter((x): x is { w: Waiting; r: Row } => !!x.r && !(x.r.parent && byId.has(x.r.parent)))
    .map(({ w, r }) => ({ key: `session:${r.id}:${w.at}`, source: 'session', ask: w.reason, details: '', at: Date.parse(w.at) || now, links: [], sessionId: r.id, title: r.title } as Action))
  return [...brief, ...asks, ...dedupe(fromReports)]
}

// The session that wrote a report: "Acme_admin" -> "Acme admin COO"; roles by their title.
function cooSession(rows: Row[], name: string): Row | undefined {
  const want = name === 'Production' ? 'production vp' : name === 'Communication_VP' ? 'communication vp' : plainTitle(`${name.replace(/_/g, ' ')} COO`)
  const first = plainTitle(name.replace(/_/g, ' ')).split(' ')[0] || name.toLowerCase()
  const pick = (f: (t: string) => boolean) => rows.filter(r => f(plainTitle(r.title))).sort((a, b) => (a.at < b.at ? 1 : -1))[0]
  return pick(t => t === want || t === `cos ${want}`) || pick(t => /\bcoo$/.test(t) && t.startsWith(first))
}

async function openTarget($: any, kind: string, target: string, rows: Row[]) {
  if (kind === 'session') return openSession($, linkFor(rows, target))
  try { await $.process.run(['open', target]) } catch {}
}

// ── Chief of Staff ticker ────────────────────────────────────────────────────
// The loop inside the CoS session dies when it closes or after 7 days. This is the
// durable wake: every refresh, if the brief is older than COS_STALE_MS and the session
// titled "⭐ 𝐂𝐇𝐈𝐄𝐅 𝐎𝐅 𝐒𝐓𝐀𝐅𝐅 ⭐" (or the older plain title) is idle, the first mod instance to write cos-tick.json
// (a 25-min guard stops repeats) sends it a one-line wake sentence. Never a bare
// "/chief-of-staff": peer-bare-command-drop.sh blocks bare slash commands and shows you an error card.
// The guard command is cos.py tick-peek unless sidebar.json names another (tickGate).
// Every session runs this mod: only the holder of cos-ticker.json sends, and never within
// 5 min of the last tick (cos-tick.json), whatever changed.
const COS_STALE_MS = 35 * 60000
async function tickCos($: any, rows: Row[], cos: Brief | null) {
  try {
    const age = cos ? Date.now() - Date.parse(cos.generatedAt) : Infinity
    const dir = flagDir($)
    const target = cosRow(rows)
    const me = String(await $.session.id())
    if (!target || target.id.replace(/^local_/, '') === me.replace(/^local_/, '')) return // the CoS can't wake itself
    const now = Date.now()
    const leaseFile = `${dir}/cos-ticker.json`
    let lease: any = {}
    try { lease = JSON.parse(String(await $.fs.read(leaseFile))) } catch {}
    if (!holdsLease(lease, me, now)) return
    await $.fs.write(leaseFile, JSON.stringify({ by: me, at: new Date(now).toISOString() }))
    const tok = `${dir}/cos-tick.json`
    let last: any = {}
    try { last = JSON.parse(String(await $.fs.read(tok))) } catch {}
    if (!tickDue(last, now)) return
    // Shared with /loop pass entry: a recent full pass suppresses duplicate wakes,
    // but changed inbox/flags/reports always get through this five-minute guard.
    let changed = false
    let changedInputs = ''
    try {
      const cmd = settings.tickGate.length ? settings.tickGate : ['python3', `${home}/.claude/chief-of-staff/bin/cos.py`, 'tick-peek']
      const gate = await $.process.run(cmd)
      if (String(gate?.stdout || '').startsWith('SKIP:')) return
      changedInputs = String(gate?.stdout || '').trim()
      changed = changedInputs.startsWith('RUN: changed')
    } catch {} // fail open: an unavailable guard must never silence the Chief
    // The CoS writes selfClearedAt right before clear_session self: wake it now, not at 35 min.
    let cleared = ''
    try {
      const st = JSON.parse(String(await $.fs.read(`${dir}/cos-state.json`)))
      cleared = String(st.selfClearedAt || '')
      storedCosId = String(st.cosSessionId || '')
    } catch {}
    const fresh = !!cleared && (!cos || Date.parse(cleared) > Date.parse(cos.generatedAt))
    if (age < COS_STALE_MS && !fresh && !changed) return
    if (target.running) return
    if (changed && last.inputs === changedInputs) return // identical work was already woken; don't flood while running state catches up
    const bypass = fresh && last.cleared !== cleared // a fresh self-clear skips the 25-min guard once
    if (!bypass && !changed && Date.now() - Date.parse(last.at) < 25 * 60000) return
    const stamp = () => JSON.stringify({ at: new Date().toISOString(), by: me, to: target.id, cleared: fresh ? cleared : last.cleared, inputs: changed ? changedInputs : last.inputs })
    await $.fs.write(tok, stamp()) // claim first so a second window sees it
    await $.mcp.call('ccd_session_mgmt', 'send_message', { session_id: target.id, message: 'Chief of Staff tick from the Workspace sidebar: run your /chief-of-staff pass now.' })
    await $.fs.write(tok, stamp())
  } catch {}
}

// Your click on an option = your answer. Sent verbatim to the Chief of Staff, then the
// question leaves the brief and the flag is cleared.
async function answerQuestion($: any, a: Action, label: string) {
  try {
    const cosTarget = cosRow((await read($, snap)).rows)
    if (!cosTarget) return
    await $.mcp.call('ccd_session_mgmt', 'send_message', { session_id: cosTarget.id, message: `The owner answered on the Workspace card "${a.title || ''}" (session ${a.sessionId || ''}): "${a.ask}" → ${label}` })
  } catch {}
  await mark($, a, 'done')
}

async function gather($: any, rows: Row[]) {
  const waiting = await readFlags($, rows)
  const cos = await readCos($)
  const rep = await readReports($)
  const marks = await readMarks($)
  const actions = visible(collect(rows, waiting, cos, rep.actions), marks, Date.now())
  const flagNote = [flagError, reportNote].filter(Boolean).join(' · ')
  return { waiting, cos, actions, coos: rep.coos, flagNote }
}

async function refresh($: any) {
  await ensureHome($)
  await loadSettings($)
  const got = await loadSessions($)
  const rows = got.rows || (await read($, snap)).rows
  const g = await gather($, rows)
  await update($, snap, prev => ({ ...prev, ...got, ...g }))
  if (got.rows) await exportSessions($, got.rows, g.waiting)
  await drainRelay($)
  await tickCos($, rows, g.cos)
}

const ago = (ms: number, now: number) => {
  if (!ms) return ''
  const m = Math.max(0, Math.round((now - ms) / 60000))
  if (m < 60) return `${m}m`
  const h = Math.round(m / 60)
  return h < 48 ? `${h}h` : `${Math.round(h / 24)}d`
}
const pretty = (name: string) => name === 'Communication_VP' ? 'Communication VP' : name === 'Production' ? 'Production VP' : name.replace(/_/g, ' ')

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'workspace', description: 'Open the Workspace panel: your actions and every COO' })
    void $.ui.open({ id: PANE, title: TITLE })
    void fileUnderParent($)
    await refresh($)
    // Actions and COO lines every minute (cached by file time); the session list every fifth tick.
    let tick = 0
    $.clock.every(60000, async () => {
      tick += 1
      if (tick % 5 === 0) return refresh($)
      await drainRelay($)
      const g = await gather($, (await read($, snap)).rows)
      await update($, snap, prev => ({ ...prev, ...g }))
      await tickCos($, (await read($, snap)).rows, g.cos) // every minute, so a self-clear wakes within ~2 min
    })
    return next(e)
  })
  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    await refresh($)
    return done
  })

  on('command.run', { command: 'workspace' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })
    await refresh($)
    return { text: 'Workspace panel opened.' }
  })

  on('prompt.submit', async ($, e, next) => {
    await setFlag($, null)
    return next(e)
  })

  on('tool.call', { tool: 'AskUserQuestion' }, async ($, e, next) => {
    await setFlag($, 'Question')
    const done = await next(e)
    await setFlag($, null)
    return done
  })

  on('tool.call', { tool: 'ExitPlanMode' }, async ($, e, next) => {
    await setFlag($, 'Plan approval')
    const done = await next(e)
    await setFlag($, null)
    return done
  })

  on('tool.call', { tool: 'mcp__ccd_turn__wrap_up' }, async ($, e, next) => {
    const done = await next(e)
    const ask = (e as any).ask
    if (typeof ask === 'string' && ask.trim()) await setFlag($, ask.trim().slice(0, 90))
    return done
  })

  on('classic.PermissionRequest', async ($, e, next) => {
    await setFlag($, `Permission: ${e.tool_name}`)
    return next(e)
  })

  on('classic.PostToolUse', async ($, e, next) => {
    if (flagged && e.tool_name !== 'mcp__ccd_turn__wrap_up') await setFlag($, null)
    return next(e)
  })


  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const { rows, error, fetchedAt, actions, coos, flagNote, cos } = await read($, snap)
    const now = Date.now()
    const list = actions || []

    const card = (a: Action, i: number) => {
      const asker = a.source === 'brief' || a.source === 'session' ? (a.title || 'Chief of Staff') : pretty(a.source)
      const coo = a.source !== 'brief' && a.source !== 'session' ? cooSession(rows, a.source) : undefined
      const who = a.sessionId ? { kind: 'session', target: a.sessionId } : coo ? { kind: 'session', target: coo.id } : null
      return (
        <Box key={`act-${i}-${a.key.slice(0, 40)}`} flexDirection="column" gap="xs" padding="sm" borderStyle="round" borderColor="warning">
          <Box flexDirection="row" justifyContent="space-between" gap="sm">
            <Text size="footnote" weight="semibold" color="accent" wrap="truncate">{asker}</Text>
            <Text size="caption" dimColor>{ago(a.at, now)}</Text>
          </Box>
          <Text size="body" weight="semibold">{a.ask}</Text>
          {a.details ? <Text size="footnote" dimColor wrap="truncate">{a.details}</Text> : null}
          {a.copy ? (
            <Button key={`copy-${i}`} onPress={(press: any) => $.ui.copy({ text: a.copy!, surface: press?.surface })}>
              <Text size="caption" weight="semibold">⧉ Copy: {a.copy.slice(0, 60)}</Text>
            </Button>
          ) : null}
          {(a.options || []).filter(o => !/^later$/i.test(o.label)).map((o, oi) => (
            <Button key={`pick-${i}-${oi}`} onPress={() => answerQuestion($, a, o.label)}>
              <Text size="footnote" weight="semibold" color={o.recommended ? 'success' : undefined}>{o.recommended ? '★ ' : '○ '}{o.label}</Text>
            </Button>
          ))}
          <Box flexDirection="row" gap="sm" flexWrap="wrap">
            {a.links.slice(0, 3).map((l, li) => (
              <Button key={`link-${i}-${li}`} onPress={() => openTarget($, l.kind, l.target, rows)}>
                <Text size="footnote" weight="bold" color="accent">{l.label} ›</Text>
              </Button>
            ))}
            {who ? (
              <Button key={`who-${i}`} onPress={() => openTarget($, who.kind, who.target, rows)}>
                <Text size="footnote" color="accent">Open {a.source === 'brief' || a.source === 'session' ? 'session' : pretty(a.source)} ›</Text>
              </Button>
            ) : null}
            <Button key={`done-${i}`} onPress={() => mark($, a, 'done')}>
              <Text size="footnote" weight="semibold" color="success">✓ Done</Text>
            </Button>
            <Button key={`later-${i}`} onPress={() => mark($, a, 'later')}>
              <Text size="footnote" dimColor>Later</Text>
            </Button>
          </Box>
        </Box>
      )
    }

    const cosMe = cosRow(rows)
    return (
      <Box flexDirection="column" gap="md" paddingX="sm">
        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
          <Text size="footnote" dimColor>{fetchedAt ? `updated ${ago(fetchedAt, now) || 'now'} ago` : 'loading…'}</Text>
          <Button key="refresh" onPress={() => refresh($)}>Refresh</Button>
        </Box>
        {error ? <Text color="error" size="footnote">Couldn't load sessions: {error}</Text> : null}
        <Box key="actions" flexDirection="column" gap="sm" padding={list.length ? 'md' : undefined}
          borderStyle={list.length ? 'round' : undefined} borderColor={list.length ? 'warning' : undefined}
          backgroundColor={list.length ? 'rgba(245, 158, 11, 0.12)' : undefined}>
          <Text size="title" weight="bold" color={list.length ? 'warning' : undefined}>
            {list.length ? `🟠 Waiting on you · ${list.length}` : '✓ Nothing waiting on you'}
          </Text>
          {list.map(card)}
          {flagNote ? <Text size="caption" color="error">{flagNote}</Text> : null}
        </Box>
        <Box key="coos" flexDirection="column" gap="sm">
          <Text size="title" weight="bold">COOs</Text>
          {cos ? (
            <Box key="coo-cos" flexDirection="column" paddingLeft="sm">
              <Box flexDirection="row" justifyContent="space-between" gap="sm">
                <Button key="open-cos" onPress={() => openSession($, cosMe?.link || '')}>
                  <Text size="body" weight="semibold" color="accent">⭐ Chief of Staff</Text>
                </Button>
                <Text size="caption" color={now - Date.parse(cos.generatedAt) > STALE_MS ? 'error' : undefined} dimColor={now - Date.parse(cos.generatedAt) <= STALE_MS}>
                  {ago(Date.parse(cos.generatedAt), now)}
                </Text>
              </Box>
              <Text size="footnote">{cos.headline}</Text>
            </Box>
          ) : null}
          {(coos || []).map(c => {
            const s = cooSession(rows, c.name)
            const stale = now - c.at > STALE_MS
            return (
              <Box key={`coo-${c.name}`} flexDirection="column" paddingLeft="sm">
                <Box flexDirection="row" justifyContent="space-between" gap="sm">
                  <Button key={`open-coo-${c.name}`} onPress={() => openSession($, s?.link || '')}>
                    <Text size="body" weight="semibold" color={s?.running ? 'success' : undefined}>{s?.running ? '● ' : ''}{pretty(c.name)}</Text>
                  </Button>
                  <Text size="caption" color={stale ? 'error' : undefined} dimColor={!stale}>{stale ? '● ' : ''}{ago(c.at, now)}</Text>
                </Box>
                <Text size="footnote" dimColor wrap="truncate">{c.outcome}</Text>
              </Box>
            )
          })}
        </Box>
      </Box>
    )
  })
}
