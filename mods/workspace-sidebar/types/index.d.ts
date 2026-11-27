// Same shapes as hooks/actions.ts (the contract must be self-contained).
export type Link = { label: string; kind: 'url' | 'file' | 'session'; target: string }
export type Action = {
  key: string; source: string; ask: string; details: string; at: number; links: Link[]; sessionId?: string
  options?: { label: string; why: string; recommended?: boolean }[]; title?: string; copy?: string; packet?: Packet
}
export type Packet = {
  tag: 'legal' | 'money'; recommend: string; agree: string[]; checked: string[]
  verify: { label: string; value: string }[]; link: string; after: string; time: string
}
export type Decided = { id: string; title: string; what: string; why: string; source: string; undo: string }
export type CooLine = { name: string; outcome: string; at: number; forCos?: string }

export type Row = { id: string; title: string; link: string; group: string; running: boolean; at: string; parent: string }
export type Waiting = { id: string; reason: string; at: string }
export type Brief = { generatedAt: string; headline: string; cooking: { id: string; title: string; status: string; details?: string }[]; decided?: Decided[]; needsOwner: { id: string; title: string; ask: string; packet?: Partial<Packet>; details?: string; copy?: string; options?: { label: string; why: string; recommended?: boolean }[] }[] }
export type Snapshot = { rows: Row[]; error: string; fetchedAt: number; waiting: Waiting[]; flagNote: string; cos?: Brief | null; actions: Action[]; coos: CooLine[]; decided: Decided[]; permLine: string }

declare module 'claude-code' {
  interface PluginState {
    'workspace-sidebar': {
      snap: Shaped<Snapshot>
    }
  }
}
