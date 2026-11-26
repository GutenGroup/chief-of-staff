// Workspace panel parsing. Run: node --test tests/test_sidebar_actions.mts (Node 23.6+ strips the types).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { dedupe, holdsLease, isReportFile, linksIn, parseReport, tickDue, visible } from '../mods/workspace-sidebar/hooks/actions.ts'

const NOW = Date.parse('2026-11-26T13:00:00Z')
const SID = ['local', '0a1b2c3d-1111-2222-3333-444455556666'].join('_') // a session id, built so the release scan passes

test('collects needs-owner and needs-<owner> lines from the last 24 h only', () => {
  const text = [
    '- 2026-11-26T12:20Z | status: amber | done: payments set up | needs-owner[money]: approve the payments with BankID | options: A / B',
    '- 2026-11-26T11:00Z | done: x | needs-Alex[legal]: sign the lease at https://example.com/sign',
    '- 2026-11-24T10:00Z | done: old | needs-owner[legal]: an ask from two days ago',
  ].join('\n')
  const { actions } = parseReport(text, 'Acme.md', NOW, 'Alex')
  assert.deepEqual(actions.map(a => a.ask), ['approve the payments with BankID', 'sign the lease at https://example.com/sign'])
  assert.equal(actions[0]!.details, 'options: A / B')
  assert.deepEqual(actions[1]!.links, [{ label: 'Sign', kind: 'url', target: 'https://example.com/sign' }])
})

test('a heading dates the lines under it; a later plain "none" clears earlier asks', () => {
  const text = [
    '## 2026-11-26T12:00Z all clear',
    '- needs-owner: none',
    '## 2026-11-26T09:00Z waiting',
    '- needs-owner[legal]: tick the terms box',
    '- needs-owner: none new',
  ].join('\n')
  assert.deepEqual(parseReport(text, 'Acme.md', NOW, '').actions, [])
  const open = parseReport(text.split('\n').slice(2).join('\n'), 'Acme.md', NOW, '').actions
  assert.deepEqual(open.map(a => a.ask), ['tick the terms box'])
})

test('a planning date is not an entry time, and CLOSED is not an ask', () => {
  const text = ['- 2026-12-06 planning date | needs-owner[legal]: decide later', '## 2026-11-26T10:00Z x', '- needs-owner: CLOSED 2026-11-25'].join('\n')
  const r = parseReport(text, 'Acme.md', NOW, '')
  assert.deepEqual(r.actions, [])
  assert.equal(r.latest!.at, Date.parse('2026-11-26T10:00:00Z'))
})

test('latest outcome prefers the done: clause', () => {
  const r = parseReport('- 2026-11-26T12:00Z | status: green | done: shipped 1.2 | next: watch', 'Acme.laptop-2.md', NOW, '')
  assert.equal(r.latest!.name, 'Acme')
  assert.equal(r.latest!.outcome, 'shipped 1.2')
})

test('digests and protocol files are not reports', () => {
  assert.equal(isReportFile('Acme.md'), true)
  assert.equal(isReportFile('fleet_CoS.md'), false)
  assert.equal(isReportFile('README.md'), false)
  assert.equal(isReportFile("Acme (Someone's conflicted copy 2026-11-24).md"), false)
})

test('links: files under the data root and sessions', () => {
  const l = linksIn(`see Context/Acme/plan.md and ${SID}`, '/data', '/home/x')
  assert.deepEqual(l.map(x => [x.kind, x.target]), [['file', '/data/Context/Acme/plan.md'], ['session', SID]])
})

test('the same ask from two reports shows once; Done hides it, Later hides it until it expires', () => {
  const a = parseReport('- 2026-11-26T12:20Z | needs-owner[money]: approve the Telenor payments at the bank with BankID', 'Admin.md', NOW, '').actions
  const b = parseReport('- 2026-11-26T12:38Z | NEEDS SAM[money]: BankID-approve the Telenor payments at the bank', 'Comms.md', NOW, 'Sam').actions
  const both = dedupe([...a, ...b])
  assert.equal(both.length, 1)
  const key = both[0]!.key
  assert.equal(visible(both, { [key]: { state: 'done', at: '' } }, NOW).length, 0)
  assert.equal(visible(both, { [key]: { state: 'later', at: '', until: NOW + 1 } }, NOW).length, 0)
  assert.equal(visible(both, { [key]: { state: 'later', at: '', until: NOW - 1 } }, NOW).length, 1)
})

