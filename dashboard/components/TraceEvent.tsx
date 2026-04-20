"use client";

import { useState } from "react";

import type { TraceEvent as TraceEventT } from "@/lib/types";

const KIND_COLOR: Record<string, string> = {
  thought: "text-blue-400 border-blue-400/40",
  action: "text-amber-400 border-amber-400/40",
  observation: "text-emerald-400 border-emerald-400/40",
  final: "text-purple-400 border-purple-400/40",
  error: "text-red-400 border-red-400/40",
  discovery: "text-cyan-400 border-cyan-400/40",
  decision: "text-amber-400 border-amber-400/40",
  invocation: "text-emerald-400 border-emerald-400/40",
  summary: "text-purple-400 border-purple-400/40",
};

export function TraceEventRow({ event }: { event: TraceEventT }) {
  const [expanded, setExpanded] = useState(false);
  const color = KIND_COLOR[event.kind] ?? "text-gray-400 border-gray-500/40";
  const ts = new Date(event.at).toLocaleTimeString();

  return (
    <div className={`border-l-2 pl-3 py-2 mb-1 ${color}`}>
      <button
        className="w-full text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex gap-3 text-xs">
          <span className="uppercase tracking-wider opacity-80 w-24 shrink-0">
            {event.kind}
          </span>
          <span className="opacity-60 shrink-0">{ts}</span>
          <span className="truncate">{event.summary}</span>
        </div>
      </button>
      {expanded && (
        <pre className="mt-2 text-[11px] opacity-75 whitespace-pre-wrap break-all bg-black/30 p-2 rounded">
          {JSON.stringify(event.detail, null, 2)}
        </pre>
      )}
    </div>
  );
}
