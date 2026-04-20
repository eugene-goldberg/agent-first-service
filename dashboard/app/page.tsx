import { BriefPanel } from "@/components/BriefPanel";
import { ServiceSnapshot } from "@/components/ServiceSnapshot";
import { TracePanel } from "@/components/TracePanel";

const CLIENT_AGENT_URL =
  process.env.NEXT_PUBLIC_CLIENT_AGENT_URL ?? "http://127.0.0.1:8080";
const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://127.0.0.1:8000";
const PROJECTS_URL = "http://127.0.0.1:8001";
const PEOPLE_URL = "http://127.0.0.1:8002";
const COMMUNICATIONS_URL = "http://127.0.0.1:8003";

export default function Page() {
  return (
    <main className="h-screen grid grid-rows-[auto,1fr] gap-4 p-4">
      <header className="flex items-baseline gap-6">
        <h1 className="text-xl tracking-wide">Agent-First Services — Live Demo</h1>
        <span className="text-xs opacity-60">
          Two agents cooperating through a self-describing API.
        </span>
      </header>

      <div className="grid grid-cols-12 gap-4 min-h-0">
        <div className="col-span-4 min-h-0 grid grid-rows-[auto,1fr] gap-4">
          <div className="h-40">
            <BriefPanel />
          </div>
          <div className="min-h-0">
            <TracePanel title="Client agent — /sse/client" url={`${CLIENT_AGENT_URL}/sse/client`} />
          </div>
        </div>

        <div className="col-span-4 min-h-0">
          <TracePanel title="Orchestrator — /sse/orchestrator" url={`${ORCHESTRATOR_URL}/sse/orchestrator`} />
        </div>

        <div className="col-span-4 min-h-0 grid grid-rows-3 gap-4">
          <ServiceSnapshot title="Projects (:8001)" url={`${PROJECTS_URL}/`} />
          <ServiceSnapshot title="People (:8002)" url={`${PEOPLE_URL}/`} />
          <ServiceSnapshot title="Communications (:8003)" url={`${COMMUNICATIONS_URL}/`} />
        </div>
      </div>
    </main>
  );
}
