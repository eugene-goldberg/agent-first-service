"use client";

import { useEffect, useState } from "react";

import type { CapabilityCatalog, Envelope } from "./types";

export function useServiceSnapshot(url: string, refreshMs = 3000) {
  const [catalog, setCatalog] = useState<CapabilityCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchOnce() {
      try {
        const resp = await fetch(url, { cache: "no-store" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const body = await resp.json();
        const raw = (body && typeof body === "object" && "data" in body) ? body.data : body;
        const normalized: CapabilityCatalog = {
          service: raw.service ?? "",
          description: raw.description ?? "",
          capabilities: (raw.capabilities ?? []).map((c: any, i: number) => ({
            id: c.id ?? c.intent ?? `cap-${i}`,
            verb: c.verb ?? c.method ?? "",
            path: c.path ?? "",
            summary: c.summary ?? c.returns ?? c.intent ?? "",
            hints: c.hints,
          })),
        };
        if (!cancelled) {
          setCatalog(normalized);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }

    fetchOnce();
    const id = setInterval(fetchOnce, refreshMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [url, refreshMs]);

  return { catalog, error };
}
