export type TraceKind =
  | "thought"
  | "action"
  | "observation"
  | "final"
  | "error"
  | "discovery"
  | "decision"
  | "invocation"
  | "summary";

export interface TraceEvent {
  brief_id?: string;
  job_id?: string;
  kind: TraceKind;
  summary: string;
  detail: Record<string, unknown>;
  at: string;
}

export interface CapabilityCatalog {
  service: string;
  description: string;
  capabilities: Array<{
    id: string;
    verb: string;
    path: string;
    summary: string;
    hints?: string[];
  }>;
}

export interface Envelope<T> {
  data: T;
  _self: string;
  _related: Array<{ rel: string; href: string; verb: string }>;
  _suggested_next: Array<{ rel: string; href: string; verb: string; example_body?: unknown }>;
  _generated_at: string;
}
