"use client";

import { useEffect, useState } from "react";

const PROJECTS_URL = "http://127.0.0.1:8001";

type Project = {
  id: string;
  name: string;
  description?: string;
};

type Task = {
  id: string;
  project_id: string;
  title: string;
  status: string;
  assignee_id: string | null;
  due_date: string | null;
};

export function CreatedProjectPanel({ refreshMs = 2000 }: { refreshMs?: number }) {
  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const projResp = await fetch(`${PROJECTS_URL}/projects`, { cache: "no-store" });
        if (!projResp.ok) throw new Error(`HTTP ${projResp.status}`);
        const projBody = await projResp.json();
        const list: Project[] = Array.isArray(projBody.data) ? projBody.data : [];
        if (list.length === 0) {
          if (!cancelled) {
            setProject(null);
            setTasks([]);
            setError(null);
          }
          return;
        }
        const latest = list[list.length - 1];
        const taskResp = await fetch(`${PROJECTS_URL}/projects/${latest.id}/tasks`, {
          cache: "no-store",
        });
        const taskBody = taskResp.ok ? await taskResp.json() : { data: [] };
        if (!cancelled) {
          setProject(latest);
          setTasks(Array.isArray(taskBody.data) ? taskBody.data : []);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }

    poll();
    const id = setInterval(poll, refreshMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [refreshMs]);

  return (
    <div className="h-full border border-gray-800 rounded-lg flex flex-col overflow-hidden">
      <header className="px-4 py-2 border-b border-gray-800 bg-black/40 flex items-center justify-between">
        <h2 className="text-sm uppercase tracking-wider">Created project</h2>
        {project && (
          <code className="text-xs opacity-60">{project.id}</code>
        )}
      </header>
      <div className="flex-1 min-h-0 overflow-y-scroll p-4 text-sm">
        {error && <p className="text-red-400 text-xs">{error}</p>}
        {!project && !error && (
          <p className="opacity-50 text-xs">No project created yet…</p>
        )}
        {project && (
          <div className="space-y-3">
            <div>
              <div className="text-xs opacity-60 uppercase tracking-wider mb-1">Name</div>
              <div className="text-amber-300 break-words">{project.name}</div>
            </div>
            {project.description && (
              <div>
                <div className="text-xs opacity-60 uppercase tracking-wider mb-1">Description</div>
                <div className="opacity-90 break-words">{project.description}</div>
              </div>
            )}
            <div>
              <div className="text-xs opacity-60 uppercase tracking-wider mb-1">
                Tasks ({tasks.length})
              </div>
              {tasks.length === 0 ? (
                <p className="opacity-50 text-xs">No tasks yet.</p>
              ) : (
                <ul className="space-y-1">
                  {tasks.map((t) => (
                    <li key={t.id} className="flex gap-3 text-xs">
                      <span className="shrink-0 w-16 text-emerald-400 uppercase tracking-wider">
                        {t.status}
                      </span>
                      <span className="break-words flex-1">{t.title}</span>
                      <span className="opacity-50 shrink-0">
                        {t.assignee_id ?? "unassigned"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