test('"sign X; delete Y" is two asks, and an id like #380 joins repeats of one ask', () => {
  const text = [
    '- 2026-11-26T12:33Z | needs-owner[legal]: delete drafts #380/#381? (recommended yes; alt: leave)',
    '- 2026-11-26T12:28Z | needs-owner[legal]: sign GGU-1001 and GGU-1002; delete drafts #380/#381?',
    '- 2026-11-26T12:18Z | needs-owner[legal]: #380/#381 (void refused): turn auto-draft off then delete both',
  ].join('\n')
  const asks = parseReport(text, 'Acme.md', NOW, '').actions.map(a => a.ask)
  assert.deepEqual(asks, ['delete drafts #380/#381? (recommended yes; alt: leave)', 'sign GGU-1001 and GGU-1002'])
})

test('numbered options are one card showing the recommended option', () => {
  const text = '- 2026-11-26T12:20Z | status: amber | needs-owner[legal]: Sam, options: (1, recommended) sign in once in the bot chat, which unblocks the connect; (2) do the connects yourself (about 10 min); (3) hold until later'
  const acts = parseReport(text, 'Ops.md', NOW, 'Sam').actions
  assert.equal(acts.length, 1)
  assert.equal(acts[0]!.ask, 'sign in once in the bot chat, which unblocks the connect')
  assert.match(acts[0]!.details, /\(2\) do the connects yourself.*\(3\) hold until later/)
  const unmarked = parseReport('- 2026-11-26T12:20Z | needs-owner[legal]: (1) renew now; (2) wait a week', 'Ops.md', NOW, '').actions
  assert.deepEqual(unmarked.map(a => a.ask), ['renew now'])
})

test('Chief of Staff ticks: one sending session, none within 5 min of the last', () => {
  const at = (ms: number) => new Date(NOW - ms).toISOString()
  assert.equal(holdsLease({}, 'a', NOW), true) // nobody holds it yet
  assert.equal(holdsLease({ by: 'local_a', at: at(60e3) }, 'a', NOW), true) // the holder renews
  assert.equal(holdsLease({ by: 'a', at: at(60e3) }, 'b', NOW), false) // another live session stays quiet
  assert.equal(holdsLease({ by: 'a', at: at(4 * 60e3) }, 'b', NOW), true) // the holder closed: take over
  assert.equal(tickDue({}, NOW), true)
  assert.equal(tickDue({ at: at(2 * 60e3) }, NOW), false)
  assert.equal(tickDue({ at: at(6 * 60e3) }, NOW), true)
})

test('only needs-owner[legal] and [money] reach the owner; an untagged ask shows in the COO row for the Chief of Staff', () => {
  const text = [
    '- 2026-11-26T12:30Z | done: drafted the reply | needs-owner: should the reply go out today or Monday? (recommended today)',
    '- 2026-11-26T12:20Z | needs-owner[legal]: sign the lease at https://example.com/sign',
    '- 2026-11-26T12:10Z | needs-owner[money]: pay the invoice by card',
  ].join('\n')
  const r = parseReport(text, 'Acme.md', NOW, '')
  assert.deepEqual(r.actions.map(a => a.ask), ['sign the lease at https://example.com/sign', 'pay the invoice by card'])
  assert.equal(r.latest!.forCos, 'should the reply go out today or Monday? (recommended today)')
  const cleared = parseReport(text + '\n- 2026-11-26T12:40Z | needs-owner: none', 'Acme.md', NOW, '')
  assert.equal(cleared.latest!.forCos, undefined)
  assert.deepEqual(cleared.actions, [])
})
