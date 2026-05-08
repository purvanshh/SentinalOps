CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY,
    incident_id UUID REFERENCES incidents(id),
    agent_name TEXT NOT NULL,
    input JSONB,
    output JSONB,
    latency DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
