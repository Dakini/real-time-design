export interface ComponentSpec {
  type: string;
  label: string;
  description: string;
  category: string;
  width: number;
  height: number;
}

export const PALETTE_CATEGORIES = [
  "General",
  "Data",
  "Messaging",
  "Network",
  "Compute",
  "AI",
] as const;

export const COMPONENT_LIBRARY: ComponentSpec[] = [
  { type: "service", label: "Service", description: "process", category: "General", width: 176, height: 60 },
  { type: "rounded", label: "Module", description: "rounded", category: "General", width: 176, height: 60 },
  { type: "boundary", label: "Boundary", description: "group / VPC", category: "General", width: 240, height: 140 },
  { type: "generic", label: "Component", description: "generic", category: "General", width: 160, height: 60 },

  { type: "relational-db", label: "Relational DB", description: "Postgres / MySQL", category: "Data", width: 176, height: 60 },
  { type: "nosql-db", label: "NoSQL DB", description: "document / wide-column", category: "Data", width: 176, height: 60 },
  { type: "cache", label: "Cache", description: "Redis / Memcached", category: "Data", width: 160, height: 60 },
  { type: "object-store", label: "Object Storage", description: "blobs / files", category: "Data", width: 176, height: 60 },
  { type: "warehouse", label: "Data Warehouse", description: "analytics", category: "Data", width: 176, height: 60 },

  { type: "queue", label: "Queue", description: "work items", category: "Messaging", width: 160, height: 60 },
  { type: "stream", label: "Event Stream", description: "topic / log", category: "Messaging", width: 176, height: 60 },
  { type: "pubsub", label: "Pub/Sub Broker", description: "fan-out", category: "Messaging", width: 176, height: 60 },

  { type: "client", label: "Client", description: "consumer", category: "Network", width: 160, height: 60 },
  { type: "browser-client", label: "Browser / Mobile", description: "end user", category: "Network", width: 176, height: 60 },
  { type: "api-gateway", label: "API Gateway", description: "authn · throttling", category: "Network", width: 176, height: 60 },
  { type: "load-balancer", label: "Load Balancer", description: "L4 / L7", category: "Network", width: 176, height: 60 },
  { type: "cdn", label: "CDN", description: "edge cache", category: "Network", width: 160, height: 60 },
  { type: "external-api", label: "External API", description: "third party", category: "Network", width: 176, height: 60 },

  { type: "server", label: "Server", description: "app instance", category: "Compute", width: 176, height: 60 },
  { type: "worker", label: "Worker", description: "background jobs", category: "Compute", width: 160, height: 60 },
  { type: "function", label: "Function", description: "serverless", category: "Compute", width: 160, height: 60 },
  { type: "cluster", label: "Container Cluster", description: "orchestrated", category: "Compute", width: 190, height: 60 },

  { type: "llm", label: "LLM / Model", description: "inference", category: "AI", width: 176, height: 60 },
  { type: "embedding", label: "Embedding Model", description: "vectorize", category: "AI", width: 190, height: 60 },
  { type: "vector-db", label: "Vector Database", description: "similarity search", category: "AI", width: 190, height: 60 },
  { type: "agent", label: "Agent / Tool", description: "orchestration", category: "AI", width: 176, height: 60 },
];

export function specFor(type: string): ComponentSpec | undefined {
  return COMPONENT_LIBRARY.find((c) => c.type === type);
}

export function categoryOf(type: string): string {
  return specFor(type)?.category ?? "General";
}
