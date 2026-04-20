"use client";

import { useEffect, useRef, useState } from "react";

import type { TraceEvent } from "./types";

export function useTraceStream(url: string): {
  events: TraceEvent[];
  connected: boolean;
} {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const src = new EventSource(url);
    sourceRef.current = src;

    src.onopen = () => setConnected(true);
    src.onerror = () => setConnected(false);

    const handler = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as TraceEvent;
        setEvents((prev) => [...prev, payload]);
      } catch {
        // ignore malformed payloads
      }
    };

    const kinds = [
      "thought", "action", "observation", "final", "error",
      "discovery", "decision", "invocation", "summary",
    ];
    kinds.forEach((k) => src.addEventListener(k, handler));
    src.addEventListener("message", handler);

    return () => {
      src.close();
    };
  }, [url]);

  return { events, connected };
}
