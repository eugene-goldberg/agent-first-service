"use client";

import { useTraceStream } from "@/lib/useTraceStream";
import { TraceEventRow } from "./TraceEvent";

export function TracePanel({ title, url }: { title: string; url: string }) {
  const { events, connected } = useTraceStream(url);

  return (
    <div className="flex flex-col h-full border border-gray-800 rounded-lg overflow-hidden">
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-black/40">
        <h2 className="text-sm uppercase tracking-wider">{title}</h2>
        <span
          className={`text-xs px-2 py-1 rounded ${
            connected ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
          }`}
        >
          {connected ? "live" : "disconnected"}
        </span>
      </header>
      <div className="flex-1 min-h-0 overflow-y-scroll p-3 text-sm">
        {events.length === 0 && (
          <p className="opacity-50 text-xs">Waiting for trace events…</p>
        )}
        {events.map((ev, i) => (
          <TraceEventRow event={ev} key={`${ev.at}-${i}`} />
        ))}
      </div>
    </div>
  );
}
