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
        const body = (await resp.json()) as Envelope<CapabilityCatalog>;
        if (!cancelled) {
          setCatalog(body.data);
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
