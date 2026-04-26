"use client";

import { useState } from "react";

import { useServiceSnapshot } from "@/lib/useServiceSnapshot";

export function ServiceSnapshot({ title, url }: { title: string; url: string }) {
  const { catalog, error } = useServiceSnapshot(url);
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex flex-col border border-gray-800 rounded-lg overflow-hidden">
      <header className="px-3 py-2 border-b border-gray-800 bg-black/40 flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-wider opacity-80">{title}</h2>
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="text-[10px] uppercase tracking-wider opacity-70 hover:opacity-100"
          aria-expanded={!collapsed}
          aria-label={collapsed ? `Expand ${title}` : `Collapse ${title}`}
        >
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </header>
      {!collapsed && (
        <div className="p-3 text-xs overflow-y-auto">
          {error && <p className="text-red-400">{error}</p>}
          {!catalog && !error && <p className="opacity-50">Loading…</p>}
          {catalog && (
            <>
              <p className="opacity-70 mb-2">{catalog.description}</p>
              <ul className="space-y-1">
                {catalog.capabilities.map((c) => (
                  <li key={c.id} className="flex gap-2">
                    <span className="shrink-0 text-amber-400 font-semibold w-14">{c.verb}</span>
                    <code className="shrink-0 opacity-80">{c.path}</code>
                    <span className="opacity-60 truncate">{c.summary}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
