// Same shapes as hooks/actions.ts (the contract must be self-contained).
export type Link = { label: string; kind: 'url' | 'file' | 'session'; target: string }
export type Action = {
  key: string; source: string; ask: string; details: string; at: number; links: Link[]; sessionId?: string
  options?: { label: string; why: string; recommended?: boolean }[]; title?: string; copy?: string
}
export type CooLine = { name: string; outcome: string; at: number }

export type Row = { id: string; title: string; link: string; group: string; running: boolean; at: string; parent: string }
export type Waiting = { id: string; reason: string; at: string }
export type Brief = { generatedAt: string; headline: string; cooking: { id: string; title: string; status: string; details?: string }[]; needsOwner: { id: string; title: string; ask: string; details?: string; copy?: string; options?: { label: string; why: string; recommended?: boolean }[] }[] }
export type Snapshot = { rows: Row[]; error: string; fetchedAt: number; waiting: Waiting[]; flagNote: string; cos?: Brief | null; actions: Action[]; coos: CooLine[] }

declare module 'claude-code' {
  interface PluginState {
    'workspace-sidebar': {
      snap: Shaped<Snapshot>
    }
  }
}
