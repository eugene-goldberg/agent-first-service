"use client";

import { useState } from "react";

const CLIENT_AGENT_URL =
  process.env.NEXT_PUBLIC_CLIENT_AGENT_URL ?? "http://127.0.0.1:8080";

export function BriefPanel() {
  const [brief, setBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setLastResult(null);
    try {
      const resp = await fetch(`${CLIENT_AGENT_URL}/client/briefs`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ brief }),
      });
      const body = await resp.json();
      setLastResult(`brief_id=${body.data.id}  status=${body.data.status}`);
      setBrief("");
    } catch (e) {
      setLastResult(`error: ${String(e)}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="h-full border border-gray-800 rounded-lg flex flex-col overflow-hidden">
      <header className="px-4 py-2 border-b border-gray-800 bg-black/40">
        <h2 className="text-sm uppercase tracking-wider">Presenter input</h2>
      </header>
      <form
        onSubmit={onSubmit}
        className="flex flex-col flex-1 p-4 gap-3"
      >
        <textarea
          className="flex-1 bg-black/40 border border-gray-800 rounded p-3 text-sm resize-none focus:outline-none focus:border-amber-400"
          placeholder="Type a brief like:  Build a marketing landing page for our Q3 launch."
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={4}
          disabled={submitting}
        />
        <div className="flex items-center justify-between">
          <button
            type="submit"
            disabled={submitting || !brief.trim()}
            className="px-4 py-2 bg-amber-500 text-black rounded text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? "Sending…" : "Send to client agent"}
          </button>
          {lastResult && (
            <span className="text-xs opacity-60">{lastResult}</span>
          )}
        </div>
      </form>
    </div>
  );
}
