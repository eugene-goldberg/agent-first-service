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
  const disconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const src = new EventSource(url);
    sourceRef.current = src;

    const clearPendingDisconnect = () => {
      if (disconnectTimerRef.current !== null) {
        clearTimeout(disconnectTimerRef.current);
        disconnectTimerRef.current = null;
      }
    };

    src.onopen = () => {
      clearPendingDisconnect();
      setConnected(true);
    };
    src.onerror = () => {
      clearPendingDisconnect();
      disconnectTimerRef.current = setTimeout(() => setConnected(false), 1500);
    };

    const handler = (event: MessageEvent) => {
      clearPendingDisconnect();
      setConnected(true);
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
      clearPendingDisconnect();
      src.close();
    };
  }, [url]);

  return { events, connected };
}
