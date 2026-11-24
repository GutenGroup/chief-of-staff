export type Row = { id: string; title: string; link: string; group: string; running: boolean; at: string; parent: string }
export type Waiting = { id: string; reason: string; at: string }
export type Brief = { generatedAt: string; headline: string; cooking: { id: string; title: string; status: string; details?: string }[]; needsOwner: { id: string; title: string; ask: string; details?: string; copy?: string; options?: { label: string; why: string; recommended?: boolean }[] }[] }
export type Snapshot = { rows: Row[]; error: string; fetchedAt: number; waiting: Waiting[]; flagNote: string; cos?: Brief | null }

declare module 'claude-code' {
  interface PluginState {
    'workspace-sidebar': {
      snap: Shaped<Snapshot>
      open: Shaped<string[]>
    }
  }
}
