# Branching Strategy

SentinelOps follows a Trunk-Based Development branching strategy:
- Short-lived feature branches (`feat/*`, `fix/*`, `docs/*`) are created from `main`.
- Feature branches are merged back to `main` frequently via Pull Requests.
- CI workflows validate code on every PR before merge is allowed.
