import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Brief, Row, Snapshot, Waiting } from '../types'
import { LOGOS } from './logos'

const PANE = 'workspace-sidebar'
const TITLE = 'Workspace'
const PREVIEW = 4
// Virtual section: the newest top-level sessions from any group, like the app's Recents.
const LATEST = '__latest'
const LATEST_COUNT = 6
// The Chief of Staff session is found by title (it may carry stars or bold letters).
const plainTitle = (t: string) => t.normalize('NFKD').replace(/[^A-Za-z ]/g, '').replace(/\s+/g, ' ').trim().toLowerCase()
const isCos = (r: Row) => plainTitle(r.title) === 'chief of staff'
const cosRow = (rows: Row[]) => rows.filter(isCos).sort((a, b) => (a.at < b.at ? 1 : -1))[0]

const snap = atom({ plugin: 'workspace-sidebar', key: 'snap' } as const, { rows: [], error: '', fetchedAt: 0, waiting: [], flagNote: '' } as Snapshot, {
  shape: 'snap-3',
})
const open = atom({ plugin: 'workspace-sidebar', key: 'open' } as const, [] as string[], { shape: 'open-1' })

// Sidebar group name -> [tier, clean display name]. Order here is display order.
// The project tiers come from ~/.claude/needs-input/sidebar.json (written by install.sh from your config):
// {"tiers":[{"tier":"Projects","sections":["Acme","Side project"]}]}. A group name is shown with or without
// a leading emoji: sections "Acme" matches the sidebar group "🟦 Acme" and "Acme".
const TODAY = { tier: 'Today', sections: [['⭐ Chief of Staff', 'Chief of Staff'], [LATEST, 'Latest'], ['🟨 To do', 'To do']] as [string, string][] }
let TIERS: { tier: string; sections: [string, string][] }[] = [TODAY]
async function loadTiers($: any) {
  try {
    const cfg = JSON.parse(String(await $.fs.read(`${flagDir($)}/sidebar.json`)))
    const extra = (cfg?.tiers || []).map((t: any) => ({
      tier: String(t.tier || 'Projects'),
      sections: (t.sections || []).map((n: any) => [`🟦 ${String(n)}`, String(n)] as [string, string]),
    }))
    TIERS = [TODAY, ...extra]
  } catch {
    TIERS = [TODAY]
  }
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
// titled exactly "Chief of Staff" is idle, the first mod instance to write cos-tick.json
// (a 25-min guard stops repeats) sends it a one-line wake sentence. Never a bare
// "/chief-of-staff": peer-bare-command-drop.sh blocks bare slash commands and shows you an error card.
const COS_STALE_MS = 35 * 60000
async function tickCos($: any, rows: Row[], cos: Brief | null) {
  try {
    const age = cos ? Date.now() - Date.parse(cos.generatedAt) : Infinity
    const dir = flagDir($)
    // Shared with /loop pass entry: a recent full pass suppresses duplicate wakes,
    // but changed inbox/flags/reports always get through this five-minute guard.
    let changed = false
    let changedInputs = ''
    try {
      const gate = await $.process.run(['python3', `${home}/.claude/chief-of-staff/bin/cos.py`, 'tick-peek'])
      if (String(gate?.stdout || '').startsWith('SKIP:')) return
      changedInputs = String(gate?.stdout || '').trim()
      changed = changedInputs.startsWith('RUN: changed')
    } catch {} // fail open: an unavailable guard must never silence the Chief
    // The CoS writes selfClearedAt right before clear_session self: wake it now, not at 35 min.
    let cleared = ''
    try { cleared = String(JSON.parse(String(await $.fs.read(`${dir}/cos-state.json`))).selfClearedAt || '') } catch {}
    const fresh = !!cleared && (!cos || Date.parse(cleared) > Date.parse(cos.generatedAt))
    if (age < COS_STALE_MS && !fresh && !changed) return
    const target = cosRow(rows)
    if (!target || target.running) return
    const me = await $.session.id()
    if (target.id.replace(/^local_/, '') === String(me).replace(/^local_/, '')) return // can't message itself; another session's mod does it
    const tok = `${dir}/cos-tick.json`
    let last: any = {}
    try { last = JSON.parse(String(await $.fs.read(tok))) } catch {}
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
async function answerQuestion($: any, q: { id: string; title?: string; ask: string }, label: string) {
  try {
    // A click is your answer, routed to the Chief of Staff, which passes it on.
    const cosTarget = cosRow((await read($, snap)).rows)
    if (!cosTarget) return
    await $.mcp.call('ccd_session_mgmt', 'send_message', { session_id: cosTarget.id, message: `The owner answered on the Workspace card "${q.title || ''}" (session ${q.id}): "${q.ask}" → ${label}` })
    const dir = flagDir($)
    const brief = JSON.parse(String(await $.fs.read(`${dir}/cos-brief.json`)))
    brief.needsOwner = (brief.needsOwner || []).filter((x: any) => x.id !== q.id || x.ask !== q.ask)
    await $.fs.write(`${dir}/cos-brief.json`, JSON.stringify(brief, null, 1))
    const idx = JSON.parse(String(await $.fs.read(`${dir}/index.json`)))
    delete idx[q.id]
    await $.fs.write(`${dir}/index.json`, JSON.stringify(idx))
  } catch {}
  await refresh($)
}

async function refresh($: any) {
  await ensureHome($)
  await loadTiers($)
  const got = await loadSessions($)
  const waiting = await readFlags($, got.rows || (await read($, snap)).rows)
  const cos = await readCos($)
  const flagNote = flagError || `${waiting.length} flag(s) in ${flagDir($)}`
  await update($, snap, prev => ({ ...prev, ...got, waiting, flagNote, cos }))
  if (got.rows) await exportSessions($, got.rows, waiting)
  await drainRelay($)
  await tickCos($, got.rows || (await read($, snap)).rows, cos)
}

const ago = (iso: string, now: number) => {
  const t = Date.parse(iso)
  if (!t) return ''
  const m = Math.max(0, Math.round((now - t) / 60000))
  if (m < 60) return `${m}m`
  const h = Math.round(m / 60)
  return h < 48 ? `${h}h` : `${Math.round(h / 24)}d`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'workspace', description: 'Open the tiered Workspace panel' })
    void $.ui.open({ id: PANE, title: TITLE })
    void fileUnderParent($)
    await refresh($)
    // Flags every minute (cheap); the full session list every fifth tick.
    let tick = 0
    $.clock.every(60000, async () => {
      tick += 1
      if (tick % 5 === 0) return refresh($)
      await drainRelay($)
      const waiting = await readFlags($, (await read($, snap)).rows)
      const cos = await readCos($)
      const flagNote = flagError || `${waiting.length} flag(s) in ${flagDir($)}`
      await update($, snap, prev => ({ ...prev, waiting, flagNote, cos }))
      await tickCos($, (await read($, snap)).rows, cos) // every minute, so a self-clear wakes within ~2 min
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
    const els = $.ui.resolve(e)
    const { Box, Text, Button } = els
    const Svg = 'Svg' in els ? els.Svg : undefined
    const { rows, error, fetchedAt, waiting, flagNote, cos } = await read($, snap)
    const expanded = await read($, open)
    const now = Date.now()

    const byGroup = new Map<string, Row[]>()
    for (const r of rows) {
      const list = byGroup.get(r.group) || []
      list.push(r)
      byGroup.set(r.group, list)
    }
    for (const list of byGroup.values()) list.sort((a, b) => (a.at < b.at ? 1 : -1))
    const ids = new Set(rows.map(r => r.id))
    byGroup.set(
      LATEST,
      rows
        .filter(r => !(r.parent && ids.has(r.parent)))
        .sort((a, b) => (a.at < b.at ? 1 : -1))
        .slice(0, LATEST_COUNT),
    )

    const known = new Set(TIERS.flatMap(t => t.sections.map(s => s[0])))
    const other = [...byGroup.keys()].filter(g => !known.has(g))
    const tiers = [...TIERS]
    if (other.length) tiers.push({ tier: 'Other', sections: other.map(g => [g, g || 'Ungrouped'] as [string, string]) })

    const waitingIds = new Set((waiting || []).map(w => w.id))
    const toggle = (name: string) => update($, open, list => (list.includes(name) ? list.filter(n => n !== name) : [...list, name]))

    return (
      <Box flexDirection="column" gap="md" paddingX="sm">
        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
          <Text size="footnote" dimColor>
            {rows.length} sessions{fetchedAt ? ` · updated ${ago(new Date(fetchedAt).toISOString(), now) || 'now'} ago` : ''}
          </Text>
          <Button key="refresh" onPress={async () => {
            await refresh($)
          }}>Refresh</Button>
        </Box>
        {error ? <Text color="error" size="footnote">Couldn't load sessions: {error}</Text> : null}
        {(() => {
          const byId = new Map(rows.map(r => [r.id, r] as [string, Row]))
          const need = (waiting || [])
            .map(w => ({ w, r: byId.get(w.id) }))
            // a child whose coordinator is still active routes through that coordinator
            .filter((x): x is { w: Waiting; r: Row } => !!x.r && !(x.r.parent && byId.has(x.r.parent)))
            .sort((a, b) => (a.w.at < b.w.at ? 1 : -1))
          return (
            <Box key="needs-input" flexDirection="column" gap="sm" padding={need.length ? 'md' : undefined}
              borderStyle={need.length ? 'round' : undefined} borderColor={need.length ? 'warning' : undefined}
              backgroundColor={need.length ? 'rgba(245, 158, 11, 0.12)' : undefined}>
              <Text size="title" weight="bold" color={need.length ? 'warning' : undefined}>
                {need.length ? `🟠 Needs your input · ${need.length}` : '✓ Nothing needs your input'}
              </Text>
              {need.length ? null : <Text dimColor wrap="truncate">{'─'.repeat(200)}</Text>}
              {need.length ? need.map(({ w, r }) => (
                <Box key={`need-${r.id}`} flexDirection="column" paddingLeft="sm">
                  <Box flexDirection="row" justifyContent="space-between" gap="sm">
                    <Button key={`open-need-${r.id}`} onPress={() => openSession($, r.link)}>
                      <Text size="body" weight="semibold" wrap="truncate">{r.title}</Text>
                    </Button>
                    <Text size="caption" dimColor>{ago(w.at, now)}</Text>
                  </Box>
                  <Text size="footnote" dimColor wrap="truncate">{w.reason}</Text>
                </Box>
              )) : null}
              <Text size="caption" dimColor>{flagNote}</Text>
            </Box>
          )
        })()}
        {cos ? (
          <Box key="cos" flexDirection="column" gap="xs" padding="md" borderStyle="round" borderColor="accent">
            <Box flexDirection="row" justifyContent="space-between">
              {(() => {
                // Title opens the Chief of Staff session itself (newest one with that title).
                const me = rows.filter(isCos).sort((a, b) => (a.at < b.at ? 1 : -1))[0]
                return (
                  <Button key="open-cos-session" onPress={() => openSession($, me?.link || '')}>
                    <Text size="title" weight="bold" color="accent">⭐ {me?.running ? '● ' : ''}Chief of Staff ›</Text>
                  </Button>
                )
              })()}
              <Text size="caption" dimColor>{ago(cos.generatedAt, now)} ago</Text>
            </Box>
            <Text size="body">{cos.headline}</Text>
            {(cos.needsOwner || []).map((q, qi) => (
              <Box key={`ask-${q.id}-${qi}`} flexDirection="column" gap="xs" padding="sm" borderStyle="round" borderColor="warning">
                <Button key={`open-ask-${q.id}-${qi}`} onPress={() => openSession($, linkFor(rows, q.id))}>
                  <Text size="footnote" weight="semibold" color="accent">{q.title} ›</Text>
                </Button>
                <Text size="body" weight="semibold">{q.ask}</Text>
                {q.details ? <Text size="footnote">{q.details}</Text> : null}
                {q.copy ? (
                  <Box key={`copy-${q.id}-${qi}`} flexDirection="column" gap="xs" padding="sm" borderStyle="round" borderColor="secondary">
                    <Text size="footnote" mono>{q.copy}</Text>
                    <Button key={`copy-btn-${q.id}-${qi}`} onPress={(press: any) => $.ui.copy({ text: q.copy!, surface: press?.surface })}>
                      <Text size="caption" weight="semibold">⧉ Copy</Text>
                    </Button>
                  </Box>
                ) : null}
                {(q.options || []).map((o, oi) => (
                  <Box key={`ask-${q.id}-${qi}-${oi}`} flexDirection="column" paddingLeft="sm">
                    <Button key={`pick-${q.id}-${qi}-${oi}`} onPress={() => answerQuestion($, q, o.label)}>
                      <Text size="body" weight="semibold" color={o.recommended ? 'success' : undefined}>{o.recommended ? '★ ' : '○ '}{o.label}{o.recommended ? ' (Recommended)' : ''}</Text>
                    </Button>
                    <Text size="footnote" dimColor>{o.why}</Text>
                  </Box>
                ))}
              </Box>
            ))}
            {(cos.cooking || []).map(c => {
              const bare = String(c.id || '').replace(/^local_/, '')
              const r = bare ? rows.find(x => x.id.replace(/^local_/, '').startsWith(bare)) : undefined
              return (
                <Box key={`cos-${c.id}`} flexDirection="column" paddingLeft="sm">
                  <Button key={`open-cos-${c.id}`} onPress={() => openSession($, linkFor(rows, c.id))}>
                    <Text size="footnote" weight="semibold" color="accent" wrap="truncate">{r?.running ? '● ' : ''}{c.title} ›</Text>
                  </Button>
                  <Text size="footnote" dimColor>{c.status}</Text>
                  {c.details ? <Text size="footnote">{c.details}</Text> : null}
                </Box>
              )
            })}
          </Box>
        ) : null}
        {(() => {
          // Coordinators: top-level sessions that started other sessions, busiest first.
          const kids = new Map<string, Row[]>()
          for (const r of rows) if (r.parent && ids.has(r.parent)) kids.set(r.parent, [...(kids.get(r.parent) || []), r])
          // A worker the CoS detached and filed in its project's group counts under that group's COO.
          const isCoo = (r: Row) => /\bCOO\b/.test(r.title)
          for (const c of rows.filter(r => isCoo(r) && r.group && !(r.parent && ids.has(r.parent)))) {
            const have = new Set((kids.get(c.id) || []).map(k => k.id))
            const extra = rows.filter(r => r.group === c.group && r.id !== c.id && !have.has(r.id) && !isCoo(r) && !isCos(r) && !(r.parent && ids.has(r.parent)))
            if (extra.length) kids.set(c.id, [...(kids.get(c.id) || []), ...extra])
          }
          const coords = rows
            .filter(r => kids.has(r.id) && !(r.parent && ids.has(r.parent)))
            .map(r => ({ r, k: kids.get(r.id)! }))
            .map(x => ({ ...x, live: x.k.filter(k => k.running).length, wait: x.k.filter(k => waitingIds.has(k.id)).length, last: [x.r.at, ...x.k.map(k => k.at)].sort().pop() || '' }))
            .sort((a, b) => (b.live - a.live) || (a.last < b.last ? 1 : -1))
            .slice(0, 8)
          if (!coords.length) return null
          return (
            <Box key="coords" flexDirection="column" gap="sm">
              <Text size="title" weight="bold">Coordinators</Text>
              <Text dimColor wrap="truncate">{'─'.repeat(200)}</Text>
              {coords.map(({ r, k, live, wait, last }) => (
                <Box key={`coord-${r.id}`} flexDirection="column" paddingLeft="sm">
                  <Box flexDirection="row" justifyContent="space-between" gap="sm">
                    <Button key={`open-coord-${r.id}`} onPress={() => openSession($, r.link)}>
                      <Text size="body" weight="semibold" wrap="truncate" color={waitingIds.has(r.id) ? 'warning' : r.running ? 'success' : undefined}>
                        {waitingIds.has(r.id) ? '🟠 ' : r.running ? '● ' : ''}{r.title}
                      </Text>
                    </Button>
                    <Text size="caption" dimColor>{ago(last, now)}</Text>
                  </Box>
                  <Text size="footnote" dimColor>
                    {(r.group.replace(/^\S+\s/, '') || 'Ungrouped')} · {k.length} sessions{live ? ` · ${live} running` : ''}{wait ? ` · ${wait} waiting` : ''}
                  </Text>
                  {k.filter(c => c.running || waitingIds.has(c.id)).slice(0, 4).map(c => (
                    <Button key={`open-kid-${c.id}`} onPress={() => openSession($, c.link)}>
                      <Text size="footnote" wrap="truncate" color={waitingIds.has(c.id) ? 'warning' : 'success'}>
                        {'   '}{waitingIds.has(c.id) ? '🟠 ' : '● '}{c.title}
                      </Text>
                    </Button>
                  ))}
                </Box>
              ))}
            </Box>
          )
        })()}
        {tiers.map(t => {
          const present = t.sections.filter(([g]) => (byGroup.get(g) || []).length > 0)
          if (!present.length) return null
          return (
            <Box key={`tier-${t.tier}`} flexDirection="column" gap="sm">
              <Text size="title" weight="bold">{t.tier}</Text>
              <Text dimColor wrap="truncate">{'─'.repeat(200)}</Text>
              {present.map(([g, label]) => {
                const list = byGroup.get(g) || []
                const all = expanded.includes(g)
                const ordered = [...list.filter(r => waitingIds.has(r.id)), ...list.filter(r => !waitingIds.has(r.id))]
                const shown = all || g === LATEST ? ordered : ordered.slice(0, PREVIEW)
                const live = list.filter(r => r.running).length
                return (
                  <Box key={`sec-${g}`} flexDirection="column" gap="xs" paddingLeft="sm">
                    <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                      {(() => {
                        const logo = LOGOS[label]
                        if (!logo || !Svg) return <Text size="heading" weight="semibold">{label}</Text>
                        const ht = logo.ratio > 1.5 ? 20 : 22
                        const mark = <Svg source={logo.svg} alt={label} height={ht} width={Math.round(ht * logo.ratio)} />
                        return logo.ratio > 1.5 ? mark : (
                          <Box flexDirection="row" alignItems="center" gap="sm">
                            {mark}
                            <Text size="heading" weight="semibold">{label}</Text>
                          </Box>
                        )
                      })()}
                      <Text size="footnote" dimColor>
                        {list.some(r => waitingIds.has(r.id)) ? `🟠 ${list.filter(r => waitingIds.has(r.id)).length} waiting · ` : ''}
                        {live ? `${live} running · ` : ''}{list.length}
                      </Text>
                    </Box>
                    {shown.map(r => (
                      <Box key={`row-${r.id}`} flexDirection="row" justifyContent="space-between" paddingLeft="sm" gap="sm">
                        <Button key={`open-${r.id}`} onPress={() => openSession($, r.link)}>
                          <Text size={isCos(r) ? 'body' : 'footnote'} wrap="truncate" weight={waitingIds.has(r.id) || isCos(r) ? 'bold' : undefined}
                            color={waitingIds.has(r.id) ? 'warning' : isCos(r) ? 'accent' : r.running ? 'success' : undefined}>
                            {waitingIds.has(r.id) ? '🟠 ' : r.running ? '● ' : ''}
                            {r.title}
                          </Text>
                        </Button>
                        <Text size="caption" dimColor>{ago(r.at, now)}</Text>
                      </Box>
                    ))}
                    {list.length > PREVIEW && g !== LATEST ? (
                      <Button key={`more-${g}`} onPress={() => toggle(g)}>
                        <Text size="footnote" dimColor>{all ? 'Show less' : `Show all ${list.length}`}</Text>
                      </Button>
                    ) : null}
                  </Box>
                )
              })}
            </Box>
          )
        })}
      </Box>
    )
  })
}
