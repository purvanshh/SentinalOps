# SentinelOps Package Architecture

## 6-Package Separation

The repository is split into six packages with clear boundaries:

### sentinel-common
Shared foundation. Schemas, Protocol contracts, DTOs, and telemetry models used by all other packages. Zero runtime dependencies beyond the standard library.

### sentinel-runtime
Runtime agents, LangGraph orchestration, tool integrations, and safety engine. This is the operational core that processes live incidents. Depends on sentinel-common.

### sentinel-eval
Evaluation framework, benchmark suites, scoring (safety, calibration, grounding), and red-team adversarial testing. Runs against sentinel-runtime but never mutates production state. Depends on sentinel-common.

### sentinel-sim
Simulation layer: incident generators, synthetic environments, traffic simulation, and chaos/failure injection. Produces test data for sentinel-eval and development. Depends on sentinel-common.

### sentinel-ui
Next.js operator dashboard. Wraps `apps/web-dashboard`. Provides incident views, approval flows, trace visualization, and evaluation results.

### sentinel-docs
Architecture documentation, ADRs, API specs, and runbooks.

## Why This Separation

1. **Dependency isolation** — evaluation and simulation never ship to production runtime
2. **Independent versioning** — packages evolve at different rates
3. **Clear contracts** — sentinel-common defines the interface; other packages implement it
4. **Test boundary enforcement** — eval code cannot accidentally reach production paths
5. **Team ownership** — different packages can be owned by different teams
