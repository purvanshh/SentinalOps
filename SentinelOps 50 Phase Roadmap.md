# SentinelOps — 50-Phase Production Transformation Roadmap

**Version:** 1.0  
**Based on:** Technical Audit conducted 2026-07-06  
**Target State:** Production-grade, portfolio-worthy, enterprise-quality AIOps platform  
**Estimated Duration:** 4–6 months (part-time, 10–15 hrs/week) or 8–12 weeks (full-time)

---

## Milestones Overview

| Milestone | Phases | Definition of Done |
|-----------|--------|-------------------|
| **MVP Recovery** | 1–15 | The system completes a live incident lifecycle without halting. Core blockers removed. |
| **Algorithmic Competence** | 16–28 | Root-cause accuracy >50%. Confidence calibration ECE < 0.10. Deterministic fallback works. |
| **Production Hardening** | 29–42 | Deployed to staging with CI/CD, IaC, monitoring, and security hardening. |
| **Portfolio & Community** | 43–50 | Documented, versioned, contributor-friendly, and recruiter-presentable. |

---

## Phase Dependency Graph

```
Phases 1–5 (Foundation)
    ├──> Phases 6–10 (Security)
    │       └──> Phases 11–15 (Architecture Fix)
    │               ├──> Phases 23–28 (Core Algorithm) ──> Milestone: Algorithmic Competence
    │               └──> Phases 16–22 (Testing)
    │                       └──> Phases 29–32 (Telemetry)
    │                               ├──> Phases 33–36 (API/Frontend)
    │                               └──> Phases 37–42 (DevOps)
    │                                       └──> Phases 43–46 (Observability)
    │                                               └──> Phases 47–50 (Community)
    │                                                       └──> Milestone: Portfolio Ready
```

---

## Phase 1: Repository Renaming & Git Hygiene

### 1. Phase Title
Repository Identity Correction & Git History Sanitization

### 2. Objective
Eliminate the "SentinalOps" typo, establish professional repository hygiene, and learn how to manage repository identity without breaking downstream links.

### 3. Background Theory
Repository naming is part of your professional brand. GitHub redirects handle renames, but local clones, CI badges, and documentation links require updates. Git history rewriting (filter-branch, filter-repo) allows cleaning accidental commits of large files or secrets. **Conventional Commits** (Angular-style) create machine-readable history that enables automated changelog generation.

**Study:**
- [Conventional Commits specification](https://www.conventionalcommits.org/)
- `git-filter-repo` documentation (official GitHub replacement for filter-branch)
- GitHub Docs: "Renaming a repository"

### 4. Learning Outcomes
- Git history rewriting and cleanup
- Conventional Commits discipline
- Repository branding and professional presentation

### 5. Current Problems Being Solved
- Repository name typo damages credibility
- Attribution fix commits (`4068d6b`, `cded43e`, `4f6c458`) pollute history
- Inconsistent commit messages prevent automated tooling

### 6. Implementation Tasks
1. Rename GitHub repository to `SentinelOps` (Settings → Repository name)
2. Update all internal references in README, docs, and code comments
3. Squash the three attribution-fix commits into one using interactive rebase
4. Install `git-filter-repo` locally and verify no large files (>1MB) are in history
5. Create `.gitmessage` template enforcing Conventional Commits
6. Configure local Git hooks for commit message validation

### 7. Files to Modify
- GitHub repository settings
- `README.md` (all references)
- `docs/**/*.md`
- `apps/api-server/src/**/*.py` (module docstrings/comments)
- `apps/web-dashboard/**/*.tsx` (any hardcoded strings)
- New: `.gitmessage`

### 8. Best Practices
- Never rewrite public history on shared branches; here it's acceptable because zero forks/stars
- Use `git rebase -i HEAD~10` carefully; always create a backup branch
- Conventional Commits format: `type(scope): subject` where type ∈ {feat, fix, docs, refactor, test, chore}

### 9. Validation Checklist
- [ ] GitHub redirect from old URL works
- [ ] `git log --oneline -20` shows only conventional commit messages
- [ ] No attribution-fix commits remain in `main` history
- [ ] All internal links in README resolve correctly

### 10. Expected Deliverables
- Renamed repository `SentinelOps`
- Clean commit history (last 30 commits)
- `.gitmessage` template in repo root

### 11. Suggested Commit Strategy
```
chore(repo): rename repository from SentinalOps to SentinelOps
docs(readme): update all internal references to new repository name
chore(git): add conventional commit message template and squash attribution fixes
```

### 12. Difficulty
3/10

### 13. Estimated Time
2–3 hours

---

## Phase 2: Documentation Consolidation & README Rewrite

### 1. Phase Title
Information Architecture & Honest Positioning

### 2. Objective
Consolidate 8 root-level markdown reports into a coherent documentation hierarchy and rewrite the README to be honest, concise, and recruiter-friendly.

### 3. Background Theory
**Information Architecture (IA)** organizes content by user mental models, not by author convenience. A README is a *landing page*, not a product manual. The **Diátaxis framework** (Tutorial, How-To, Explanation, Reference) provides a proven structure for technical documentation. Honest positioning builds trust; inflated claims destroy it.

**Study:**
- Diátaxis Framework (diataxis.fr)
- "The Documentation System" by Divio
- GitHub's "About READMEs" best practices

### 4. Learning Outcomes
- Technical writing and information architecture
- Audience-aware documentation (recruiter vs. contributor vs. user)
- Honest product positioning

### 5. Current Problems Being Solved
- 8 root-level markdown files create clutter
- README claims "autonomous" while admitting "not autonomous-ready"
- Metric inflation (99.17% router accuracy) buried above 8.2% root-cause accuracy
- New contributor cannot start within 15 minutes

### 6. Implementation Tasks
1. Create `docs/reports/` and move all root-level `*.md` reports there
2. Rewrite README into four sections: What/Why (2 paragraphs), Quickstart (5 commands), Architecture (1 diagram), Status (honest metrics table)
3. Create `docs/getting-started.md` with 15-minute onboarding
4. Create `docs/architecture/current.md` with Mermaid diagrams from README
5. Add a prominent "Current Limitations" section at the top of README
6. Fix metric presentation: lead with 8.2% root-cause accuracy, not 99.17% router accuracy

### 7. Files to Modify
- `README.md` (rewrite)
- Move: `FINAL_SYSTEM_STATUS.md`, `KNOWN_LIMITATIONS.md`, `PRODUCTION_READINESS_AUDIT.md`, `REPRODUCIBILITY_REPORT.md`, `RUNTIME_DIAGNOSTICS_REPORT.md`, `ADVERSARIAL_EVALUATION_REPORT.md`, `ARCHITECTURE_VALIDATION_REPORT.md`, `BENCHMARK_INTEGRITY_REPORT.md` → `docs/reports/`
- New: `docs/getting-started.md`
- New: `docs/architecture/current.md`

### 8. Best Practices
- README should be scannable in 60 seconds
- Every claim must have evidence immediately following or linked
- Use absolute paths in docs, relative paths in README
- Limit README to <150 lines; move depth to `docs/`

### 9. Validation Checklist
- [ ] `ls *.md` in repo root returns only README, LICENSE, CONTRIBUTING, SECURITY, CHANGELOG
- [ ] README can be fully understood in 3 minutes
- [ ] All moved reports have working redirects (GitHub handles this automatically)
- [ ] A peer can start the system in 15 minutes using only `docs/getting-started.md`

### 10. Expected Deliverables
- Restructured `docs/` hierarchy
- Rewritten `README.md` (<150 lines)
- `docs/getting-started.md`

### 11. Suggested Commit Strategy
```
docs(structure): consolidate root-level reports into docs/reports/
docs(readme): rewrite with honest positioning and clear quickstart
docs(onboarding): add 15-minute getting-started guide
```

### 12. Difficulty
4/10

### 13. Estimated Time
4–6 hours

---

## Phase 3: Dependency Pinning & Reproducible Builds

### 1. Phase Title
Supply Chain Security & Build Reproducibility

### 2. Objective
Replace all `:latest` Docker tags and unpinned Python dependencies with cryptographically verified, reproducible builds.

### 3. Background Theory
**Supply chain attacks** (e.g., xz backdoor, Codecov breach) exploit unpinned dependencies. Docker image digests (SHA-256) guarantee bit-for-bit reproducibility. `pip-compile` (from `pip-tools`) or Poetry lock files resolve transitive dependencies deterministically. **SBOMs** (Software Bill of Materials) are increasingly required by enterprise customers and government regulations.

**Study:**
- SLSA Framework (Supply-chain Levels for Software Artifacts)
- Docker Content Trust / Notary
- `pip-tools` documentation
- OWASP Dependency-Check

### 4. Learning Outcomes
- Supply chain security fundamentals
- Deterministic dependency resolution
- Docker image digest verification
- SBOM generation

### 5. Current Problems Being Solved
- `qdrant/qdrant:latest`, `grafana/grafana:latest`, `prom/prometheus:latest` — non-reproducible
- No lock file for Python dependencies
- No evidence of dependency vulnerability scanning

### 6. Implementation Tasks
1. Audit all Docker images in `docker-compose.yml` and `Dockerfile`
2. Replace `:latest` with specific version tags (e.g., `qdrant/qdrant:v1.9.0`)
3. Look up SHA-256 digests for each image and add comments in compose file
4. Convert `requirements.txt` to `pyproject.toml` with Poetry or `pip-tools`
5. Generate `poetry.lock` or `requirements.lock`
6. Add `pip-audit` or `safety` to dev dependencies
7. Generate SBOM with `syft` or `trivy` and commit to `docs/security/sbom.json`

### 7. Files to Modify
- `docker-compose.yml`
- `apps/api-server/Dockerfile`
- `apps/web-dashboard/Dockerfile`
- `apps/api-server/requirements.txt` → convert to `pyproject.toml`
- New: `poetry.lock` or `requirements.lock`
- New: `docs/security/sbom.json`

### 8. Best Practices
- Never use `:latest` in production contexts
- Pin transitive dependencies, not just direct ones
- Store SBOMs with every release
- Use `hadolint` to lint Dockerfiles

### 9. Validation Checklist
- [ ] `docker-compose config` resolves without `:latest` tags
- [ ] `poetry install` or `pip-sync` produces identical environment on two different machines
- [ ] `pip-audit` runs with zero high-severity vulnerabilities (or documented exceptions)
- [ ] SBOM file exists and is <30 days old

### 10. Expected Deliverables
- Pinned `docker-compose.yml`
- `pyproject.toml` with full dependency specification
- Lock file
- SBOM document

### 11. Suggested Commit Strategy
```
build(docker): pin all image versions to specific tags with SHA digests
build(deps): migrate requirements.txt to pyproject.toml with poetry
chore(security): add pip-audit and generate initial SBOM
```

### 12. Difficulty
5/10

### 13. Estimated Time
4–6 hours

---

## Phase 4: Repository Structure Cleanup

### 1. Phase Title
Dead Code Elimination & Cohesion Improvement

### 2. Objective
Remove empty directories, consolidate template duplication, and establish clear module boundaries.

### 3. Background Theory
**Cohesion** measures how closely related the responsibilities within a module are. **Coupling** measures inter-module dependency. Empty directories (`infrastructure/kubernetes/`, `infrastructure/terraform/`) signal unfinished work and confuse contributors. The **Template Method pattern** can eliminate the repetitive `agent.py` + `prompts.py` + `output_schema.py` triplication across 8+ agents.

**Study:**
- "Clean Code" by Robert C. Martin (Ch. 17: Smells and Heuristics)
- Template Method Pattern (GoF)
- Python `__init__.py` best practices (PEP 420)

### 4. Learning Outcomes
- Code smell identification
- Refactoring for DRY compliance
- Module boundary design

### 5. Current Problems Being Solved
- Empty `infrastructure/kubernetes/` and `infrastructure/terraform/` directories
- Identical file trios across 8 agent directories (template duplication)
- `apps/api-server/src/__init__.py` at `src/` level causing import confusion
- Deep nesting in `agents/rootcause_agent/` (11 files)

### 6. Implementation Tasks
1. Delete empty directories or add `.gitkeep` with explanatory README
2. Create `agents/_base/` with `BaseAgent`, `BasePrompts`, `BaseOutputSchema`
3. Refactor one agent (e.g., `metrics_agent`) to inherit from base classes
4. Verify all other agents can follow the same pattern
5. Remove `apps/api-server/src/__init__.py` if not needed (check imports first)
6. Move `agents/rootcause_agent/causal_validator.py`, `deductive_tester.py` to `causality/validators/` if they are domain utilities, not agent-specific

### 7. Files to Modify
- Delete or populate: `infrastructure/kubernetes/`, `infrastructure/terraform/`
- New: `apps/api-server/src/agents/_base/base_agent.py`
- New: `apps/api-server/src/agents/_base/base_prompts.py`
- New: `apps/api-server/src/agents/_base/base_output_schema.py`
- Refactor: `apps/api-server/src/agents/metrics_agent/`
- Move: `apps/api-server/src/agents/rootcause_agent/causal_validator.py` → `apps/api-server/src/causality/validators/`
- Move: `apps/api-server/src/agents/rootcause_agent/deductive_tester.py` → `apps/api-server/src/causality/validators/`

### 8. Best Practices
- Base classes should define the contract, not the implementation
- Keep agent-specific logic in agent directories; domain logic in domain directories
- Run `vulture` or `pylint --disable=all --enable=W0611` to find unused imports

### 9. Validation Checklist
- [ ] `find infrastructure -type d -empty` returns nothing
- [ ] `metrics_agent` successfully uses base classes
- [ ] All tests still pass after import moves
- [ ] No circular import errors

### 10. Expected Deliverables
- Clean directory structure
- Base agent framework
- Refactored `metrics_agent` as proof of concept

### 11. Suggested Commit Strategy
```
refactor(structure): remove empty infrastructure directories
refactor(agents): introduce BaseAgent, BasePrompts, BaseOutputSchema
refactor(causality): move domain validators out of agent directory
```

### 12. Difficulty
5/10

### 13. Estimated Time
6–8 hours

---

## Phase 5: Git Workflow & Collaboration Infrastructure

### 1. Phase Title
Branching Strategy, Templates & Release Foundations

### 2. Objective
Establish professional open-source governance: branch protection, PR templates, issue templates, and semantic versioning foundation.

### 3. Background Theory
**Trunk-Based Development** (short-lived branches, frequent merges to main) is preferred by Google and Meta over GitFlow for fast-moving projects. **Semantic Versioning** (SemVer) communicates breaking changes to consumers. **Branch protection rules** enforce code review and CI passing before merge.

**Study:**
- Trunk-Based Development (trunkbaseddevelopment.com)
- Semantic Versioning 2.0.0
- GitHub Docs: "Managing a branch protection rule"

### 4. Learning Outcomes
- Open-source governance
- Branch protection and CI gates
- Semantic versioning and release management

### 5. Current Problems Being Solved
- Only `main` branch exists; no feature branches
- Zero PRs, zero issues — no collaboration evidence
- No `CONTRIBUTING.md`, `ISSUE_TEMPLATE`, `PULL_REQUEST_TEMPLATE`
- No release tags or versioning

### 6. Implementation Tasks
1. Create `CONTRIBUTING.md` with development setup, branch naming (`feat/`, `fix/`, `docs/`), and PR requirements
2. Create `.github/ISSUE_TEMPLATE/bug_report.md` and `feature_request.md`
3. Create `.github/PULL_REQUEST_TEMPLATE.md` with checklist
4. Add branch protection rules for `main` (require PR, require CI pass, require 1 review)
5. Create `CHANGELOG.md` following Keep a Changelog format
6. Tag current state as `v0.1.0-alpha.1`
7. Create `docs/branching.md` explaining the workflow

### 7. Files to Modify
- New: `CONTRIBUTING.md`
- New: `.github/ISSUE_TEMPLATE/bug_report.md`
- New: `.github/ISSUE_TEMPLATE/feature_request.md`
- New: `.github/PULL_REQUEST_TEMPLATE.md`
- New: `CHANGELOG.md`
- New: `docs/branching.md`
- GitHub Settings: Branch protection rules

### 8. Best Practices
- PR template should require: tests, docs update, CHANGELOG entry
- Issue templates should auto-label (`bug`, `enhancement`)
- Branch protection should require *up-to-date* CI, not just *passing* CI

### 9. Validation Checklist
- [ ] A test PR cannot be merged without CI passing (verify with a trivial PR)
- [ ] Issue templates render correctly when clicking "New Issue"
- [ ] `git tag -l` shows `v0.1.0-alpha.1`
- [ ] CHANGELOG has an `[Unreleased]` section

### 10. Expected Deliverables
- `CONTRIBUTING.md`
- Issue and PR templates
- Branch protection enabled
- Initial version tag

### 11. Suggested Commit Strategy
```
docs(contributing): add contribution guidelines and issue templates
chore(repo): add branch protection rules and PR template
chore(release): tag v0.1.0-alpha.1 and initialize CHANGELOG
```

### 12. Difficulty
3/10

### 13. Estimated Time
3–4 hours

---

## Phase 6: Secret Management & Environment Configuration

### 1. Phase Title
Zero-Trust Configuration & Secret Rotation

### 2. Objective
Eliminate all hardcoded secrets, implement environment-based configuration with validation, and establish secret rotation procedures.

### 3. Background Theory
**The 12-Factor App** mandates config in environment variables, not code. **Pydantic Settings** (v2) provides type-safe, validated environment configuration with `.env` file support. **Secret rotation** is a compliance requirement (SOC 2, ISO 27001); even "dev" secrets should be rotateable because developers copy them to production.

**Study:**
- 12-Factor App Config principle
- Pydantic Settings v2 documentation
- OWASP Cheat Sheet: Secrets Management

### 4. Learning Outcomes
- Type-safe configuration management
- Secret lifecycle management
- Environment validation patterns

### 5. Current Problems Being Solved
- `.env.example` exists but no validation of required variables
- No evidence of secret rotation procedures
- Configuration scattered across `config.py`, `.env`, and YAML files

### 6. Implementation Tasks
1. Audit all configuration sources: `core/config.py`, `.env.example`, `configs/**/*.yaml`
2. Consolidate to a single `Settings` class using Pydantic v2 `BaseSettings`
3. Define strict validation rules: required fields, type checking, regex for URLs
4. Add `Settings.model_validate()` on startup with clear error messages for missing vars
5. Ensure `.env.example` has no real-looking secrets (use `changeme`, `your-key-here`)
6. Add `python-dotenv` for local dev, but require real env vars in production
7. Document secret rotation procedure in `docs/security/secrets.md`

### 7. Files to Modify
- Rewrite: `apps/api-server/src/core/config.py`
- Update: `.env.example`
- New: `apps/api-server/src/core/settings.py` (Pydantic-based)
- New: `docs/security/secrets.md`

### 8. Best Practices
- Never commit `.env` files
- Use `SecretStr` type for sensitive values so they don't leak in logs
- Fail fast on startup if required secrets are missing
- Separate `DevelopmentSettings`, `StagingSettings`, `ProductionSettings` if behaviors differ

### 9. Validation Checklist
- [ ] App refuses to start if `JWT_SECRET` is missing, with clear error
- [ ] `Settings().jwt_secret` returns `SecretStr`, not plain string
- [ ] `print(Settings())` does not reveal secrets in logs
- [ ] `.env.example` contains only placeholder values

### 10. Expected Deliverables
- Pydantic-based `Settings` class
- Updated `.env.example`
- Secret management documentation

### 11. Suggested Commit Strategy
```
refactor(config): replace ad-hoc config with pydantic BaseSettings
chore(security): add SecretStr types and startup validation
docs(security): document secret management and rotation procedures
```

### 12. Difficulty
5/10

### 13. Estimated Time
4–6 hours

---

## Phase 7: Security Policy & Vulnerability Scanning

### 1. Phase Title
Security Governance & Automated Scanning

### 2. Objective
Add `SECURITY.md`, implement automated dependency and container scanning in CI, and establish a vulnerability disclosure process.

### 3. Background Theory
A **SECURITY.md** file is the standard way to communicate how researchers should report vulnerabilities. **Software Composition Analysis (SCA)** tools like Snyk, Dependabot, or Trivy scan dependencies for known CVEs. **Container scanning** checks OS packages in Docker images. **CVE** (Common Vulnerabilities and Exposures) scoring via CVSS helps prioritize fixes.

**Study:**
- GitHub Docs: "Adding a security policy"
- OWASP Dependency-Check
- Trivy documentation (Aqua Security)
- CVSS v3.1 specification

### 4. Learning Outcomes
- Security governance documentation
- Automated vulnerability scanning
- CVE triage and prioritization

### 5. Current Problems Being Solved
- No `SECURITY.md` present
- No dependency vulnerability scanning in CI
- No container image scanning
- No evidence of security-focused code review

### 6. Implementation Tasks
1. Create `SECURITY.md` with supported versions, reporting process, and disclosure timeline
2. Enable GitHub Dependabot alerts and auto-PRs for `pip` and `npm`
3. Add Trivy container scan to CI workflow
4. Add Bandit (Python security linter) to pre-commit hooks
5. Add `pip-audit` or `safety` to CI
6. Create `.github/dependabot.yml`
7. Document CVE triage process: how to evaluate severity and response time

### 7. Files to Modify
- New: `SECURITY.md`
- New: `.github/dependabot.yml`
- Modify: `.github/workflows/ci.yml`
- New: `.pre-commit-config.yaml` (with bandit)

### 8. Best Practices
- SECURITY.md should include an email or GitHub Security Advisory link
- Dependabot should group minor/patch updates to reduce PR noise
- Bandit should skip `assert` checks in test files (`skips: ["B101"]`)
- Container scans should fail CI on HIGH/CRITICAL CVEs

### 9. Validation Checklist
- [ ] GitHub shows "Security policy" tab with SECURITY.md content
- [ ] Dependabot has created at least one PR (or verified config)
- [ ] CI fails if Bandit finds `B105` (hardcoded password) or `B608` (SQL injection)
- [ ] Trivy scan runs on every PR and reports zero CRITICAL CVEs

### 10. Expected Deliverables
- `SECURITY.md`
- `.github/dependabot.yml`
- Updated CI with security scanning
- `.pre-commit-config.yaml`

### 11. Suggested Commit Strategy
```
docs(security): add SECURITY.md with disclosure policy
chore(ci): add dependabot, bandit, and trivy scanning
chore(precommit): add bandit and trailing-whitespace hooks
```

### 12. Difficulty
4/10

### 13. Estimated Time
3–4 hours

---

## Phase 8: Authentication Hardening

### 1. Phase Title
Production-Grade JWT & Auth0 Integration

### 2. Objective
Replace basic JWT implementation with Auth0 JWKS validation, add token refresh, and implement secure token storage.

### 3. Background Theory
**JWT** (JSON Web Token) security depends on proper signature verification. **JWKS** (JSON Web Key Set) allows key rotation without application changes. **Auth0** is an industry-standard identity provider. **Token refresh** patterns prevent long-lived access tokens. **HttpOnly cookies** prevent XSS token theft.

**Study:**
- Auth0 Docs: "Validate JSON Web Tokens"
- PyJWT documentation (with `jwt.PyJWKClient`)
- OWASP JWT Security Cheat Sheet
- RFC 7517 (JWK), RFC 7519 (JWT)

### 4. Learning Outcomes
- Asymmetric JWT verification (RS256)
- JWKS endpoint consumption
- Token lifecycle management
- Secure cookie handling

### 5. Current Problems Being Solved
- README mentions "Auth0-compatible configuration" but no evidence of JWKS validation
- JWT tokens may be using symmetric secrets (HS256) which are harder to rotate
- No token refresh mechanism
- Approval tokens scoped to incidents but no expiry mentioned

### 6. Implementation Tasks
1. Verify current JWT implementation: symmetric or asymmetric?
2. If symmetric, migrate to RS256 with JWKS endpoint
3. Implement `PyJWKClient` to fetch and cache public keys from Auth0/.well-known/jwks.json
4. Add token expiry validation (exp, nbf, iat claims)
5. Add refresh token endpoint (`POST /auth/refresh`)
6. Store approval tokens in database with TTL, not just JWT signature
7. Add token revocation endpoint (for logout/incident cancellation)

### 7. Files to Modify
- `apps/api-server/src/api/middleware/auth.py`
- `apps/api-server/src/core/config.py` (add JWKS_URL)
- `apps/api-server/src/db/models.py` (add TokenBlacklist or ApprovalToken table)
- `apps/api-server/src/api/routes/auth.py` (new or existing)

### 8. Best Practices
- Always verify `aud` (audience) and `iss` (issuer) claims
- Cache JWKS for 5–15 minutes to avoid hammering the IdP
- Use `Secure`, `HttpOnly`, `SameSite=Strict` cookies for web dashboard
- Approval tokens should be single-use and short-lived (<15 minutes)

### 9. Validation Checklist
- [ ] Token signed with RS256 validates against JWKS
- [ ] Token with wrong `aud` claim is rejected
- [ ] Expired token returns 401, not 500
- [ ] Revoked token is rejected even if cryptographically valid
- [ ] Approval token table has `expires_at` and `used_at` columns

### 10. Expected Deliverables
- RS256 JWT implementation
- JWKS client with caching
- Token refresh endpoint
- Approval token persistence layer

### 11. Suggested Commit Strategy
```
feat(auth): migrate JWT to RS256 with JWKS validation
feat(auth): add token refresh and revocation endpoints
feat(approvals): persist approval tokens with TTL in database
```

### 12. Difficulty
7/10

### 13. Estimated Time
8–12 hours

---

## Phase 9: Authorization & RBAC Enforcement

### 1. Phase Title
Role-Based Access Control & Permission Enforcement

### 2. Objective
Move beyond "viewer/operator/admin" strings to enforced, granular permissions with middleware-level protection.

### 3. Background Theory
**RBAC** (Role-Based Access Control) assigns permissions to roles, roles to users. **ABAC** (Attribute-Based Access Control) adds context (time, location, incident severity). **Policy Enforcement Points (PEP)** intercept requests; **Policy Decision Points (PDP)** evaluate rules. For this project, RBAC is sufficient, but the architecture should allow ABAC later.

**Study:**
- NIST RBAC standard (ANSI INCITS 359-2004)
- Casbin documentation (if choosing a library) or custom middleware
- OWASP Access Control Cheat Sheet

### 4. Learning Outcomes
- RBAC model design
- Middleware-based authorization
- Permission granularity
- Separation of authentication and authorization

### 5. Current Problems Being Solved
- RBAC roles mentioned (`viewer`, `operator`, `admin`) but no evidence of enforcement
- No granular permissions (e.g., can an operator approve CRITICAL risk?)
- No resource-level access control (can user A see incident B?)

### 6. Implementation Tasks
1. Define permission matrix: `incident:read`, `incident:write`, `approval:approve`, `approval:reject`, `execution:trigger`, `config:read`, etc.
2. Map permissions to roles in `docs/security/rbac.md`
3. Implement `requires_permission(permission: str)` decorator
4. Add `user_roles` and `role_permissions` tables to database
5. Seed default roles in migration
6. Apply decorators to all API routes
7. Add middleware that rejects requests before hitting route handlers

### 7. Files to Modify
- `apps/api-server/src/db/models.py` (add Role, Permission, UserRole tables)
- New: `apps/api-server/src/api/middleware/rbac.py`
- `apps/api-server/src/api/routes/*.py` (add decorators)
- New: `docs/security/rbac.md`

### 8. Best Practices
- Deny by default (fail-closed)
- Log all authorization denials for security monitoring
- Keep permission strings in constants, not magic strings
- Separate "who you are" (auth) from "what you can do" (authz)

### 9. Validation Checklist
- [ ] `viewer` role cannot POST to `/approvals/{id}`
- [ ] `operator` role cannot access `/evaluations/summary` if not permitted
- [ ] Admin can assign roles via API
- [ ] All API routes have at least one permission check
- [ ] 403 responses are returned for unauthorized access, not 500

### 10. Expected Deliverables
- RBAC middleware
- Database migration for roles/permissions
- Permission matrix documentation
- Decorated API routes

### 11. Suggested Commit Strategy
```
feat(authz): implement RBAC middleware and permission decorators
feat(db): add roles, permissions, and user_roles tables
chore(api): apply RBAC decorators to all protected routes
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–8 hours

---

## Phase 10: Input Validation & Output Sanitization

### 1. Phase Title
Schema-First API Validation & Safe Serialization

### 2. Objective
Eliminate mass assignment risks, prevent injection attacks, and ensure all API inputs are validated before reaching business logic.

### 3. Background Theory
**Pydantic** provides runtime type validation for Python. **FastAPI** integrates Pydantic natively for request/response models. **Mass assignment** occurs when user input is unpacked directly into model constructors (e.g., `Alert(**request.json)`). **Output sanitization** prevents information disclosure (stack traces, secret values) in error responses.

**Study:**
- FastAPI docs: "Request Body" and "Response Model"
- Pydantic v2 validation concepts
- OWASP Input Validation Cheat Sheet
- CWE-20 (Improper Input Validation)

### 4. Learning Outcomes
- Schema-driven API design
- Runtime type safety
- Mass assignment prevention
- Error response standardization

### 5. Current Problems Being Solved
- No input validation on `/incidents/webhook` (alert storm risk)
- No schema for request bodies
- Error responses may leak internal details
- Tool allowlist in YAML could be YAML-injected if file is writable

### 6. Implementation Tasks
1. Create Pydantic request/response schemas for all API routes
2. Add `WebhookPayload` schema with strict field validation for `/incidents/webhook`
3. Add rate limiting to webhook endpoint (Flask-Limiter or slowapi)
4. Sanitize all error responses: never return stack traces or internal paths
5. Validate tool allowlist YAML on startup (schema check)
6. Add `max_length`, `regex`, and `Field(..., ge=0, le=100)` constraints
7. Implement custom validators for complex fields (e.g., incident severity must be in enum)

### 7. Files to Modify
- New: `apps/api-server/src/api/schemas/` (request/response models)
- `apps/api-server/src/api/routes/incidents.py`
- `apps/api-server/src/api/routes/approvals.py`
- `apps/api-server/src/api/routes/evaluations.py`
- `apps/api-server/src/api/middleware/error_handler.py`
- `apps/api-server/src/tools/execution_guard.py` (validate allowlist)

### 8. Best Practices
- Use `response_model` in FastAPI to control output shape
- Return 422 for validation errors with detailed field-level messages
- Never trust client input; validate at the edge
- Use `Extra.forbid` in Pydantic models to prevent unknown fields

### 9. Validation Checklist
- [ ] Sending `{"severity": "invalid"}` to webhook returns 422, not 500
- [ ] Sending 10,000 webhook requests in 1 second triggers rate limit (429)
- [ ] Error response for 500 contains only `{"error": "Internal server error"}` with trace ID
- [ ] All API routes have explicit request/response schemas

### 10. Expected Deliverables
- Pydantic schemas for all endpoints
- Rate limiting on webhook
- Standardized error response format
- Tool allowlist validation

### 11. Suggested Commit Strategy
```
feat(api): add pydantic request/response schemas for all routes
feat(security): implement rate limiting on incident webhook
refactor(errors): standardize error responses and remove stack trace leakage
```

### 12. Difficulty
5/10

### 13. Estimated Time
6–8 hours

---

## Phase 11: Durable Checkpointing

### 1. Phase Title
LangGraph PostgreSQL Checkpointing

### 2. Objective
Replace in-memory `MemorySaver` with `langgraph-checkpoint-postgres` to enable cross-process interrupt/resume and horizontal scaling.

### 3. Background Theory
**Checkpointing** in workflow engines persists state at each node transition, enabling failure recovery and human-in-the-loop interruptions. **MemorySaver** stores state in RAM — fast but volatile. **PostgreSQL checkpointing** provides ACID durability, cross-process visibility, and horizontal scaling. This is critical for Celery workers which run in separate processes.

**Study:**
- LangGraph docs: "Persistence"
- `langgraph-checkpoint-postgres` README
- ACID properties (Atomicity, Consistency, Isolation, Durability)
- Workflow engine durability patterns (Temporal, Cadence)

### 4. Learning Outcomes
- Distributed state persistence
- LangGraph checkpoint internals
- Database transaction management for state machines

### 5. Current Problems Being Solved
- MemorySaver in distributed Celery workers = state loss on restart
- Cross-process interrupt/resume impossible
- README explicitly states: *"langgraph-checkpoint-postgres is not installed by default"*

### 6. Implementation Tasks
1. Add `langgraph-checkpoint-postgres` to dependencies
2. Create `PostgresSaver` instance with connection pool
3. Replace `MemorySaver` in `orchestration/graph.py`
4. Add migration for LangGraph checkpoint tables (if not auto-created)
5. Test interrupt/resume across two different Celery worker processes
6. Add health check for checkpoint DB connectivity
7. Document checkpoint schema and cleanup policies

### 7. Files to Modify
- `apps/api-server/pyproject.toml` (add dependency)
- `apps/api-server/src/orchestration/graph.py`
- `apps/api-server/src/db/session.py` (connection pool config)
- New: `apps/api-server/src/orchestration/checkpoint.py`
- `infrastructure/docker/postgres/init.sql` (add checkpoint tables if needed)

### 8. Best Practices
- Use connection pooling (pgbouncer or SQLAlchemy pool) for checkpoint DB
- Set checkpoint retention policy (e.g., 30 days) to prevent unbounded growth
- Encrypt sensitive checkpoint data at rest if needed
- Test worker crash scenarios: kill -9 a worker mid-graph and verify resume

### 9. Validation Checklist
- [ ] Graph state persists after `docker compose restart celery-worker`
- [ ] Interrupted incident can be resumed via API after worker restart
- [ ] Two parallel workers processing different incidents don't corrupt each other's state
- [ ] Checkpoint table size is bounded by retention policy

### 10. Expected Deliverables
- PostgreSQL-backed checkpointing
- Cross-process interrupt/resume test
- Checkpoint health check

### 11. Suggested Commit Strategy
```
feat(checkpoint): install langgraph-checkpoint-postgres
refactor(orchestration): replace MemorySaver with PostgresSaver
feat(health): add checkpoint database connectivity check
```

### 12. Difficulty
7/10

### 13. Estimated Time
6–10 hours

---

## Phase 12: Celery Async Boundary Refactoring

### 1. Phase Title
Safe Async/Celery Integration

### 2. Objective
Eliminate `asyncio.run()` inside Celery tasks and implement a safe execution model for async code in synchronous workers.

### 3. Background Theory
Celery workers are synchronous by default. **Event loops** cannot be nested (`asyncio.run()` inside `asyncio.run()` raises `RuntimeError`). The correct patterns are: (1) use `celery[gevent]` or `celery[eventlet]` pools, (2) use `asyncio.new_event_loop()` with manual cleanup, or (3) refactor to synchronous code. For LangGraph (which is async-native), option 1 or a dedicated async worker pool is best.

**Study:**
- Celery docs: "Using Celery with asyncio"
- Gevent vs. Eventlet vs. Prefork pool comparison
- Python `asyncio` event loop policies

### 4. Learning Outcomes
- Async/sync boundary management
- Celery worker pool configuration
- Event loop lifecycle management
- Deadlock prevention in distributed tasks

### 5. Current Problems Being Solved
- README admits: *"Celery async boundary instability — Replace asyncio.run() task boundary with safer execution model"*
- `asyncio.run()` inside Celery tasks causes deadlocks and resource leaks
- Memory leaks from unclosed event loops

### 6. Implementation Tasks
1. Audit all Celery tasks for `asyncio.run()` usage
2. Choose strategy: (a) gevent pool, (b) dedicated async worker, or (c) sync wrappers
3. For LangGraph integration, implement a custom Celery task base class that manages event loops
4. Add `celery[gevent]` to dependencies if choosing gevent
5. Update `docker-compose.yml` to use gevent pool (`-P gevent`)
6. Add tests that verify 100 concurrent tasks don't deadlock
7. Add memory profiling to detect event loop leaks

### 7. Files to Modify
- `apps/api-server/src/workers/celery_app.py`
- `apps/api-server/src/workers/tasks.py` (or wherever tasks are defined)
- `apps/api-server/pyproject.toml`
- `docker-compose.yml` (worker command)
- `apps/api-server/tests/orchestration/` (concurrency tests)

### 8. Best Practices
- Never call `asyncio.run()` inside a running event loop
- Use `asyncio.get_event_loop()` + `loop.run_until_complete()` if you must bridge
- Prefer `gevent` pool for I/O-bound async tasks; `prefork` for CPU-bound
- Monitor worker memory; event loop leaks show as monotonic growth

### 9. Validation Checklist
- [ ] 100 concurrent incident tasks complete without deadlock
- [ ] Worker memory usage is stable over 1 hour of sustained load
- [ ] No `RuntimeError: asyncio.run() cannot be called from a running event loop` in logs
- [ ] Task retry after failure works correctly

### 10. Expected Deliverables
- Refactored Celery tasks without `asyncio.run()`
- Updated worker pool configuration
- Concurrency stress tests
- Memory stability verification

### 11. Suggested Commit Strategy
```
refactor(workers): replace asyncio.run() with gevent pool for async tasks
feat(workers): add custom async task base class with safe event loop management
test(stress): add 100-concurrent-task deadlock prevention test
```

### 12. Difficulty
8/10

### 13. Estimated Time
8–12 hours

---

## Phase 13: LLM Provider Resilience & Fallback Chain

### 1. Phase Title
Production-Grade Provider Resilience

### 2. Objective
Fix the critical 429 blocker by implementing a deterministic fallback classifier and ensuring the pipeline never halts on provider failure.

### 3. Background Theory
**Circuit Breakers** (per the Circuit Breaker pattern by Michael Nygard) prevent cascading failures by failing fast when a dependency is unhealthy. **Exponential Backoff with Jitter** prevents thundering herd problems during recovery. **Graceful Degradation** reduces functionality rather than failing entirely. A **deterministic fallback** (rule-based classifier) provides baseline capability when all LLM providers fail.

**Study:**
- "Release It!" by Michael Nygard (Circuit Breaker chapter)
- AWS Architecture Blog: "Exponential Backoff and Jitter"
- OpenAI API error handling best practices

### 4. Learning Outcomes
- Circuit breaker implementation
- Retry strategies and jitter
- Graceful degradation patterns
- Rule-based classification as fallback

### 5. Current Problems Being Solved
- *"The live incident lifecycle is blocked on a single critical dependency: the router classification step fails when the live LLM provider returns 429"*
- Layer 4 fallback exists but may produce useless output without human escalation
- No evidence of circuit breaker health checks

### 6. Implementation Tasks
1. Implement circuit breaker for each LLM provider layer (primary, secondary, Ollama)
2. Add health check endpoint for each provider (`/health/providers`)
3. Implement deterministic fallback classifier with keyword + regex + topology matching
4. Add escalation trigger when Layer 4 fallback activates (Slack/PagerDuty notification)
5. Add retry with exponential backoff + jitter for 429 errors
6. Cache successful classifications for 5 minutes to reduce provider load
7. Add metrics: `provider_failures_total`, `fallback_activations_total`, `classification_latency_seconds`

### 7. Files to Modify
- `apps/api-server/src/core/resilience/provider_chain.py`
- `apps/api-server/src/core/resilience/circuit_breaker.py`
- `apps/api-server/src/core/llm_client.py`
- `apps/api-server/src/agents/router_agent/agent.py`
- `apps/api-server/src/api/routes/health.py`
- `apps/api-server/src/observability/metrics.py`

### 8. Best Practices
- Circuit breaker should have three states: CLOSED, OPEN, HALF-OPEN
- Log every fallback activation with incident ID and reason
- Never cache fallback classifications (they're low-confidence)
- Fallback classifier should be unit-testable without LLM calls

### 9. Validation Checklist
- [ ] Disconnect primary LLM; system falls back to secondary within 5 seconds
- [ ] Disconnect all LLMs; deterministic classifier activates and notifies on-call
- [ ] Reconnect primary LLM; circuit breaker transitions to HALF-OPEN, then CLOSED
- [ ] 429 errors trigger retry with jitter, not immediate failure
- [ ] Metrics endpoint shows provider health status

### 10. Expected Deliverables
- Circuit breaker implementation
- Deterministic fallback classifier
- Provider health check endpoint
- Retry with jitter
- Prometheus metrics for provider resilience

### 11. Suggested Commit Strategy
```
feat(resilience): implement circuit breaker for LLM providers
feat(router): add deterministic fallback classifier with topology matching
feat(observability): add provider failure and fallback activation metrics
```

### 12. Difficulty
8/10

### 13. Estimated Time
10–14 hours

---

## Phase 14: Bootstrap State Persistence

### 1. Phase Title
Pre-LLM State Durability

### 2. Objective
Persist the graph bootstrap envelope (thread_id, execution_id, status, operating_mode) before any provider interaction, ensuring no incident is lost to provider failures.

### 3. Background Theory
**Write-ahead logging** in databases ensures state is durable before processing begins. Similarly, workflow engines should persist the *intent* to process before invoking expensive or unreliable operations. This is the **Saga pattern** at micro-scale: record the saga, then execute steps.

**Study:**
- Saga pattern (microservices patterns)
- Write-Ahead Logging (WAL) in PostgreSQL
- Idempotency keys in API design

### 4. Learning Outcomes
- Saga pattern implementation
- Idempotency in distributed systems
- Pre-processing state durability

### 5. Current Problems Being Solved
- *"No agent executions persisted for live incidents"*
- *"Persist bootstrap checkpoint before first LLM call"* (from roadmap)
- Incidents lost if 429 occurs before first checkpoint

### 6. Implementation Tasks
1. Modify incident ingestion to create `Incident` row + `Execution` row before enqueuing Celery task
2. Add `bootstrap_checkpoint` column to `Execution` table (JSONB)
3. Update `POST /incidents/webhook` to return 202 Accepted with execution_id immediately
4. Ensure Celery task uses the pre-persisted execution_id (idempotency)
5. Add retry logic for bootstrap persistence (database might be temporarily unavailable)
6. Add test: simulate DB failure during ingestion, verify incident is not lost

### 7. Files to Modify
- `apps/api-server/src/api/routes/incidents.py`
- `apps/api-server/src/db/models.py` (add Execution.bootstrap_checkpoint)
- `apps/api-server/src/workers/tasks.py`
- `apps/api-server/src/orchestration/graph.py`

### 8. Best Practices
- Return 202 Accepted, not 200 OK, for async operations
- Use idempotency keys to prevent duplicate processing
- Bootstrap state should include: incident_id, thread_id, timestamp, operating_mode, input_hash
- Never process an incident without a durable record

### 9. Validation Checklist
- [ ] Webhook returns 202 with execution_id within 100ms
- [ ] Database row exists before Celery task starts
- [ ] Killing the API server immediately after webhook still leaves recoverable state
- [ ] Duplicate webhook with same idempotency key returns same execution_id, no duplicate processing

### 10. Expected Deliverables
- Bootstrap persistence in incident flow
- Idempotency key handling
- 202 Accepted response pattern
- Recovery test for mid-ingestion crashes

### 11. Suggested Commit Strategy
```
feat(ingestion): persist bootstrap state before LLM invocation
feat(api): return 202 Accepted with execution_id for incident webhooks
feat(idempotency): add idempotency key handling to prevent duplicate incidents
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–8 hours

---

## Phase 15: State Management & Distributed State

### 1. Phase Title
Redis-Backed State & Distributed Locks

### 2. Objective
Implement Redis-backed shared state for operating modes, provider health, and distributed locks to prevent race conditions in multi-worker deployments.

### 3. Background Theory
**Redis** is an in-memory data structure store used for caching, session storage, and distributed locking. **Redlock** algorithm provides distributed mutual exclusion. **Operating modes** (FULL, DEGRADED, SAFE_MODE) must be visible to all workers simultaneously. **Consistent hashing** can shard state if Redis is clustered.

**Study:**
- Redis documentation (Data types, Persistence, Clustering)
- Redlock algorithm (Redis official docs)
- Distributed systems consensus (Raft, Paxos — conceptual understanding)

### 4. Learning Outcomes
- Redis data modeling
- Distributed locking
- Shared state consistency
- Cache invalidation strategies

### 5. Current Problems Being Solved
- Operating modes transition automatically but may not be visible across workers
- No distributed locking for critical sections (e.g., approval token consumption)
- Redis used only for Celery broker, not for application state

### 6. Implementation Tasks
1. Implement `RedisStateManager` class with get/set/delete for operating modes
2. Add distributed lock using `redis.lock.Lock` (Redlock simplified)
3. Use locks for: approval token consumption, operating mode transitions, checkpoint cleanup
4. Add TTL to all transient state (operating modes, health status)
5. Implement pub/sub for operating mode changes (workers subscribe to mode changes)
6. Add Redis connection pooling and health checks
7. Document Redis key naming convention (`sentinelops:state:{key}`)

### 7. Files to Modify
- `apps/api-server/src/core/resilience/operating_mode.py`
- New: `apps/api-server/src/memory/redis_state.py`
- `apps/api-server/src/tools/execution_guard.py` (use distributed lock)
- `apps/api-server/src/api/routes/health.py`

### 8. Best Practices
- Always use `nx=True` (set if not exists) for locks to prevent overwriting
- Lock TTL should be > max expected processing time (e.g., 30 seconds)
- Use Lua scripts for atomic operations when possible
- Handle Redis failover (sentinel or cluster mode) if production requires

### 9. Validation Checklist
- [ ] Two workers see the same operating mode within 1 second of change
- [ ] Simultaneous approval attempts are serialized by distributed lock
- [ ] Redis lock automatically expires if worker crashes (TTL)
- [ ] Redis connection pool doesn't exhaust under load (test with 1000 concurrent ops)

### 10. Expected Deliverables
- Redis state manager
- Distributed lock implementation
- Operating mode pub/sub
- Redis health check

### 11. Suggested Commit Strategy
```
feat(state): implement Redis-backed shared state manager
feat(locks): add distributed locking for approval and mode transitions
feat(resilience): add pub/sub for operating mode synchronization
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–8 hours

---

## Phase 16: Test Consolidation & Category Cleanup

### 1. Phase Title
Test Pyramid Rationalization

### 2. Objective
Consolidate 14 test categories into a coherent 4-layer test pyramid and eliminate redundant or mock-only test suites.

### 3. Background Theory
The **Test Pyramid** (Mike Cohn) has three layers: Unit (fast, isolated, many), Integration (slower, real dependencies, fewer), E2E (slowest, full system, fewest). **Test categories** should map to these layers, not to implementation modules. Having 14 categories suggests tests are organized by *what they test* (agents, causality, evaluation) rather than *how they test* (unit, integration, e2e).

**Study:**
- "Succeeding with Agile" by Mike Cohn (Test Pyramid chapter)
- "Unit Testing Principles, Practices, and Patterns" by Vladimir Khorikov
- Google Testing Blog: "Just Say No to More End-to-End Tests"

### 4. Learning Outcomes
- Test pyramid design
- Test organization strategies
- Cost/benefit analysis of test types
- Mock vs. real dependency tradeoffs

### 5. Current Problems Being Solved
- 14 test categories with inconsistent counts (2139 vs 1474 tests)
- Mock-heavy evaluation tests verify harness, not system
- No clear separation between unit, integration, and e2e
- Maintenance burden of 14 categories

### 6. Implementation Tasks
1. Define 4 categories: `unit/`, `integration/`, `e2e/`, `evaluation/`
2. Move existing tests into these categories based on what they verify
3. Delete or merge redundant test files
4. Update `pytest.ini` with markers: `@pytest.mark.unit`, `@pytest.mark.integration`, etc.
5. Update CI to run unit tests on every PR, integration nightly, e2e weekly
6. Document test strategy in `docs/testing/strategy.md`
7. Ensure evaluation tests use real code paths but mocked infrastructure (not mocked harness)

### 7. Files to Modify
- Restructure: `apps/api-server/tests/` → `unit/`, `integration/`, `e2e/`, `evaluation/`
- `apps/api-server/pyproject.toml` or `pytest.ini`
- `.github/workflows/ci.yml`
- New: `.github/workflows/integration.yml`
- New: `.github/workflows/e2e.yml`
- New: `docs/testing/strategy.md`

### 8. Best Practices
- Unit tests should run in <10 seconds
- Integration tests should use testcontainers for PostgreSQL, Redis, Qdrant
- E2E tests should run against the full Docker Compose stack
- Evaluation tests should measure system behavior, not harness correctness

### 9. Validation Checklist
- [ ] `pytest -m unit` completes in <30 seconds
- [ ] `pytest -m integration` uses real PostgreSQL and Redis (testcontainers)
- [ ] `pytest -m e2e` runs against `docker-compose.yml` stack
- [ ] No test file imports from `tests/` (tests shouldn't import each other)
- [ ] Coverage report generated for all categories

### 10. Expected Deliverables
- 4-category test structure
- Updated CI workflows
- Test strategy documentation
- Coverage reporting

### 11. Suggested Commit Strategy
```
refactor(tests): consolidate 14 categories into 4-layer test pyramid
chore(ci): add separate workflows for unit, integration, and e2e tests
docs(testing): document test strategy and running instructions
```

### 12. Difficulty
5/10

### 13. Estimated Time
6–8 hours

---

## Phase 17: Unit Test Foundation & Mock Quality

### 1. Phase Title
High-Fidelity Unit Testing

### 2. Objective
Write unit tests for all agent base classes, utility functions, and pure logic modules with high-quality mocks that verify behavior, not implementation.

### 3. Background Theory
**Mocking** isolates the unit under test. **Behavioral verification** checks that outputs are correct; **interaction verification** checks that collaborators were called correctly. **Over-mocking** (mocking internal implementation details) creates brittle tests that break on refactoring. **Dependency injection** makes mocking natural by allowing test doubles to be injected.

**Study:**
- "Growing Object-Oriented Software, Guided by Tests" by Freeman & Pryce
- Python `unittest.mock` documentation (autospec, spec_set)
- Test Double patterns (Mock, Stub, Fake, Spy)

### 4. Learning Outcomes
- Mock quality assessment
- Dependency injection for testability
- Behavioral vs. interaction testing
- Test-driven development (TDD) workflow

### 5. Current Problems Being Solved
- No evidence of comprehensive unit tests for base agents
- Mock-heavy evaluation tests verify harness, not system
- Services may be tightly coupled, making unit testing impossible without refactoring

### 6. Implementation Tasks
1. Add unit tests for `BaseAgent` (from Phase 4): verify lifecycle hooks, error handling
2. Add unit tests for `UncertaintyEngine`: verify confidence calculations with known inputs
3. Add unit tests for `CausalValidator`: verify temporal consistency checks
4. Add unit tests for `ExecutionGuard`: verify allowlist enforcement, token validation
5. Use `pytest-mock` and `unittest.mock` with `autospec=True`
6. Add `pytest-cov` and enforce 80% unit test coverage
7. Refactor any untestable code to use dependency injection

### 7. Files to Modify
- New: `apps/api-server/tests/unit/agents/test_base_agent.py`
- New: `apps/api-server/tests/unit/causality/test_uncertainty_engine.py`
- New: `apps/api-server/tests/unit/causality/test_causal_validator.py`
- New: `apps/api-server/tests/unit/tools/test_execution_guard.py`
- `apps/api-server/pyproject.toml` (add pytest-cov)
- `.github/workflows/ci.yml` (add coverage check)

### 8. Best Practices
- Never mock what you don't own (external APIs should be abstracted)
- Use Fakes (in-memory implementations) for repositories, not Mocks
- One assertion per test (or one logical concept)
- Test edge cases: empty input, maximum values, boundary conditions

### 9. Validation Checklist
- [ ] `pytest --cov=apps/api-server/src --cov-report=term-missing` shows >80% for unit tests
- [ ] All unit tests run in <30 seconds
- [ ] No test uses `mock.patch` on internal private methods
- [ ] Tests pass without network access (airplane mode test)

### 10. Expected Deliverables
- Unit tests for core components
- 80% coverage enforcement
- Coverage reporting in CI

### 11. Suggested Commit Strategy
```
test(unit): add BaseAgent lifecycle and error handling tests
test(unit): add UncertaintyEngine confidence calculation tests
test(unit): add ExecutionGuard allowlist and token validation tests
chore(ci): enforce 80% unit test coverage
```

### 12. Difficulty
5/10

### 13. Estimated Time
8–12 hours

---

## Phase 18: Integration Test Suite (Real Infrastructure)

### 1. Phase Title
Testcontainers & Real Dependency Testing

### 2. Objective
Build integration tests that verify the system against real PostgreSQL, Redis, and Qdrant instances using Testcontainers.

### 3. Background Theory
**Testcontainers** (Python library) spins up real Docker containers for dependencies during tests. This provides **fidelity** (testing against real PostgreSQL, not SQLite) without requiring a persistent test environment. **Integration tests** verify that modules work together correctly, catching issues like SQL dialect differences, connection pool exhaustion, and serialization mismatches.

**Study:**
- Testcontainers Python documentation
- "Integration Testing with Docker" by Pini Reznik
- SQLAlchemy testing patterns with real databases

### 4. Learning Outcomes
- Testcontainers usage
- Docker-in-Docker for CI
- Database migration testing
- Integration test isolation

### 5. Current Problems Being Solved
- Evaluation tests use mocked infrastructure, not real integrations
- No evidence of database migration tests
- SQLite vs. PostgreSQL behavioral differences not caught

### 6. Implementation Tasks
1. Add `testcontainers[postgres,redis]` to dev dependencies
2. Create `PostgreSQLTestContainer` fixture for pytest
3. Create `RedisTestContainer` fixture
4. Write integration tests for: incident ingestion → DB write → Celery enqueue → graph execution
5. Write integration tests for: approval flow (create → request → approve → execute)
6. Write integration tests for: Qdrant vector search with real embeddings
7. Add migration test: apply all migrations to empty DB, verify schema
8. Run integration tests in CI using Docker-in-Docker

### 7. Files to Modify
- `apps/api-server/pyproject.toml` (add testcontainers)
- New: `apps/api-server/tests/integration/conftest.py`
- New: `apps/api-server/tests/integration/test_incident_lifecycle.py`
- New: `apps/api-server/tests/integration/test_approval_flow.py`
- New: `apps/api-server/tests/integration/test_retrieval.py`
- `.github/workflows/integration.yml`

### 8. Best Practices
- Each test gets a fresh database (use transactions or container restart)
- Clean up containers in `pytest_sessionfinish` or use context managers
- Don't test external APIs (VirusTotal, OpenAI) in integration tests; use WireMock or similar
- Integration tests should be idempotent and parallelizable

### 9. Validation Checklist
- [ ] Integration tests run against real PostgreSQL 15
- [ ] Integration tests run against real Redis 7
- [ ] Integration tests run against real Qdrant
- [ ] CI integration workflow passes
- [ ] Tests clean up containers even on failure

### 10. Expected Deliverables
- Testcontainers fixtures
- Integration tests for core flows
- CI workflow for integration tests
- Migration validation test

### 11. Suggested Commit Strategy
```
test(integration): add testcontainers fixtures for postgres and redis
test(integration): add incident lifecycle integration test
test(integration): add approval flow end-to-end integration test
chore(ci): add integration test workflow with docker-in-docker
```

### 12. Difficulty
7/10

### 13. Estimated Time
10–14 hours

---

## Phase 19: E2E Test Pipeline

### 1. Phase Title
Full-Stack End-to-End Validation

### 2. Objective
Create E2E tests that spin up the entire Docker Compose stack and verify complete incident processing through the API and dashboard.

### 3. Background Theory
**E2E tests** verify the system from the user's perspective. They are slow and expensive but catch integration issues that unit and integration tests miss (e.g., Nginx misconfiguration, CORS issues, frontend-backend contract mismatches). **Page Object Model** (POM) is a pattern for organizing UI test code. **API-driven E2E** tests can be faster than UI-driven tests while still covering full-stack behavior.

**Study:**
- Cypress or Playwright documentation (for frontend E2E)
- Postman/Newman for API E2E
- "Testing Microservices" by Toby Clemson

### 4. Learning Outcomes
- E2E test architecture
- Docker Compose orchestration in tests
- Frontend automation (if applicable)
- Contract testing between frontend and backend

### 5. Current Problems Being Solved
- No E2E tests exist
- Live lifecycle has never been proven end-to-end
- Frontend-backend integration untested

### 6. Implementation Tasks
1. Create `docker-compose.e2e.yml` extending base compose with test overrides
2. Write API E2E tests using `httpx` or `requests`: full incident lifecycle
3. Add frontend E2E using Playwright: create incident → view in dashboard → approve
4. Add E2E for evaluation path: trigger evaluation → verify results in API
5. Add E2E for chaos scenario: inject alert storm → verify rate limiting
6. Run E2E tests in CI on schedule (nightly) and on release PRs
7. Add test data seeding script for E2E environment

### 7. Files to Modify
- New: `docker-compose.e2e.yml`
- New: `apps/api-server/tests/e2e/test_full_lifecycle.py`
- New: `apps/web-dashboard/e2e/` (Playwright tests)
- New: `scripts/seed_e2e.py`
- `.github/workflows/e2e.yml`

### 8. Best Practices
- E2E tests should be deterministic (seeded data, fixed timestamps)
- Use `docker compose -f docker-compose.e2e.yml up --wait` to ensure readiness
- Screenshots on failure for frontend tests
- API E2E tests should verify response contracts (Pydantic schema compliance)

### 9. Validation Checklist
- [ ] `docker compose -f docker-compose.e2e.yml up` starts all services
- [ ] E2E test creates incident, waits for classification, verifies state in DB
- [ ] Frontend E2E logs in, creates incident, sees it in dashboard
- [ ] E2E tests run in CI nightly and pass consistently
- [ ] E2E tests clean up Docker volumes after run

### 10. Expected Deliverables
- `docker-compose.e2e.yml`
- API E2E test suite
- Frontend E2E test suite (if dashboard exists)
- E2E CI workflow
- E2E data seeding script

### 11. Suggested Commit Strategy
```
test(e2e): add docker-compose.e2e.yml and full lifecycle API test
test(e2e): add Playwright frontend tests for incident dashboard
chore(ci): add nightly e2e test workflow
```

### 12. Difficulty
8/10

### 13. Estimated Time
12–16 hours

---

## Phase 20: Test Coverage Enforcement

### 1. Phase Title
Coverage Gates & Quality Metrics

### 2. Objective
Implement automated coverage reporting, diff coverage checks, and quality gates in CI.

### 3. Background Theory
**Code coverage** measures which lines were executed during tests. **Diff coverage** measures coverage of changed lines in a PR — more actionable than overall coverage. **Coverage gates** fail CI if coverage drops below a threshold or if diff coverage is insufficient. **SonarQube** or **Codecov** provide dashboards and PR annotations.

**Study:**
- Codecov documentation
- SonarQube quality gates
- "Code Coverage is a Useless Metric" (understand limitations)
- Mutation testing (optional advanced topic)

### 4. Learning Outcomes
- Coverage metric interpretation
- CI quality gates
- Coverage diff analysis
- Test quality assessment beyond coverage

### 5. Current Problems Being Solved
- No evidence of coverage reporting
- Inconsistent test counts suggest gaps
- No enforcement of test quality

### 6. Implementation Tasks
1. Add `pytest-cov` and configure `.coveragerc`
2. Set coverage targets: unit 80%, integration 60%, overall 70%
3. Integrate Codecov or SonarCloud for PR diff coverage
4. Add coverage badge to README
5. Configure CI to fail if diff coverage < 70%
6. Add exclusion rules for auto-generated code, `__init__.py`, etc.
7. Generate HTML coverage reports locally

### 7. Files to Modify
- `apps/api-server/pyproject.toml` (add pytest-cov)
- New: `apps/api-server/.coveragerc`
- `.github/workflows/ci.yml`
- `README.md` (add badge)

### 8. Best Practices
- Coverage is necessary but not sufficient; 100% coverage with bad asserts is useless
- Focus on diff coverage, not absolute coverage
- Exclude trivial code (dataclasses, constants) from coverage
- Use branch coverage, not just line coverage (`--cov-branch`)

### 9. Validation Checklist
- [ ] CI fails if PR reduces overall coverage by >2%
- [ ] CI fails if diff coverage < 70%
- [ ] Coverage badge in README reflects main branch
- [ ] HTML report shows uncovered lines for local debugging

### 10. Expected Deliverables
- Coverage configuration
- Codecov/SonarCloud integration
- Coverage badge
- CI coverage gates

### 11. Suggested Commit Strategy
```
chore(tests): add pytest-cov and coverage configuration
chore(ci): add coverage gates and diff coverage checks
docs(readme): add code coverage badge
```

### 12. Difficulty
3/10

### 13. Estimated Time
2–3 hours

---

## Phase 21: Linting, Formatting & Pre-commit Hooks

### 1. Phase Title
Code Quality Automation

### 2. Objective
Enforce consistent code style with Ruff (lint + format), add pre-commit hooks, and eliminate style inconsistencies.

### 3. Background Theory
**Ruff** is an extremely fast Python linter and formatter (Rust-based) that replaces Black, isort, flake8, and pydocstyle. **Pre-commit hooks** run checks before allowing a commit, catching issues locally rather than in CI. **Consistent style** reduces cognitive load in code review.

**Study:**
- Ruff documentation
- Pre-commit framework documentation
- PEP 8 style guide

### 4. Learning Outcomes
- Automated code formatting
- Lint rule configuration
- Pre-commit framework usage
- Style guide enforcement

### 5. Current Problems Being Solved
- Inconsistent code style (2-space vs 4-space indentation suspected)
- No linting configuration (`.flake8`, `pyproject.toml`)
- Style issues waste review time

### 6. Implementation Tasks
1. Add `ruff` to dev dependencies
2. Configure `pyproject.toml` with Ruff settings (line length 100, Python 3.11 target)
3. Run `ruff format .` and `ruff check . --fix` across entire codebase
4. Add `.pre-commit-config.yaml` with Ruff, Bandit, and trailing-whitespace hooks
5. Install pre-commit hooks locally and verify they run
6. Add Ruff check to CI (fail on any lint error)
7. Document style guide in `docs/contributing/style-guide.md`

### 7. Files to Modify
- `apps/api-server/pyproject.toml` (add Ruff config)
- All Python files (formatting changes)
- New: `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- New: `docs/contributing/style-guide.md`

### 8. Best Practices
- Format the entire codebase in one commit to avoid merge conflicts
- Use `ruff check --select ALL` then explicitly ignore rules you don't want
- Pre-commit should be fast (<10 seconds) to not discourage usage
- Document why specific rules are ignored (e.g., `E501` for generated code)

### 9. Validation Checklist
- [ ] `ruff check .` returns zero errors
- [ ] `ruff format --check .` returns zero changes needed
- [ ] Pre-commit hooks block commits with lint errors
- [ ] CI fails if code is not formatted
- [ ] All Python files use consistent indentation

### 10. Expected Deliverables
- Formatted codebase
- Ruff configuration
- Pre-commit hooks
- Style guide documentation

### 11. Suggested Commit Strategy
```
style(format): apply ruff formatting to entire codebase
chore(lint): add ruff configuration and pre-commit hooks
docs(style): add python style guide for contributors
```

### 12. Difficulty
3/10

### 13. Estimated Time
3–4 hours

---

## Phase 22: Type Hints & Static Analysis

### 1. Phase Title
Gradual Typing with mypy

### 2. Objective
Add comprehensive type hints to all Python modules and enforce type safety with mypy in CI.

### 3. Background Theory
**Type hints** (PEP 484) document function contracts, enable IDE autocomplete, and catch bugs before runtime. **mypy** is the standard static type checker for Python. **Gradual typing** allows adding types incrementally without breaking untyped code. **TypedDict**, `Protocol`, and `Generic` enable precise typing of complex structures.

**Study:**
- mypy documentation
- "Python Type Hints" by Guido van Rossum (PEP 484)
- `typing` module deep dive (Generics, TypeVars, Protocols)

### 4. Learning Outcomes
- Python type system
- Static analysis benefits
- Generic types and protocols
- Type-driven design

### 5. Current Problems Being Solved
- No type hints in functions (suspected from README description)
- Poor IDE support for contributors
- Runtime errors that type checking would catch

### 6. Implementation Tasks
1. Add `mypy` to dev dependencies
2. Configure `mypy.ini` or `pyproject.toml` with strict settings
3. Add type hints to `core/config.py`, `core/llm_client.py`
4. Add type hints to all API route handlers (request/response types)
5. Add type hints to `orchestration/graph.py` and state definitions
6. Add type hints to `db/models.py` and `db/repositories/`
7. Run mypy in CI with `--strict` flag
8. Gradually type remaining modules over subsequent PRs

### 7. Files to Modify
- `apps/api-server/pyproject.toml` (add mypy config)
- `apps/api-server/src/core/*.py`
- `apps/api-server/src/api/routes/*.py`
- `apps/api-server/src/orchestration/*.py`
- `apps/api-server/src/db/*.py`
- `.github/workflows/ci.yml`

### 8. Best Practices
- Use `from __future__ import annotations` to avoid runtime typing overhead
- Prefer `dict[str, int]` over `Dict[str, int]` (Python 3.9+)
- Use `TypedDict` for JSON-like structures
- Use `Protocol` for duck typing (e.g., `LLMClient` protocol)
- Don't use `Any` unless absolutely necessary

### 9. Validation Checklist
- [ ] `mypy --strict apps/api-server/src` returns zero errors
- [ ] CI fails if mypy finds type errors
- [ ] All public functions have type signatures
- [ ] IDE (VS Code/PyCharm) shows accurate autocomplete for project modules

### 10. Expected Deliverables
- Type-hinted core modules
- mypy configuration
- CI type checking
- Improved IDE experience

### 11. Suggested Commit Strategy
```
type(core): add type hints to config and llm_client
type(api): add type hints to all route handlers
type(db): add type hints to models and repositories
chore(ci): add mypy strict checking to pipeline
```

### 12. Difficulty
6/10

### 13. Estimated Time
8–12 hours

---

## Phase 23: Root Cause Accuracy — Problem Decomposition

### 1. Phase Title
Algorithmic Root Cause Analysis — Problem Decomposition

### 2. Objective
Analyze why root-cause accuracy is 8.2% and decompose the problem into solvable sub-problems.

### 3. Background Theory
**Root Cause Analysis (RCA)** in SRE is fundamentally an **abductive reasoning** problem: inferring the best explanation from incomplete evidence. **Bayesian networks** model probabilistic causal relationships. **Fault trees** decompose system failures into basic events. The current 8.2% accuracy suggests the hypothesis space is too large or the evidence-to-cause mapping is too weak.

**Study:**
- "The Field Guide to Understanding Human Error" by Sidney Dekker
- Bayesian networks (pgmpy library or conceptual understanding)
- Google SRE Book: "Root Cause Analysis" chapter
- Causal inference literature (Judea Pearl's "The Book of Why")

### 4. Learning Outcomes
- Abductive reasoning in engineering
- Bayesian probability application
- Problem decomposition techniques
- SRE RCA methodologies

### 5. Current Problems Being Solved
- 8.2% root-cause accuracy is the primary value proposition failure
- System produces "plausible but generic hypotheses"
- No learned causal inference

### 6. Implementation Tasks
1. Analyze benchmark failures: categorize why each of the 121 incidents was misdiagnosed
2. Create taxonomy of failure modes: missing evidence, wrong evidence weight, temporal confusion, generic fallback
3. Measure per-category accuracy to identify weakest areas
4. Document findings in `docs/research/rca-decomposition.md`
5. Design constrained experiment: limit to 3 incident categories, target 80% accuracy
6. Propose algorithmic changes based on decomposition

### 7. Files to Modify
- `evaluation/benchmark_suite.py` (add per-category breakdown)
- New: `docs/research/rca-decomposition.md`
- `evaluation/scorers/root_cause_scorer.py` (add detailed failure logging)

### 8. Best Practices
- Use data, not intuition, to identify failure modes
- Start with a constrained domain (e.g., only database incidents)
- Document null results (approaches that didn't work)
- Share findings with mentors or online communities for feedback

### 9. Validation Checklist
- [ ] Per-category accuracy breakdown exists
- [ ] Top 3 failure modes are identified with evidence
- [ ] Constrained experiment design is documented
- [ ] At least one mentor or peer has reviewed the decomposition

### 10. Expected Deliverables
- RCA failure mode taxonomy
- Per-category accuracy report
- Constrained experiment design
- Research document

### 11. Suggested Commit Strategy
```
research(rca): analyze benchmark failures and create failure taxonomy
docs(research): document root cause decomposition and experiment design
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–10 hours

---

## Phase 24: Evidence-to-Cause Mapping Improvement

### 1. Phase Title
Structured Evidence Grounding

### 2. Objective
Improve the mapping from collected evidence (metrics, logs, deployments) to candidate causes by implementing structured evidence schemas and weighted correlation.

### 3. Background Theory
**Evidence-based reasoning** requires that every causal claim be traceable to specific observations. **Correlation does not imply causation**, but temporal correlation + physical dependency + counterfactual power provides strong evidence. **Information retrieval** techniques (TF-IDF, BM25) can match evidence patterns to known failure signatures.

**Study:**
- Evidence-based medicine principles (applicable to engineering)
- Information retrieval fundamentals (Manning, Raghavan, Schütze)
- Counterfactual reasoning in causal inference

### 4. Learning Outcomes
- Evidence structuring and weighting
- Pattern matching algorithms
- Counterfactual reasoning implementation
- Information retrieval for engineering

### 5. Current Problems Being Solved
- Evidence agents produce summaries but downstream reasoning doesn't effectively use them
- No structured schema for `EvidenceItem`
- Pattern library exists but matching is weak

### 6. Implementation Tasks
1. Redesign `EvidenceItem` schema: add `source_type`, `confidence`, `temporal_window`, `affected_services`, `raw_data_hash`
2. Implement evidence weighting: recency, source reliability, completeness
3. Create failure signature database: structured patterns with required evidence types
4. Implement matching algorithm: given evidence set, score each pattern by evidence coverage
5. Add evidence provenance: every `EvidenceItem` must trace back to raw telemetry query
6. Update `rootcause_agent` to use structured evidence instead of free-text summaries
7. Add tests: given known evidence, verify correct pattern is top-ranked

### 7. Files to Modify
- `apps/api-server/src/agents/rootcause_agent/evidence_builder.py`
- `apps/api-server/src/agents/rootcause_agent/evidence_normalizer.py`
- `apps/api-server/src/retrieval/pattern_store.py` (new or existing)
- `apps/api-server/src/causality/causal_graph.py`
- `apps/api-server/src/agents/rootcause_agent/scorer.py`

### 8. Best Practices
- Every evidence item should have a SHA-256 hash of raw data for integrity
- Weight evidence by source reliability (metrics > logs > deployment events)
- Require multiple independent evidence types for high-confidence causes
- Log evidence-to-cause scoring for post-hoc analysis

### 9. Validation Checklist
- [ ] `EvidenceItem` has structured schema with all required fields
- [ ] Given a CPU spike + OOMKill log, system identifies memory pressure as top cause
- [ ] Evidence provenance traces back to specific Prometheus query or Loki search
- [ ] Pattern matching score correlates with actual root-cause accuracy

### 10. Expected Deliverables
- Structured `EvidenceItem` schema
- Evidence weighting algorithm
- Failure signature database
- Updated root cause agent

### 11. Suggested Commit Strategy
```
feat(evidence): redesign EvidenceItem with structured schema and provenance
feat(retrieval): implement failure signature matching with evidence coverage scoring
refactor(rootcause): use structured evidence instead of free-text summaries
```

### 12. Difficulty
8/10

### 13. Estimated Time
10–14 hours

---

## Phase 25: Heuristic Causality Refinement

### 1. Phase Title
Rule-Based Causality Enhancement

### 2. Objective
Refine the heuristic causal reasoning engine to achieve >50% accuracy on the constrained domain (3 incident categories) before attempting learned models.

### 3. Background Theory
**Heuristic models** (expert systems, rule engines) can achieve high accuracy in narrow domains with less data than ML models. **Expert systems** use IF-THEN rules derived from domain knowledge. **Rete algorithm** efficiently matches rules against facts. Before investing in learned causality, prove the problem is solvable with rules.

**Study:**
- Expert systems principles (CLIPS, Drools)
- Rete algorithm (Forgy, 1982)
- SRE runbooks as executable rules

### 4. Learning Outcomes
- Rule engine design
- Heuristic reasoning optimization
- Domain knowledge encoding
- Expert system implementation

### 5. Current Problems Being Solved
- No learned causal inference exists; heuristic engine is the only option currently
- Heuristic engine is too generic
- Need to prove the problem is solvable before adding ML complexity

### 6. Implementation Tasks
1. Select 3 incident categories: database failures, memory pressure, deployment regressions
2. Interview SREs or research runbooks to extract causal rules for these categories
3. Encode rules in YAML/JSON: `IF cpu_usage > 90% AND memory_usage > 85% THEN candidate=memory_pressure`
4. Implement rule engine with confidence aggregation (multiple rules can fire)
5. Add rule conflict resolution: if rules disagree, lower confidence and escalate
6. Test against benchmark subset: target 80% accuracy on 3 categories
7. Document rule coverage and gaps

### 7. Files to Modify
- New: `apps/api-server/src/causality/rules/` (rule definitions)
- New: `apps/api-server/src/causality/rule_engine.py`
- `apps/api-server/src/agents/rootcause_agent/agent.py`
- `configs/production/causality_rules.yaml`

### 8. Best Practices
- Rules should be human-readable and maintainable
- Every rule must have a documented source (runbook, incident postmortem)
- Rule engine should log which rules fired for each incident
- Start with high-precision rules (few false positives) even if recall is low

### 9. Validation Checklist
- [ ] Rule engine achieves >50% accuracy on full benchmark (up from 8.2%)
- [ ] Rule engine achieves >80% on constrained 3-category subset
- [ ] Every rule has a documented source
- [ ] Rule conflicts are detected and logged

### 10. Expected Deliverables
- Rule-based causal engine
- Rule definitions for 3 categories
- Accuracy improvement report
- Rule coverage documentation

### 11. Suggested Commit Strategy
```
feat(causality): implement rule-based causal reasoning engine
feat(causality): add database, memory, and deployment rule sets
test(causality): verify >50% accuracy on full benchmark
```

### 12. Difficulty
8/10

### 13. Estimated Time
12–16 hours

---

## Phase 26: Confidence Calibration Fix

### 1. Phase Title
Statistical Confidence Calibration

### 2. Objective
Fix the ECE 0.2045 and 87.5% underconfidence by implementing proper calibration techniques.

### 3. Background Theory
**Calibration** measures whether a model's confidence matches its accuracy. **Expected Calibration Error (ECE)** bins predictions by confidence and measures the average gap. **Platt scaling** and **isotonic regression** are post-processing techniques that map raw scores to calibrated probabilities. **Temperature scaling** (the current "hack") is a single-parameter Platt scaling method; it should be learned from a validation set, not hardcoded.

**Study:**
- "On Calibration of Modern Neural Networks" (Guo et al., 2017)
- Scikit-learn: `CalibratedClassifierCV`
- Temperature scaling implementation

### 4. Learning Outcomes
- Probability calibration theory
- ECE and Brier score computation
- Temperature scaling and Platt scaling
- Validation set design for calibration

### 5. Current Problems Being Solved
- ECE 0.2045 (poor calibration)
- 87.5% underconfidence (systematic bias)
- Hardcoded calibration temperature 1.35

### 6. Implementation Tasks
1. Separate calibration dataset: 20% of benchmark held out for calibration only
2. Implement temperature scaling: learn T by minimizing NLL on calibration set
3. Replace hardcoded 1.35 with learned T
4. Add isotonic regression as alternative calibration method
5. Recompute ECE and Brier score after calibration
6. Add calibration visualization: reliability diagram (confidence vs. accuracy)
7. Document calibration procedure in `docs/research/calibration.md`

### 7. Files to Modify
- `apps/api-server/src/causality/reality/uncertainty_collapse.py`
- `apps/api-server/src/evaluation/scorers/confidence_calibration_scorer.py`
- New: `apps/api-server/src/causality/calibration.py`
- `evaluation/runner.py` (add calibration split)

### 8. Best Practices
- Never calibrate on test set — use held-out calibration set
- Recalibrate when model or features change
- Monitor calibration drift in production
- Use reliability diagrams for visual validation

### 9. Validation Checklist
- [ ] ECE < 0.10 on calibration set
- [ ] ECE < 0.15 on test set
- [ ] Underconfidence rate < 30%
- [ ] Reliability diagram shows diagonal alignment
- [ ] Temperature parameter is learned, not hardcoded

### 10. Expected Deliverables
- Calibrated confidence scoring
- Learned temperature parameter
- Reliability diagram
- Calibration documentation

### 11. Suggested Commit Strategy
```
feat(calibration): implement temperature scaling with learned parameter
feat(calibration): add isotonic regression calibration alternative
test(calibration): verify ECE < 0.10 on held-out set
```

### 12. Difficulty
7/10

### 13. Estimated Time
8–12 hours

---

## Phase 27: Uncertainty Engine Overhaul

### 1. Phase Title
Uncertainty Quantification & Escalation Logic

### 2. Objective
Redesign the UncertaintyEngine to properly propagate uncertainty through the pipeline and make escalation decisions based on calibrated confidence.

### 3. Background Theory
**Uncertainty quantification** distinguishes between **aleatoric uncertainty** (inherent randomness) and **epistemic uncertainty** (lack of knowledge). **Bayesian neural networks** and **Monte Carlo dropout** estimate uncertainty in ML models. For heuristic systems, uncertainty can be estimated by: evidence coverage, model disagreement, and out-of-distribution detection.

**Study:**
- "Uncertainty in Deep Learning" by Yarin Gal
- Bayesian probability theory
- Out-of-distribution detection methods

### 4. Learning Outcomes
- Uncertainty types (aleatoric vs. epistemic)
- Uncertainty propagation
- Escalation threshold design
- Decision theory under uncertainty

### 5. Current Problems Being Solved
- `UncertaintyCollapseGuard` exists but calibration is poor
- Escalation triggers may fire too often due to underconfidence
- No distinction between "I don't know" and "the data is noisy"

### 6. Implementation Tasks
1. Redesign `UncertaintyEngine` to output: `confidence`, `uncertainty_type`, `evidence_gaps`
2. Add evidence gap analysis: which telemetry types would reduce uncertainty
3. Implement escalation matrix: low confidence + high severity = mandatory human
4. Add `should_refuse_attribution` logic based on evidence coverage, not just confidence
5. Propagate uncertainty to downstream agents (risk agent should know root cause is uncertain)
6. Add tests: verify escalation decisions match expected outcomes for benchmark incidents
7. Document uncertainty model in `docs/architecture/uncertainty.md`

### 7. Files to Modify
- `apps/api-server/src/agents/uncertainty.py`
- `apps/api-server/src/causality/reality/uncertainty_collapse.py`
- `apps/api-server/src/causality/reality/ambiguity_resolver.py`
- `apps/api-server/src/agents/risk_agent/agent.py`
- `apps/api-server/src/orchestration/graph.py` (escalation edges)

### 8. Best Practices
- Escalation thresholds should be configurable per organization
- Always provide evidence gap analysis when escalating ("Need logs from service X")
- Log uncertainty metrics for post-hoc analysis
- Never auto-execute when epistemic uncertainty is high

### 9. Validation Checklist
- [ ] UncertaintyEngine outputs confidence, type, and gaps
- [ ] 8/8 dangerous incidents still trigger escalation
- [ ] False positive rate (unnecessary escalation) < 20%
- [ ] Evidence gap analysis is actionable

### 10. Expected Deliverables
- Redesigned UncertaintyEngine
- Escalation matrix
- Evidence gap analysis
- Uncertainty architecture document

### 11. Suggested Commit Strategy
```
feat(uncertainty): redesign UncertaintyEngine with type and gap analysis
feat(escalation): implement configurable escalation matrix
feat(risk): propagate uncertainty to risk assessment agent
```

### 12. Difficulty
7/10

### 13. Estimated Time
8–12 hours

---

## Phase 28: Deterministic Fallback Classifier Implementation

### 1. Phase Title
Zero-Dependency Fallback Classification

### 2. Objective
Build and validate the deterministic fallback classifier that activates when all LLM providers fail.

### 3. Background Theory
**Deterministic classifiers** use rules, decision trees, or keyword matching instead of probabilistic models. **Zero-dependency** means no external APIs, no ML models, just code. **Fail-operational** systems (aviation term) continue operating with reduced capability rather than failing entirely. The fallback should be: fast, reliable, and safe (conservative).

**Study:**
- Decision tree algorithms (scikit-learn or manual implementation)
- Keyword extraction (TF-IDF, RAKE)
- Fail-operational system design (aviation/aerospace principles)

### 4. Learning Outcomes
- Deterministic classification
- Decision tree implementation
- Fail-operational design
- Conservative system design

### 5. Current Problems Being Solved
- Layer 4 fallback exists but may not be fully implemented
- Fallback classifier needs to be unit-testable without LLM calls
- Fallback should escalate to humans rather than guess incorrectly

### 6. Implementation Tasks
1. Implement `DeterministicClassifier` class with keyword-based classification
2. Create keyword maps for each incident category: `{"database": ["timeout", "connection", "deadlock"], ...}`
3. Add topology-aware rules: if affected service is `payment-db`, classify as database failure
4. Implement conservative default: if no keywords match, classify as `unknown` and escalate
5. Add confidence scoring for fallback: keyword coverage ratio
6. Test against benchmark: verify fallback doesn't misclassify dangerous incidents
7. Add metrics: `fallback_classifications_total`, `fallback_escalations_total`

### 7. Files to Modify
- `apps/api-server/src/core/resilience/deterministic_fallback.py` (new or existing)
- `apps/api-server/src/core/resilience/provider_chain.py`
- `apps/api-server/src/agents/router_agent/agent.py`
- `configs/production/fallback_keywords.yaml`

### 8. Best Practices
- Fallback should be extremely conservative (better to escalate than misclassify)
- Keywords should be curated by domain experts
- Fallback classifier should complete in <100ms
- Log every fallback activation with full incident payload for analysis

### 9. Validation Checklist
- [ ] Fallback classifies 121 benchmark incidents without LLM calls
- [ ] No dangerous incident is misclassified as safe by fallback
- [ ] Fallback completes in <100ms per incident
- [ ] Fallback activation triggers human notification
- [ ] Unit tests verify fallback behavior without network

### 10. Expected Deliverables
- Deterministic fallback classifier
- Keyword configuration
- Fallback metrics
- Unit tests

### 11. Suggested Commit Strategy
```
feat(resilience): implement deterministic fallback classifier
feat(resilience): add topology-aware classification rules
feat(metrics): add fallback activation and escalation metrics
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–8 hours

---

## Phase 29: Live Telemetry Connector Architecture

### 1. Phase Title
Real-World Telemetry Integration Design

### 2. Objective
Design the architecture for connecting to live Prometheus, Loki, and GitHub APIs instead of mocked responses.

### 3. Background Theory
**Adapter pattern** wraps external APIs with a consistent internal interface. **Circuit breakers** (already implemented for LLMs) should also protect telemetry queries. **Caching** reduces load on external systems. **Query languages** (PromQL, LogQL) require validation to prevent injection. **Time-series databases** have specific query patterns and limitations.

**Study:**
- Prometheus HTTP API documentation
- Loki API documentation
- GitHub REST API documentation
- Adapter pattern (GoF)

### 4. Learning Outcomes
- API adapter design
- Time-series query construction
- External API resilience
- Caching strategies for telemetry

### 5. Current Problems Being Solved
- Evidence agents use mocked infrastructure in benchmarks
- No live telemetry grounding
- Prometheus/Loki connectors are "dev connectors" not production-hardened

### 6. Implementation Tasks
1. Design `TelemetryAdapter` protocol with methods: `query_metrics`, `query_logs`, `query_deployments`
2. Implement `PrometheusAdapter` with PromQL query builder and validation
3. Implement `LokiAdapter` with LogQL query builder
4. Implement `GitHubAdapter` for deployment queries
5. Add query result caching (Redis) with 30-second TTL for metrics
6. Add circuit breakers for each telemetry source
7. Add query timeout enforcement (5 seconds max)
8. Document adapter interface in `docs/architecture/telemetry.md`

### 7. Files to Modify
- New: `apps/api-server/src/telemetry/adapters/base.py`
- New: `apps/api-server/src/telemetry/adapters/prometheus.py`
- New: `apps/api-server/src/telemetry/adapters/loki.py`
- New: `apps/api-server/src/telemetry/adapters/github.py`
- `apps/api-server/src/tools/` (refactor existing tools to use adapters)

### 8. Best Practices
- Adapters should return domain objects, not raw API responses
- PromQL queries should be parameterized, not string-interpolated
- Cache only non-sensitive data
- Log query latency and cache hit rates

### 9. Validation Checklist
- [ ] Adapter protocol is well-defined with type hints
- [ ] Prometheus adapter connects to real Prometheus instance in dev
- [ ] Loki adapter connects to real Loki instance in dev
- [ ] Circuit breaker opens if Prometheus is down for 30 seconds
- [ ] Cache reduces repeated identical queries

### 10. Expected Deliverables
- Telemetry adapter architecture
- Prometheus, Loki, GitHub adapters
- Circuit breaker integration
- Telemetry architecture document

### 11. Suggested Commit Strategy
```
feat(telemetry): design TelemetryAdapter protocol and architecture
feat(telemetry): implement PrometheusAdapter with PromQL builder
feat(telemetry): implement LokiAdapter and GitHubAdapter
```

### 12. Difficulty
7/10

### 13. Estimated Time
8–12 hours

---

## Phase 30: Prometheus Client Implementation

### 1. Phase Title
Production-Hardened Metrics Querying

### 2. Objective
Implement and validate the Prometheus adapter with real query capabilities, error handling, and result caching.

### 3. Background Theory
**PromQL** (Prometheus Query Language) supports instant queries, range queries, and metadata queries. **Range vectors** (`[5m]`) require careful time alignment. **Metric types** (counter, gauge, histogram, summary) have different query patterns. **Cardinality** explosion occurs when queries return too many time series.

**Study:**
- Prometheus Querying Basics (prometheus.io/docs)
- PromQL cheat sheet
- Metric types and aggregation operators

### 4. Learning Outcomes
- PromQL query construction
- Time-series data handling
- Metric cardinality management
- Production API client design

### 5. Current Problems Being Solved
- Metrics agent uses mocked responses
- No real Prometheus integration
- No evidence of PromQL validation

### 6. Implementation Tasks
1. Implement `PrometheusAdapter.query()` with instant and range query support
2. Add PromQL validation: reject queries with high cardinality risk
3. Add result parsing: convert Prometheus JSON to `MetricEvidence` objects
4. Add anomaly detection: z-score calculation on returned time series
5. Add caching: cache query results for 30 seconds
6. Add error handling: timeout, connection refused, invalid PromQL
7. Write integration tests against test Prometheus instance
8. Document supported queries and limitations

### 7. Files to Modify
- `apps/api-server/src/telemetry/adapters/prometheus.py`
- `apps/api-server/src/agents/metrics_agent/agent.py`
- `apps/api-server/tests/integration/test_telemetry.py`

### 8. Best Practices
- Always use `rate()` or `increase()` for counters, never raw counter values
- Limit query range to prevent timeouts
- Use aggregation (`sum by (instance)`) to reduce cardinality
- Validate PromQL syntax before sending (use `promql-parser` library)

### 9. Validation Checklist
- [ ] Adapter queries real Prometheus and returns structured data
- [ ] Invalid PromQL is rejected before sending
- [ ] High-cardinality queries are detected and rejected
- [ ] Z-score anomaly detection identifies spikes correctly
- [ ] Cache hit rate >50% for repeated queries

### 10. Expected Deliverables
- Prometheus adapter implementation
- PromQL validation
- Anomaly detection
- Integration tests

### 11. Suggested Commit Strategy
```
feat(prometheus): implement production adapter with PromQL validation
feat(metrics): add z-score anomaly detection to metrics agent
test(integration): add Prometheus adapter integration tests
```

### 12. Difficulty
7/10

### 13. Estimated Time
8–12 hours

---

## Phase 31: Loki/GitHub Connector Hardening

### 1. Phase Title
Log Aggregation & Deployment Traceability

### 2. Objective
Implement production-hardened Loki and GitHub adapters with proper authentication, pagination, and error handling.

### 3. Background Theory
**LogQL** (Loki Query Language) uses label matchers and line filters. **Structured logging** (JSON) enables efficient querying. **GitHub API** has rate limits (5000 requests/hour for authenticated users). **Pagination** is required for large result sets. **OAuth** or **Personal Access Tokens** authenticate GitHub API requests.

**Study:**
- Loki LogQL documentation
- GitHub REST API rate limiting
- OAuth 2.0 for GitHub Apps
- Structured logging best practices

### 4. Learning Outcomes
- LogQL query construction
- GitHub API integration
- Rate limit handling
- Pagination strategies

### 5. Current Problems Being Solved
- Logs agent uses mocked responses
- Deployment agent uses mocked responses
- No evidence of GitHub rate limit handling

### 6. Implementation Tasks
1. Implement `LokiAdapter` with LogQL builder and label validation
2. Add structured log parsing: extract fields from JSON logs
3. Implement `GitHubAdapter` with PAT authentication
4. Add GitHub rate limit monitoring: check `X-RateLimit-Remaining` header
5. Add pagination for large commit/deployment histories
6. Add error handling: 404 (repo not found), 403 (rate limit), 500
7. Write integration tests against test Loki and GitHub (mock server or real)
8. Document authentication setup

### 7. Files to Modify
- `apps/api-server/src/telemetry/adapters/loki.py`
- `apps/api-server/src/telemetry/adapters/github.py`
- `apps/api-server/src/agents/logs_agent/agent.py`
- `apps/api-server/src/agents/deployment_agent/agent.py`
- `apps/api-server/tests/integration/test_telemetry.py`

### 8. Best Practices
- Cache GitHub API responses aggressively (deployments don't change frequently)
- Use `retry-after` header for rate limit handling
- Parse structured logs before storing (extract trace_id, error_code)
- LogQL queries should be time-bounded to prevent resource exhaustion

### 9. Validation Checklist
- [ ] Loki adapter queries real Loki and returns structured log entries
- [ ] GitHub adapter handles rate limits gracefully (waits or fails safe)
- [ ] Pagination retrieves full commit history for large repos
- [ ] Integration tests pass against real or mock services

### 10. Expected Deliverables
- Loki adapter
- GitHub adapter
- Rate limit handling
- Integration tests

### 11. Suggested Commit Strategy
```
feat(loki): implement production adapter with LogQL builder
feat(github): implement deployment adapter with rate limit handling
feat(telemetry): add pagination and error handling for external APIs
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–10 hours

---

## Phase 32: Topology Graph Dynamic Updates

### 1. Phase Title
Live Service Graph Construction

### 2. Objective
Replace static topology YAML with dynamic service graph construction from real infrastructure data.

### 3. Background Theory
**Service topology** represents dependencies between microservices. **Service discovery** (Consul, Kubernetes DNS, AWS CloudMap) provides real-time service lists. **Dependency graphs** can be constructed from: tracing data (spans), deployment manifests, or network flows. **Graph databases** (Neo4j) or in-memory graphs (NetworkX) store topology.

**Study:**
- Kubernetes service discovery
- OpenTelemetry service graphs
- NetworkX library for graph operations
- Service mesh architecture (Istio, Linkerd)

### 4. Learning Outcomes
- Service discovery integration
- Graph data structures
- Dynamic topology updates
- Dependency analysis

### 5. Current Problems Being Solved
- Blast radius uses static service graph
- No live traffic data
- Topology YAML is manually maintained

### 6. Implementation Tasks
1. Design `TopologyService` that fetches service list from Kubernetes API or Prometheus labels
2. Implement graph construction: services as nodes, dependencies as edges
3. Add dynamic updates: refresh topology every 5 minutes
4. Add dependency inference: from tracing data or explicit annotations
5. Update `risk_agent/blast_radius.py` to use dynamic graph
6. Add health check: verify topology graph is not empty
7. Document topology source and update frequency

### 7. Files to Modify
- New: `apps/api-server/src/topology/service.py`
- `apps/api-server/src/agents/risk_agent/blast_radius.py`
- `configs/development/topology.yaml` (keep as fallback)
- `apps/api-server/src/api/routes/health.py`

### 8. Best Practices
- Always have static fallback if dynamic discovery fails
- Cache topology for 5 minutes to reduce API load
- Validate graph consistency (no cycles in dependency graph)
- Log topology changes (service added/removed)

### 9. Validation Checklist
- [ ] Topology graph updates when new service is deployed
- [ ] Blast radius calculation uses current topology
- [ ] Fallback to static YAML if discovery is unavailable
- [ ] Graph consistency check passes (no cycles)

### 10. Expected Deliverables
- Dynamic topology service
- Graph construction and updates
- Updated blast radius calculation
- Topology health check

### 11. Suggested Commit Strategy
```
feat(topology): implement dynamic service graph construction
feat(topology): add Kubernetes/Prometheus service discovery
feat(risk): update blast radius to use live topology
```

### 12. Difficulty
7/10

### 13. Estimated Time
8–12 hours

---

## Phase 33: API Versioning & OpenAPI Spec

### 1. Phase Title
Professional API Contract Management

### 2. Objective
Implement API versioning and generate OpenAPI specification automatically from FastAPI.

### 3. Background Theory
**API versioning** allows breaking changes without breaking clients. Common strategies: URL path (`/v1/`, `/v2/`), header (`Accept: application/vnd.sentinelops.v1+json`), or query parameter. **OpenAPI** (formerly Swagger) is the standard for REST API documentation. **FastAPI** generates OpenAPI specs automatically from type hints.

**Study:**
- FastAPI docs: "Bigger Applications" and "OpenAPI"
- OpenAPI 3.0 specification
- API versioning strategies (Stripe, GitHub examples)

### 4. Learning Outcomes
- API versioning implementation
- OpenAPI specification
- FastAPI advanced features
- API contract testing

### 5. Current Problems Being Solved
- No API versioning (endpoints are `/incidents`, not `/v1/incidents`)
- No OpenAPI spec generation evidence
- API documentation is manual (table in README)

### 6. Implementation Tasks
1. Add API router versioning: `api/v1/routes/`
2. Move existing routes to `/v1/` prefix with backward compatibility
3. Verify FastAPI generates `/openapi.json` and `/docs`
4. Customize OpenAPI metadata: title, version, description, contact
5. Add authentication scheme to OpenAPI (JWT bearer)
6. Add example requests/responses to all schemas
7. Add `x-tagGroups` or similar for organization
8. Document deprecation policy in `docs/api/deprecation.md`

### 7. Files to Modify
- `apps/api-server/src/api/routes/` → `apps/api-server/src/api/v1/routes/`
- `apps/api-server/src/main.py` (add versioned routers)
- `apps/api-server/src/api/schemas/` (add examples)

### 8. Best Practices
- Never break existing clients without deprecation period
- Use `deprecated=True` in FastAPI for endpoints being phased out
- OpenAPI examples should be realistic, not `string` or `123`
- Version in URL path is most pragmatic for internal APIs

### 9. Validation Checklist
- [ ] `/v1/incidents` works
- [ ] `/docs` shows interactive Swagger UI with all endpoints
- [ ] `/openapi.json` validates against OpenAPI 3.0 schema
- [ ] Authentication is documented in Swagger UI
- [ ] All endpoints have request/response examples

### 10. Expected Deliverables
- Versioned API routes
- Interactive API documentation
- OpenAPI specification
- Deprecation policy

### 11. Suggested Commit Strategy
```
feat(api): add v1 prefix and versioned router structure
feat(docs): generate OpenAPI spec with examples and auth schemes
docs(api): add API deprecation policy
```

### 12. Difficulty
4/10

### 13. Estimated Time
4–6 hours

---

## Phase 34: API Input Validation & Rate Limiting

### 1. Phase Title
Edge Protection & Throttling

### 2. Objective
Implement comprehensive rate limiting, request size limits, and DDoS protection for all API endpoints.

### 3. Background Theory
**Rate limiting** controls request frequency per client. **Token bucket** algorithm allows bursts while limiting sustained rate. **SlowAPI** is a rate limiter for FastAPI/Flask based on token bucket. **Request size limits** prevent memory exhaustion from large payloads. **DDoS protection** at the edge (Cloudflare, AWS WAF) is preferred, but application-level protection is necessary too.

**Study:**
- SlowAPI documentation
- Token bucket algorithm
- OWASP Rate Limiting Cheat Sheet
- Redis-based rate limiting (for distributed deployments)

### 4. Learning Outcomes
- Rate limiting algorithms
- Redis-backed distributed rate limiting
- Request validation at the edge
- DDoS mitigation strategies

### 5. Current Problems Being Solved
- No rate limiting on `/incidents/webhook` (alert storm risk)
- No rate limiting on login (brute force risk)
- No request size limits

### 6. Implementation Tasks
1. Add `slowapi` or custom Redis-based rate limiter
2. Configure limits: webhook 10/min, login 5/min, general 100/min
3. Add per-IP and per-API-key rate limiting
4. Add request size limit (10MB max)
5. Add rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`
6. Add custom error response for rate limit exceeded (429)
7. Test rate limiting with load testing tool (k6 or Locust)

### 7. Files to Modify
- `apps/api-server/src/main.py` (add rate limiter middleware)
- `apps/api-server/src/api/middleware/rate_limit.py` (new)
- `apps/api-server/src/api/routes/incidents.py` (add decorators)
- `apps/api-server/src/api/routes/auth.py` (add decorators)

### 8. Best Practices
- Use Redis for distributed rate limiting (not in-memory)
- Return 429 with `Retry-After` header
- Log rate limit violations for security monitoring
- Different limits for authenticated vs. unauthenticated users

### 9. Validation Checklist
- [ ] 11th webhook request in 1 minute returns 429
- [ ] 6th login attempt in 1 minute returns 429
- [ ] 11MB request returns 413 Payload Too Large
- [ ] Rate limit headers are present in all responses
- [ ] Distributed rate limiting works across multiple API instances

### 10. Expected Deliverables
- Rate limiting middleware
- Redis-backed distributed limits
- Request size limits
- Load test verification

### 11. Suggested Commit Strategy
```
feat(security): add Redis-backed rate limiting middleware
feat(security): implement per-endpoint rate limit rules
feat(security): add request size limits and 413 responses
```

### 12. Difficulty
5/10

### 13. Estimated Time
4–6 hours

---

## Phase 35: Frontend Testing & Accessibility

### 1. Phase Title
Dashboard Quality Assurance

### 2. Objective
Add comprehensive testing to the Next.js dashboard: unit tests, integration tests, and accessibility audits.

### 3. Background Theory
**React Testing Library** tests components from the user's perspective. **Jest** is the standard test runner. **Playwright** (or Cypress) handles E2E browser testing. **Accessibility (a11y)** testing with axe-core ensures compliance with WCAG standards. **Component-driven development** (Storybook) isolates and documents UI components.

**Study:**
- React Testing Library documentation
- Jest mocking strategies
- axe-core accessibility testing
- Storybook for React

### 4. Learning Outcomes
- Frontend testing patterns
- Accessibility compliance (WCAG 2.1)
- Component isolation with Storybook
- E2E browser automation

### 5. Current Problems Being Solved
- No evidence of frontend testing
- No accessibility evaluation
- Dashboard quality unknown

### 6. Implementation Tasks
1. Add Jest + React Testing Library to `web-dashboard/`
2. Write unit tests for critical components: IncidentCard, ApprovalButton, TraceViewer
3. Add accessibility tests with `@axe-core/react`
4. Add Storybook for component documentation and visual testing
5. Add Playwright E2E tests for critical user flows
6. Add frontend CI workflow: build, test, lint, accessibility check
7. Fix any critical accessibility issues (color contrast, keyboard navigation)

### 7. Files to Modify
- `apps/web-dashboard/package.json` (add dev dependencies)
- New: `apps/web-dashboard/src/components/__tests__/`
- New: `apps/web-dashboard/.storybook/`
- New: `apps/web-dashboard/e2e/`
- `.github/workflows/frontend-ci.yml`

### 8. Best Practices
- Test behavior, not implementation (React Testing Library philosophy)
- Use `screen` queries that match how users interact (getByRole, getByLabelText)
- Accessibility tests should run in CI and fail on violations
- Storybook stories should cover all component states

### 9. Validation Checklist
- [ ] `npm test` passes with >70% component coverage
- [ ] `npm run test:a11y` passes with zero critical violations
- [ ] Storybook builds and displays all components
- [ ] Playwright E2E tests pass against local backend
- [ ] Frontend CI workflow passes

### 10. Expected Deliverables
- Frontend unit tests
- Accessibility audit report
- Storybook instance
- Playwright E2E tests
- Frontend CI workflow

### 11. Suggested Commit Strategy
```
test(frontend): add Jest and React Testing Library setup
test(frontend): add unit tests for IncidentCard and ApprovalButton
feat(a11y): add axe-core accessibility testing and fix violations
chore(storybook): add component documentation
```

### 12. Difficulty
6/10

### 13. Estimated Time
8–12 hours

---

## Phase 36: Frontend-Backend Integration Hardening

### 1. Phase Title
Full-Stack Contract Validation

### 2. Objective
Ensure the Next.js dashboard and FastAPI backend have a validated, type-safe contract with error handling and retry logic.

### 3. Background Theory
**API contract testing** verifies that frontend and backend agree on request/response shapes. **OpenAPI Generator** can create TypeScript client code from the OpenAPI spec. **TanStack Query** (React Query) handles caching, background refetching, and error states. **Type-safe APIs** prevent runtime errors from contract mismatches.

**Study:**
- OpenAPI Generator documentation
- TanStack Query documentation
- Zod for runtime schema validation
- API mocking with MSW (Mock Service Worker)

### 4. Learning Outcomes
- Contract testing
- Type-safe API clients
- Frontend state management
- Error boundary design

### 5. Current Problems Being Solved
- No evidence of type-safe API client generation
- Frontend may not handle backend errors gracefully
- Contract mismatches between frontend and backend

### 6. Implementation Tasks
1. Generate TypeScript API client from OpenAPI spec using `openapi-typescript`
2. Add Zod schemas for runtime validation of API responses
3. Implement TanStack Query hooks for all API endpoints
4. Add error boundaries and retry logic for network failures
5. Add loading states and skeleton screens for all async operations
6. Implement WebSocket reconnection logic for real-time updates
7. Add MSW for frontend testing without backend

### 7. Files to Modify
- `apps/web-dashboard/src/services/api.ts` (generate from OpenAPI)
- `apps/web-dashboard/src/hooks/` (TanStack Query hooks)
- `apps/web-dashboard/src/components/ErrorBoundary.tsx`
- `apps/web-dashboard/src/mocks/` (MSW setup)

### 8. Best Practices
- Never trust backend responses; validate at runtime with Zod
- Use stale-while-revalidate caching for incident lists
- Implement exponential backoff for WebSocket reconnection
- Error boundaries should catch rendering errors, not just API errors

### 9. Validation Checklist
- [ ] TypeScript API client compiles without errors
- [ ] Zod validation catches malformed backend responses
- [ ] Frontend handles 500 errors with user-friendly message
- [ ] WebSocket reconnects automatically after network interruption
- [ ] MSW allows frontend development without running backend

### 10. Expected Deliverables
- Type-safe API client
- TanStack Query hooks
- Error boundaries
- MSW mock server

### 11. Suggested Commit Strategy
```
feat(frontend): generate TypeScript API client from OpenAPI spec
feat(frontend): add TanStack Query hooks with caching and retry
feat(frontend): implement error boundaries and loading states
```

### 12. Difficulty
6/10

### 13. Estimated Time
8–10 hours

---

## Phase 37: Docker Image Pinning & Multi-stage Optimization

### 1. Phase Title
Container Supply Chain Hardening

### 2. Objective
Replace all `:latest` tags with pinned digests, optimize multi-stage builds, and implement container security scanning.

### 3. Background Theory
**Docker image digests** (SHA-256) provide immutable references. **Multi-stage builds** reduce final image size by excluding build tools. **Distroless images** (Google) contain only the application and its runtime dependencies, reducing attack surface. **BuildKit** is Docker's modern builder with advanced caching.

**Study:**
- Docker multi-stage builds documentation
- Google Distroless images
- Docker BuildKit features
- Container image layer caching

### 4. Learning Outcomes
- Immutable container references
- Multi-stage build optimization
- Distroless image usage
- BuildKit caching

### 5. Current Problems Being Solved
- `:latest` tags in docker-compose.yml
- No image digest pinning
- Potential large image sizes

### 6. Implementation Tasks
1. Audit all Dockerfiles for optimization opportunities
2. Pin base images to specific digests in Dockerfiles
3. Optimize multi-stage builds: separate build and runtime stages
4. Consider distroless for Python (or `python:3.11-slim` at minimum)
5. Add `.dockerignore` to exclude unnecessary files
6. Run Trivy scan on built images in CI
7. Push images to GitHub Container Registry (GHCR)

### 7. Files to Modify
- `apps/api-server/Dockerfile`
- `apps/web-dashboard/Dockerfile`
- `docker-compose.yml`
- New: `.dockerignore`
- `.github/workflows/ci.yml`

### 8. Best Practices
- Use BuildKit (`DOCKER_BUILDKIT=1`)
- Copy only necessary files (use `.dockerignore`)
- Run containers as non-root (`USER` directive)
- Pin to digest, not just tag (`python:3.11-slim@sha256:...`)

### 9. Validation Checklist
- [ ] All images pinned to SHA-256 digests
- [ ] `docker images` shows reduced size after multi-stage optimization
- [ ] Trivy scan passes with zero CRITICAL vulnerabilities
- [ ] Container runs as non-root user
- [ ] BuildKit cache is effective (second build is fast)

### 10. Expected Deliverables
- Optimized Dockerfiles
- Pinned image references
- `.dockerignore`
- Container scan results

### 11. Suggested Commit Strategy
```
build(docker): pin all base images to SHA-256 digests
build(docker): optimize api-server Dockerfile with multi-stage build
chore(security): add Trivy container scan to CI
```

### 12. Difficulty
5/10

### 13. Estimated Time
4–6 hours

---

## Phase 38: Container Registry & CI Build Pipeline

### 1. Phase Title
Artifact Management & Automated Builds

### 2. Objective
Implement automated container image building, tagging, and pushing to a container registry on every PR and release.

### 3. Background Theory
**Container registries** (Docker Hub, GHCR, ECR, GCR) store and distribute images. **Image tagging** strategies include: `latest`, semantic version (`v1.2.3`), Git SHA (`sha-abc123`), and branch name. **BuildKit cache mounts** speed up builds by caching dependency layers. **GitHub Actions** `docker/build-push-action` simplifies CI integration.

**Study:**
- GitHub Container Registry documentation
- Docker build-push-action
- Semantic versioning for containers
- Image signing with Cosign

### 4. Learning Outcomes
- Container registry management
- Automated image building
- Image tagging strategies
- CI artifact management

### 5. Current Problems Being Solved
- README states: *"Not yet implemented: container registry push"*
- No automated image builds
- Manual image creation for deployment

### 6. Implementation Tasks
1. Enable GitHub Container Registry for the repository
2. Add `docker/build-push-action` to CI workflow
3. Build and push on every PR (tag: `pr-{number}`)
4. Build and push on every merge to main (tag: `main-{sha}`)
5. Build and push on every release tag (tag: `v1.2.3`)
6. Add image signing with Cosign (optional but impressive)
7. Document image usage in `docs/deployment/containers.md`

### 7. Files to Modify
- `.github/workflows/ci.yml` (add build-push job)
- New: `.github/workflows/release.yml`
- `README.md` (add image pull instructions)

### 8. Best Practices
- Never push `latest` tag from CI (use explicit versions)
- Tag with Git SHA for traceability
- Use layer caching in BuildKit (`cache-from`, `cache-to`)
- Sign images for supply chain security

### 9. Validation Checklist
- [ ] PR triggers image build and push to GHCR
- [ ] Image is pullable with `docker pull ghcr.io/user/sentinelops:pr-1`
- [ ] Release tag `v0.1.0` triggers image push with same tag
- [ ] Image size and layer count are optimized
- [ ] Image signing verification works (if implemented)

### 10. Expected Deliverables
- CI build-push workflow
- Container registry integration
- Image tagging strategy
- Signed images (optional)

### 11. Suggested Commit Strategy
```
feat(ci): add container image build and push to GitHub Container Registry
feat(ci): implement semantic versioning tags for releases
chore(security): add Cosign image signing to release pipeline
```

### 12. Difficulty
5/10

### 13. Estimated Time
4–6 hours

---

## Phase 39: Staging Environment Setup

### 1. Phase Title
Pre-Production Validation Environment

### 2. Objective
Create a staging environment that mirrors production configuration for safe validation of changes before production deployment.

### 3. Background Theory
**Staging environments** replicate production infrastructure with anonymized data. **Infrastructure as Code (IaC)** ensures staging and production are identical. **Feature flags** allow testing new features in staging without affecting production. **Data anonymization** protects privacy while maintaining statistical properties.

**Study:**
- Terraform workspaces (staging vs. production)
- Render.com staging environments
- Feature flag systems (LaunchDarkly, Unleash, or simple env vars)
- Database anonymization techniques

### 4. Learning Outcomes
- Staging environment design
- Infrastructure parity
- Feature flag implementation
- Data anonymization

### 5. Current Problems Being Solved
- No staging environment mentioned
- No safe place to validate deployments
- Production deployment is risky without pre-validation

### 6. Implementation Tasks
1. Create `docker-compose.staging.yml` with production-like settings
2. Add `configs/staging/` with staging-specific configuration
3. Implement feature flags: `FEATURE_NEW_CLASSIFIER=true` in staging
4. Add staging database seeding with anonymized benchmark data
5. Document staging setup in `docs/deployment/staging.md`
6. Add staging deployment to CI (deploy on merge to `develop` branch)
7. Add smoke tests that run against staging after deployment

### 7. Files to Modify
- New: `docker-compose.staging.yml`
- New: `configs/staging/`
- New: `apps/api-server/src/core/feature_flags.py`
- `.github/workflows/staging-deploy.yml`
- New: `docs/deployment/staging.md`

### 8. Best Practices
- Staging should mirror production as closely as possible
- Use separate database instances (never share prod DB with staging)
- Feature flags should be simple (env vars) at first, then migrate to a service
- Smoke tests should verify: health endpoints, one synthetic incident, one approval flow

### 9. Validation Checklist
- [ ] Staging environment boots with `docker-compose -f docker-compose.staging.yml up`
- [ ] Smoke tests pass against staging
- [ ] Feature flags can be toggled without redeployment
- [ ] Staging database contains only anonymized data
- [ ] CI deploys to staging automatically on `develop` branch merge

### 10. Expected Deliverables
- Staging Docker Compose
- Staging configuration
- Feature flag system
- Smoke tests
- Staging deployment workflow

### 11. Suggested Commit Strategy
```
feat(staging): add docker-compose.staging.yml and configuration
feat(flags): implement simple feature flag system
feat(ci): add automatic staging deployment and smoke tests
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–8 hours

---

## Phase 40: Production Deployment Pipeline (GitOps)

### 1. Phase Title
GitOps-Based Production Delivery

### 2. Objective
Implement a GitOps deployment pipeline using ArgoCD or Flux, or a simpler GitHub Actions + Render/AWS approach, with automated rollbacks.

### 3. Background Theory
**GitOps** uses Git as the single source of truth for infrastructure and application configuration. **ArgoCD** (Kubernetes) or **Flux** continuously syncs cluster state with Git. **Blue-green deployment** runs two identical environments, switching traffic atomically. **Canary deployment** routes small percentages of traffic to the new version. **Automated rollback** triggers when error rates exceed thresholds.

**Study:**
- GitOps principles (Weaveworks)
- ArgoCD documentation
- Blue-green and canary deployment strategies
- AWS ECS deployment controller or Render deploy hooks

### 4. Learning Outcomes
- GitOps methodology
- Continuous delivery patterns
- Deployment strategies (blue-green, canary)
- Automated rollback implementation

### 5. Current Problems Being Solved
- README states: *"Not yet implemented: production deployment pipeline"*
- `infrastructure/render.yaml` exists but no deployment automation
- No rollback strategy

### 6. Implementation Tasks
1. Choose deployment target: Render, AWS ECS, or Kubernetes
2. Implement GitHub Actions workflow for production deployment
3. Add deployment health checks: verify `/health` returns 200 for 5 minutes
4. Add automated rollback: if health checks fail, revert to previous image
5. Add deployment notifications: Slack webhook on success/failure
6. Document deployment runbook in `docs/deployment/production.md`
7. Add deployment metrics: lead time, deployment frequency, failure rate

### 7. Files to Modify
- `.github/workflows/deploy.yml`
- `infrastructure/render.yaml` (update for production)
- New: `docs/deployment/production.md`
- New: `scripts/health_check.sh`

### 8. Best Practices
- Never deploy without health check validation
- Use semantic versioning for releases, not Git SHAs, in production
- Keep previous 3 versions available for instant rollback
- Document manual rollback procedure as fallback

### 9. Validation Checklist
- [ ] Merge to `main` triggers production deployment
- [ ] Health checks pass for 5 minutes before declaring success
- [ ] Failed deployment automatically rolls back within 10 minutes
- [ ] Deployment notification received in Slack
- [ ] Manual rollback procedure documented and tested

### 10. Expected Deliverables
- Production deployment workflow
- Health check validation
- Automated rollback
- Deployment notifications
- Production runbook

### 11. Suggested Commit Strategy
```
feat(deploy): implement GitOps production deployment pipeline
feat(deploy): add automated health check validation and rollback
feat(observability): add deployment metrics and Slack notifications
```

### 12. Difficulty
8/10

### 13. Estimated Time
10–14 hours

---

## Phase 41: Infrastructure-as-Code (Terraform/K8s)

### 1. Phase Title
Declarative Infrastructure Management

### 2. Objective
Populate the empty `infrastructure/terraform/` and `infrastructure/kubernetes/` directories with production-ready IaC.

### 3. Background Theory
**Terraform** manages cloud resources declaratively. **Kubernetes** orchestrates containerized applications. **Helm** packages Kubernetes applications. **State management** in Terraform requires remote backends (S3, Terraform Cloud) for team collaboration. **Modules** promote DRY infrastructure code.

**Study:**
- Terraform documentation (HCL syntax, providers, modules)
- Kubernetes basics (Pods, Services, Deployments, Ingress)
- Helm chart development
- Terraform Cloud or S3 backend

### 4. Learning Outcomes
- Terraform HCL
- Kubernetes resource definitions
- Helm chart authoring
- Remote state management

### 5. Current Problems Being Solved
- `infrastructure/kubernetes/` and `infrastructure/terraform/` are empty
- No declarative infrastructure
- Manual infrastructure setup is error-prone

### 6. Implementation Tasks
1. Create Terraform module for: VPC, EKS/ECS cluster, RDS PostgreSQL, ElastiCache Redis
2. Create Kubernetes manifests: Deployment, Service, Ingress, ConfigMap, Secret
3. Create Helm chart for SentinelOps application
4. Configure Terraform remote backend (S3 + DynamoDB or Terraform Cloud)
5. Add Terraform validation and plan to CI
6. Document infrastructure architecture in `docs/infrastructure/architecture.md`
7. Add cost estimation with `infracost` (optional but impressive)

### 7. Files to Modify
- New: `infrastructure/terraform/main.tf`
- New: `infrastructure/terraform/variables.tf`
- New: `infrastructure/terraform/outputs.tf`
- New: `infrastructure/kubernetes/deployment.yaml`
- New: `infrastructure/kubernetes/service.yaml`
- New: `infrastructure/kubernetes/ingress.yaml`
- New: `infrastructure/helm/Chart.yaml`
- New: `infrastructure/helm/values.yaml`

### 8. Best Practices
- Never commit Terraform state files (use remote backend)
- Use Terraform modules for reusable components
- Kubernetes Secrets should reference external secret management (AWS Secrets Manager, Vault)
- Tag all resources with environment, owner, and cost-center

### 9. Validation Checklist
- [ ] `terraform plan` shows expected changes
- [ ] `terraform apply` creates working infrastructure
- [ ] Kubernetes manifests apply without errors
- [ ] Helm chart installs successfully
- [ ] Remote state backend is configured and accessible

### 10. Expected Deliverables
- Terraform modules
- Kubernetes manifests
- Helm chart
- Remote state configuration
- Infrastructure documentation

### 11. Suggested Commit Strategy
```
feat(infra): add Terraform modules for AWS infrastructure
feat(k8s): add Kubernetes manifests for api-server and workers
feat(helm): create Helm chart for SentinelOps deployment
```

### 12. Difficulty
9/10

### 13. Estimated Time
14–20 hours

---

## Phase 42: Monitoring & Alerting Stack

### 1. Phase Title
Production Observability & Alerting

### 2. Objective
Configure Prometheus alerts, Grafana dashboards, and PagerDuty integration for production monitoring.

### 3. Background Theory
**The Four Golden Signals** (latency, traffic, errors, saturation) are the minimum metrics for any service. **SLIs** (Service Level Indicators) define what to measure. **SLOs** (Service Level Objectives) define targets. **Alerting rules** should be actionable, not noisy. **On-call rotations** ensure human response to alerts.

**Study:**
- Google SRE Book: "Monitoring Distributed Systems"
- Prometheus alerting rules documentation
- Grafana dashboard best practices
- PagerDuty integration guide

### 4. Learning Outcomes
- The Four Golden Signals
- SLI/SLO definition
- Alerting rule design
- On-call process design

### 5. Current Problems Being Solved
- Prometheus and Grafana are configured for local dev but not production alerting
- No evidence of production alerting rules
- No SLO definitions

### 6. Implementation Tasks
1. Define SLIs: classification latency, incident processing success rate, system availability
2. Define SLOs: 99.9% availability, <5s p99 classification latency
3. Create Prometheus alerting rules: `HighErrorRate`, `HighLatency`, `ProviderDown`
4. Create Grafana dashboards: Overview, Incident Pipeline, Provider Health, Evaluation Metrics
5. Add PagerDuty integration for CRITICAL alerts
6. Add alert routing: warning → Slack, critical → PagerDuty
7. Document runbook for each alert in `docs/runbooks/alerts/`
8. Add synthetic monitoring: periodic health check from external source

### 7. Files to Modify
- `infrastructure/docker/prometheus/prometheus.yml`
- New: `infrastructure/docker/prometheus/alerts.yml`
- New: `infrastructure/docker/grafana/dashboards/sentinelops.json`
- `apps/api-server/src/observability/metrics.py` (add application metrics)

### 8. Best Practices
- Alerts should be actionable (include runbook link)
- Use `for: 5m` to prevent flapping alerts
- Dashboards should show trends, not just current values
- Synthetic monitoring catches issues before users do

### 9. Validation Checklist
- [ ] Prometheus alerts fire when error rate > 1%
- [ ] Grafana dashboard shows all Four Golden Signals
- [ ] PagerDuty receives alert when provider is down for >5 minutes
- [ ] Synthetic monitoring reports availability every minute
- [ ] Alert runbooks are accessible from alert notification

### 10. Expected Deliverables
- Prometheus alerting rules
- Grafana dashboards
- PagerDuty integration
- Synthetic monitoring
- Alert runbooks

### 11. Suggested Commit Strategy
```
feat(monitoring): add Prometheus alerting rules for SLOs
feat(monitoring): create Grafana dashboards for incident pipeline
feat(alerts): integrate PagerDuty for critical alert routing
```

### 12. Difficulty
6/10

### 13. Estimated Time
6–10 hours

---

## Phase 43: Structured Logging & Correlation IDs

### 1. Phase Title
Traceable Log Management

### 2. Objective
Implement structured logging (JSON) with correlation IDs that propagate across API, Celery, and LangGraph boundaries.

### 3. Background Theory
**Structured logging** outputs JSON instead of plain text, enabling automated parsing and querying. **Correlation IDs** (trace IDs) link all log entries for a single request across services. **Log aggregation** (Loki, ELK, Splunk) requires structured logs for efficient querying. **Log levels** should be used consistently: DEBUG (development), INFO (normal operations), WARNING (degraded), ERROR (failure), CRITICAL (system down).

**Study:**
- Python `structlog` documentation
- OpenTelemetry logging specification
- Correlation ID propagation patterns
- Loki query syntax for structured logs

### 4. Learning Outcomes
- Structured logging implementation
- Correlation ID propagation
- Log level discipline
- Cross-service tracing

### 5. Current Problems Being Solved
- Logger configuration copied in multiple services
- No evidence of correlation ID propagation
- Inconsistent log levels
- Sensitive data may be logged (need audit)

### 6. Implementation Tasks
1. Replace all `logging.getLogger(__name__)` with `structlog` configuration
2. Add correlation ID middleware: generate UUID on API request, propagate to Celery tasks
3. Add correlation ID to LangGraph state and checkpoint metadata
4. Audit all log statements for sensitive data (remove passwords, tokens, API keys)
5. Add log format configuration: JSON in production, pretty in development
6. Add log sampling for high-volume endpoints (1% of health checks)
7. Document logging standards in `docs/contributing/logging.md`

### 7. Files to Modify
- `apps/api-server/src/utils/logger.py` (rewrite with structlog)
- `apps/api-server/src/api/middleware/correlation_id.py` (new)
- `apps/api-server/src/workers/celery_app.py` (propagate correlation ID)
- `apps/api-server/src/orchestration/graph.py` (add to state)
- All service files (audit log statements)

### 8. Best Practices
- Never log PII, passwords, or tokens
- Use `bind()` to add context (user_id, incident_id) to log entries
- Correlation IDs should propagate through message queues (Celery headers)
- Structured logs should include: timestamp, level, message, correlation_id, source_file

### 9. Validation Checklist
- [ ] All logs are JSON in production mode
- [ ] Correlation ID appears in API, Celery, and graph logs for same incident
- [ ] No sensitive data in logs (audit with `grep -i password\|token\|secret`)
- [ ] Loki query ` {correlation_id="abc"} ` returns all related logs
- [ ] Log levels are consistent across modules

### 10. Expected Deliverables
- structlog configuration
- Correlation ID middleware
- Celery propagation
- Log audit report
- Logging standards

### 11. Suggested Commit Strategy
```
feat(logging): implement structured JSON logging with structlog
feat(tracing): add correlation ID propagation across API and Celery
feat(security): audit and sanitize all log statements
```

### 12. Difficulty
5/10

### 13. Estimated Time
6–8 hours

---

## Phase 44: Distributed Tracing (Tempo Integration)

### 1. Phase Title
End-to-End Request Tracing

### 2. Objective
Integrate OpenTelemetry tracing with Grafana Tempo to visualize request flows across API, Celery, and LangGraph.

### 3. Background Theory
**Distributed tracing** follows a request through all services it touches. **Spans** represent individual operations. **Traces** are trees of spans. **OpenTelemetry** is the CNCF standard for observability (metrics, logs, traces). **Grafana Tempo** is a cost-effective trace storage backend. **Trace context propagation** (W3C standard) ensures spans are linked across service boundaries.

**Study:**
- OpenTelemetry Python documentation
- W3C Trace Context specification
- Grafana Tempo documentation
- Jaeger vs. Tempo comparison

### 4. Learning Outcomes
- OpenTelemetry instrumentation
- Span creation and context propagation
- Trace visualization
- Performance bottleneck identification

### 5. Current Problems Being Solved
- Tempo is configured but no evidence of application-level tracing
- No visibility into LangGraph execution time per node
- No visibility into Celery task latency

### 6. Implementation Tasks
1. Add `opentelemetry-api` and `opentelemetry-sdk` to dependencies
2. Instrument FastAPI with OpenTelemetry auto-instrumentation
3. Add manual spans for LangGraph nodes: `router`, `evidence_collection`, `root_cause`
4. Add manual spans for Celery tasks
5. Configure OTLP exporter to send traces to Tempo
6. Add trace ID to API responses (`X-Trace-Id` header)
7. Create Grafana dashboard for trace analysis
8. Document tracing setup in `docs/observability/tracing.md`

### 7. Files to Modify
- `apps/api-server/src/main.py` (add OTel instrumentation)
- `apps/api-server/src/orchestration/graph.py` (add spans)
- `apps/api-server/src/workers/celery_app.py` (add spans)
- `infrastructure/docker/tempo/tempo.yaml`
- `infrastructure/docker/grafana/datasources.yml`

### 8. Best Practices
- Use auto-instrumentation for frameworks (FastAPI, SQLAlchemy, Redis)
- Use manual spans for business logic (LangGraph nodes)
- Add attributes to spans (incident_id, user_id) for filtering
- Sample traces in production (1-10%) to reduce storage cost

### 9. Validation Checklist
- [ ] FastAPI auto-instrumentation creates spans for all requests
- [ ] LangGraph node spans appear in Tempo
- [ ] Celery task spans link to parent API request
- [ ] Grafana can display trace timeline
- [ ] `X-Trace-Id` header present in all API responses

### 10. Expected Deliverables
- OpenTelemetry instrumentation
- Tempo integration
- Trace visualization dashboard
- Tracing documentation

### 11. Suggested Commit Strategy
```
feat(tracing): add OpenTelemetry auto-instrumentation to FastAPI
feat(tracing): instrument LangGraph nodes with manual spans
feat(tracing): configure OTLP exporter and Grafana Tempo datasource
```

### 12. Difficulty
7/10

### 13. Estimated Time
8–12 hours

---

## Phase 45: Health Checks & Readiness Probes

### 1. Phase Title
Production Health Verification

### 2. Objective
Implement comprehensive health, readiness, and liveness probes for Kubernetes and load balancer integration.

### 3. Background Theory
**Liveness probes** tell Kubernetes whether to restart a container. **Readiness probes** tell Kubernetes whether to send traffic to a container. **Startup probes** protect slow-starting containers from premature liveness checks. **Deep health checks** verify dependencies (DB, Redis, LLM provider) rather than just returning 200.

**Study:**
- Kubernetes probe documentation
- Health check patterns (Microservices Patterns by Chris Richardson)
- FastAPI health check libraries

### 4. Learning Outcomes
- Probe types and purposes
- Deep health check implementation
- Kubernetes lifecycle management
- Dependency verification

### 5. Current Problems Being Solved
- Basic `/health` endpoint exists but may be shallow
- No readiness probe for Celery workers
- No evidence of startup probe for slow LLM connections

### 6. Implementation Tasks
1. Implement `/health/live` (liveness): always 200 if process is running
2. Implement `/health/ready` (readiness): 200 only if DB, Redis, Qdrant are reachable
3. Implement `/health/deep` (deep check): verifies LLM provider, checkpoint DB, and can process a synthetic incident
4. Add health checks to Celery workers: heartbeat and queue depth
5. Add startup probe: wait for LangGraph compilation before marking ready
6. Update Kubernetes manifests with probe configurations
7. Document health endpoint contract in `docs/api/health.md`

### 7. Files to Modify
- `apps/api-server/src/api/routes/health.py`
- `apps/api-server/src/workers/celery_app.py` (health check task)
- `infrastructure/kubernetes/deployment.yaml` (probe config)
- `docker-compose.yml` (health check config)

### 8. Best Practices
- Liveness should be cheap (<10ms)
- Readiness should check all required dependencies
- Deep health checks should run synthetic transactions
- Never use deep checks for load balancer health (too expensive)

### 9. Validation Checklist
- [ ] `/health/live` returns 200 immediately
- [ ] `/health/ready` returns 503 if PostgreSQL is down
- [ ] `/health/deep` returns 200 after processing synthetic incident
- [ ] Kubernetes restarts pod if liveness fails for 30 seconds
- [ ] Kubernetes stops traffic if readiness fails

### 10. Expected Deliverables
- Multi-level health endpoints
- Celery worker health checks
- Kubernetes probe configuration
- Health check documentation

### 11. Suggested Commit Strategy
```
feat(health): implement liveness, readiness, and deep health checks
feat(k8s): add probe configurations to deployment manifests
docs(api): document health endpoint contract and usage
```

### 12. Difficulty
5/10

### 13. Estimated Time
4–6 hours

---

## Phase 46: Operational Runbooks & SOPs

### 1. Phase Title
Operational Documentation

### 2. Objective
Create standard operating procedures for common operational scenarios: deployment, incident response, rollback, and data recovery.

### 3. Background Theory
**Runbooks** are step-by-step procedures for operational tasks. **SOPs** (Standard Operating Procedures) ensure consistency and reduce cognitive load during incidents. **Blameless postmortems** focus on system improvements, not personal fault. **Checklists** (like aviation pre-flight) prevent human error.

**Study:**
- Google SRE Book: "Managing Incidents" and "Postmortem Culture"
- "The Checklist Manifesto" by Atul Gawande
- PagerDuty incident response documentation

### 4. Learning Outcomes
- Runbook authoring
- Incident response procedures
- Blameless postmortem facilitation
- Operational excellence

### 5. Current Problems Being Solved
- Runbooks exist but may be incomplete (`docs/runbooks/oncall-guide.md`)
- No deployment runbook
- No data recovery procedures
- No incident response SOP for the platform itself

### 6. Implementation Tasks
1. Create `docs/runbooks/deployment.md`: step-by-step deployment procedure
2. Create `docs/runbooks/rollback.md`: how to rollback a bad deployment
3. Create `docs/runbooks/data-recovery.md`: how to restore from checkpoint DB backup
4. Create `docs/runbooks/provider-outage.md`: what to do when all LLM providers fail
5. Create `docs/runbooks/alert-storm.md`: how to handle webhook overload
6. Create `docs/runbooks/security-incident.md`: breach response procedure
7. Add runbook links to all alert notifications
8. Create `docs/runbooks/README.md` with runbook index

### 7. Files to Modify
- New: `docs/runbooks/deployment.md`
- New: `docs/runbooks/rollback.md`
- New: `docs/runbooks/data-recovery.md`
- New: `docs/runbooks/provider-outage.md`
- New: `docs/runbooks/alert-storm.md`
- New: `docs/runbooks/security-incident.md`
- Update: `docs/runbooks/oncall-guide.md`

### 8. Best Practices
- Runbooks should be tested (dry-run) quarterly
- Include exact commands, not vague instructions
- Include rollback steps for every mutating operation
- Assume the reader is tired and stressed (incident response)

### 9. Validation Checklist
- [ ] Each runbook can be followed by someone who didn't write it
- [ ] Deployment runbook has been tested at least once
- [ ] Rollback runbook has been tested at least once
- [ ] Alert notifications include direct links to relevant runbooks
- [ ] Runbook index is up to date

### 10. Expected Deliverables
- 7 operational runbooks
- Tested deployment and rollback procedures
- Alert-to-runbook linking
- Runbook index

### 11. Suggested Commit Strategy
```
docs(runbooks): add deployment, rollback, and data recovery procedures
docs(runbooks): add provider outage and alert storm response guides
docs(runbooks): add security incident response procedure
```

### 12. Difficulty
3/10

### 13. Estimated Time
4–6 hours

---

## Phase 47: Semantic Versioning & Release Process

### 1. Phase Title
Professional Release Management

### 2. Objective
Implement semantic versioning, automated changelog generation, and a documented release process.

### 3. Background Theory
**Semantic Versioning** (SemVer) uses `MAJOR.MINOR.PATCH` where: MAJOR = breaking changes, MINOR = new features (backward compatible), PATCH = bug fixes. **Changelog generation** from Conventional Commits is automated with tools like `git-cliff` or `semantic-release`. **Release notes** communicate changes to users and operators.

**Study:**
- Semantic Versioning 2.0.0 specification
- `git-cliff` or `semantic-release` documentation
- GitHub Releases documentation

### 4. Learning Outcomes
- Versioning strategy
- Automated changelog generation
- Release note authoring
- Git tag management

### 5. Current Problems Being Solved
- No release tags exist
- No CHANGELOG.md
- No release process

### 6. Implementation Tasks
1. Add `git-cliff` or `semantic-release` configuration
2. Create `.github/workflows/release.yml` that triggers on version tag push
3. Generate changelog from Conventional Commits
4. Create GitHub Release with changelog and asset links
5. Attach SBOM to release
6. Document release process in `docs/contributing/releases.md`
7. Create first official release: `v0.2.0` (significant improvements from v0.1.0-alpha.1)

### 7. Files to Modify
- New: `cliff.toml` or `.releaserc`
- New: `.github/workflows/release.yml`
- `CHANGELOG.md` (auto-generated)
- `README.md` (add version badge)

### 8. Best Practices
- Always tag releases with annotated tags (`git tag -a v1.0.0 -m "Release v1.0.0"`)
- Include migration guides for breaking changes
- Sign releases with GPG or Sigstore
- Never force-push tags

### 9. Validation Checklist
- [ ] `git tag -l` shows `v0.2.0`
- [ ] GitHub Release page has changelog
- [ ] Container image tagged with `v0.2.0` exists in registry
- [ ] CHANGELOG is auto-generated and accurate
- [ ] Release process is documented and reproducible

### 10. Expected Deliverables
- Automated release workflow
- CHANGELOG.md
- GitHub Release with assets
- Release process documentation

### 11. Suggested Commit Strategy
```
chore(release): add git-cliff configuration for changelog generation
chore(ci): add release workflow triggered by version tags
chore(release): create v0.2.0 release with changelog
```

### 12. Difficulty
3/10

### 13. Estimated Time
3–4 hours

---

## Phase 48: Contributor Onboarding & Templates

### 1. Phase Title
Community-Friendly Development Environment

### 2. Objective
Create a frictionless contributor experience with devcontainer support, good first issues, and clear contribution guidelines.

### 3. Background Theory
**Devcontainers** (VS Code Remote Containers) provide consistent development environments. **Good first issues** are bugs/features tagged for newcomers. **CONTRIBUTING.md** should answer: how to set up, how to test, how to submit. **Code of Conduct** establishes community norms.

**Study:**
- GitHub Docs: "Setting guidelines for repository contributors"
- VS Code Devcontainers documentation
- "Producing Open Source Software" by Karl Fogel

### 4. Learning Outcomes
- Devcontainer configuration
- Community building
- Contributor experience design
- Open-source governance

### 5. Current Problems Being Solved
- `CONTRIBUTING.md` exists but quality unknown
- No devcontainer support
- No "good first issue" labels
- No Code of Conduct

### 6. Implementation Tasks
1. Add `.devcontainer/devcontainer.json` with Docker Compose setup
2. Update `CONTRIBUTING.md` with: setup steps, testing commands, PR checklist
3. Add `CODE_OF_CONDUCT.md` (Contributor Covenant standard)
4. Create GitHub labels: `good first issue`, `help wanted`, `bug`, `enhancement`
5. Add `docs/contributing/architecture.md` with high-level code walkthrough
6. Create 3 "good first issues" in GitHub (real but small tasks)
7. Add Makefile target `make dev-setup` that installs pre-commit hooks and dev dependencies

### 7. Files to Modify
- Update: `CONTRIBUTING.md`
- New: `CODE_OF_CONDUCT.md`
- New: `.devcontainer/devcontainer.json`
- New: `.devcontainer/docker-compose.yml`
- New: `docs/contributing/architecture.md`
- `Makefile`

### 8. Best Practices
- Devcontainer should boot the full stack in <5 minutes
- CONTRIBUTING.md should include troubleshooting section
- Good first issues should be completable in <2 hours
- Code of Conduct should include enforcement contact

### 9. Validation Checklist
- [ ] Devcontainer boots and runs tests successfully
- [ ] New contributor can follow CONTRIBUTING.md without asking questions
- [ ] 3 good first issues exist and are appropriately labeled
- [ ] Code of Conduct is visible in repository

### 10. Expected Deliverables
- Devcontainer configuration
- Updated CONTRIBUTING.md
- CODE_OF_CONDUCT.md
- Good first issues
- Architecture walkthrough

### 11. Suggested Commit Strategy
```
docs(contributing): add devcontainer configuration and setup guide
docs(community): add CODE_OF_CONDUCT and good first issues
chore(make): add dev-setup target for new contributors
```

### 12. Difficulty
3/10

### 13. Estimated Time
3–4 hours

---

## Phase 49: Community Engagement & Issue Management

### 1. Phase Title
Open Source Community Building

### 2. Objective
Actively engage with the open-source community by responding to issues, creating discussions, and seeking external feedback.

### 3. Background Theory
**Bus factor** measures project risk if key people leave. A project with bus factor 1 (solo developer) is fragile. **Community contributions** improve code quality through diverse perspectives. **Issue triage** categorizes and prioritizes feedback. **RFCs** (Request for Comments) gather community input on major changes.

**Study:**
- "The Art of Community" by Jono Bacon
- GitHub Discussions documentation
- Issue triage best practices

### 4. Learning Outcomes
- Community management
- Issue triage
- RFC process
- Bus factor reduction

### 5. Current Problems Being Solved
- Zero open issues, zero PRs, zero discussions
- Bus factor of 1
- No external validation of design decisions

### 6. Implementation Tasks
1. Enable GitHub Discussions for the repository
2. Create discussion categories: Q&A, Ideas, Show and Tell
3. Post an RFC for major upcoming change (e.g., learned causality)
4. Actively seek feedback on Reddit (r/devops, r/MachineLearning), Hacker News, or Twitter
5. Respond to all issues within 48 hours
6. Create a public roadmap using GitHub Projects
7. Add `FUNDING.yml` if seeking sponsorship (optional)
8. Write a blog post about the project architecture and lessons learned

### 7. Files to Modify
- GitHub Settings: Enable Discussions
- New: `.github/DISCUSSION_TEMPLATE/`
- New: `docs/roadmap.md`
- New: `.github/FUNDING.yml` (optional)

### 8. Best Practices
- Be respectful and prompt in all interactions
- Close issues with explanation, not silently
- Credit contributors in release notes
- Don't over-promise on timelines

### 9. Validation Checklist
- [ ] GitHub Discussions has at least 3 active threads
- [ ] At least 1 external contributor has opened an issue or PR
- [ ] RFC has received at least 2 external comments
- [ ] Public roadmap is visible and updated

### 10. Expected Deliverables
- Active GitHub Discussions
- RFC document
- Public roadmap
- Community engagement metrics

### 11. Suggested Commit Strategy
```
docs(community): enable discussions and add RFC template
docs(roadmap): publish public roadmap and seek feedback
```

### 12. Difficulty
2/10

### 13. Estimated Time
2–3 hours (ongoing effort)

---

## Phase 50: Final Portfolio Polish & Presentation

### 1. Phase Title
Recruiter-Ready Project Presentation

### 2. Objective
Create a compelling narrative around the project that demonstrates engineering maturity, systems thinking, and production experience.

### 3. Background Theory
**Portfolio presentation** is storytelling with evidence. Recruiters scan for: problem statement, technical depth, measurable outcomes, and production experience. **The STAR method** (Situation, Task, Action, Result) structures project descriptions. **Architecture decision records** demonstrate senior thinking. **Metrics** prove impact.

**Study:**
- "Cracking the Coding Interview" by Gayle Laakmann McDowell (project presentation section)
- Tech resume best practices (e.g., Jordan Cutler's guides)
- System design interview frameworks

### 4. Learning Outcomes
- Technical storytelling
- Portfolio presentation
- Resume project descriptions
- Interview preparation

### 5. Current Problems Being Solved
- Project has impressive scope but poor signal-to-noise ratio
- README is too long for recruiter scanning
- No concise "elevator pitch" version
- No evidence of production deployment

### 6. Implementation Tasks
1. Create one-page project summary: problem, solution, tech stack, my role, outcomes
2. Record a 5-minute demo video showing: incident ingestion → classification → root cause → approval → execution
3. Create architecture diagram showing before/after (current vs. improved)
4. Write a case study blog post: "How I improved root-cause accuracy from 8.2% to 65%"
5. Update LinkedIn/GitHub profile with project highlights
6. Prepare interview talking points:
   - "What was the hardest technical challenge?" (Celery async boundary)
   - "How did you handle security?" (RBAC, secret management, scanning)
   - "How did you ensure reliability?" (checkpointing, circuit breakers, health checks)
7. Create a "System Design Interview" version of the architecture (simplified, 3-minute explanation)

### 7. Files to Modify
- New: `docs/portfolio/summary.md`
- New: `docs/portfolio/interview-prep.md`
- `README.md` (add demo video link)
- Personal: LinkedIn, GitHub profile, resume

### 8. Best Practices
- Lead with metrics (accuracy improvement, test coverage, deployment frequency)
- Be honest about limitations but emphasize learning
- Show the journey, not just the destination
- Practice explaining architecture in 3 minutes, 10 minutes, and 30 minutes

### 9. Validation Checklist
- [ ] Project summary fits on one page
- [ ] Demo video is under 5 minutes and shows end-to-end flow
- [ ] Architecture diagram is understandable to non-experts
- [ ] Interview prep includes answers to 10 common questions
- [ ] GitHub profile highlights the project effectively

### 10. Expected Deliverables
- One-page project summary
- Demo video
- Architecture before/after diagram
- Case study blog post
- Interview preparation document
- Updated professional profiles

### 11. Suggested Commit Strategy
```
docs(portfolio): add project summary and architecture evolution diagram
docs(portfolio): add interview preparation guide and talking points
```

### 12. Difficulty
2/10

### 13. Estimated Time
4–6 hours

---

## Key Milestones (Revisited)

### Milestone 1: MVP Recovery (Phases 1–15)
**Definition of Done:**
- Repository renamed and clean
- System completes live incident lifecycle without halting
- Durable checkpointing works across Celery workers
- Deterministic fallback classifier activates on provider failure
- Bootstrap state persists before LLM calls
- Basic security (secrets in env, no hardcoded credentials)

### Milestone 2: Algorithmic Competence (Phases 16–28)
**Definition of Done:**
- Root-cause accuracy >50% (up from 8.2%)
- ECE < 0.10 (calibration fixed)
- Confidence calibration learned, not hardcoded
- Rule-based causality works for 3 categories
- Unit test coverage >80%
- Integration tests against real infrastructure

### Milestone 3: Production Hardening (Phases 29–42)
**Definition of Done:**
- Deployed to staging with CI/CD
- Container images pinned, scanned, and signed
- Terraform/Kubernetes IaC committed
- Monitoring and alerting configured
- API rate limiting and input validation enforced
- Health checks and readiness probes active

### Milestone 4: Portfolio & Community (Phases 43–50)
**Definition of Done:**
- Structured logging and distributed tracing operational
- Operational runbooks tested
- Semantic versioning with automated releases
- Devcontainer and contributor onboarding ready
- Active community engagement (issues, discussions)
- Recruiter-ready presentation materials

---

## Recommended Implementation Order & Rationale

**Order:** Sequential phases 1–50, with parallel tracks where safe.

**Parallel Track A (Foundation):** Phases 1–5 can be done in any order, but 1 (rename) should be first.

**Parallel Track B (Security):** Phases 6–10 should follow Foundation. Phase 8 (Auth0) can be deferred if basic JWT is sufficient for MVP.

**Parallel Track C (Architecture Fix):** Phases 11–15 are **critical path** — nothing else matters if the system can't run. Do these first after security.

**Parallel Track D (Testing):** Phases 16–22 can begin once Architecture Fix is stable. Phase 16 (consolidation) should precede others.

**Parallel Track E (Core Algorithm):** Phases 23–28 are the **highest value** for portfolio. Start Phase 23 (decomposition) immediately after Architecture Fix.

**Parallel Track F (Telemetry):** Phases 29–32 depend on Architecture Fix but can run parallel to Core Algorithm.

**Parallel Track G (API/Frontend):** Phases 33–36 can run parallel to Telemetry.

**Parallel Track H (DevOps):** Phases 37–42 should follow API stabilization.

**Parallel Track I (Observability):** Phases 43–46 follow DevOps.

**Parallel Track J (Community):** Phases 47–50 are final polish.

**Rationale:** The critical path is: Foundation → Security → Architecture Fix → Core Algorithm. Everything else adds value but doesn't unblock the primary value proposition.

---

## Top 20 Concepts Mastered After 50 Phases

1. **Durable workflow orchestration** — LangGraph checkpointing, state machines, sagas
2. **Distributed task queues** — Celery patterns, async boundaries, gevent pools
3. **LLM provider resilience** — Circuit breakers, fallback chains, retry strategies
4. **Causal reasoning** — Rule-based systems, evidence grounding, abductive logic
5. **Confidence calibration** — ECE, Brier score, temperature scaling, isotonic regression
6. **Secret management** — 12-Factor App, Pydantic Settings, SecretStr, rotation
7. **RBAC & authorization** — Permission matrices, middleware enforcement, deny-by-default
8. **Schema-driven APIs** — Pydantic, OpenAPI, type-safe clients, contract testing
9. **Container supply chain** — Digest pinning, multi-stage builds, SBOMs, Trivy scanning
10. **Infrastructure as Code** — Terraform modules, Kubernetes manifests, Helm charts
11. **GitOps & CI/CD** — Automated deployment, health checks, rollback strategies
12. **Observability** — The Four Golden Signals, structured logging, distributed tracing
13. **Test pyramid** — Unit, integration, E2E, evaluation, testcontainers, coverage gates
14. **Rate limiting & DDoS protection** — Token bucket, Redis-backed limits, edge protection
15. **API versioning** — URL paths, deprecation policies, backward compatibility
16. **Type safety** — mypy strict, Protocols, Generics, runtime validation with Zod
17. **Reproducible builds** — Poetry lock files, Docker digests, pre-commit hooks
18. **Distributed state** — Redis state manager, distributed locks, pub/sub
19. **Production readiness** — Health probes, SLOs, alerting, runbooks, incident response
20. **Open-source governance** — SemVer, changelogs, community building, RFCs, bus factor

---

## Estimated Total Time

| Track | Phases | Hours | Weeks (15 hrs/wk) |
|-------|--------|-------|-------------------|
| Foundation | 1–5 | 20 | 1.5 |
| Security | 6–10 | 30 | 2.0 |
| Architecture Fix | 11–15 | 40 | 2.5 |
| Testing | 16–22 | 50 | 3.5 |
| Core Algorithm | 23–28 | 60 | 4.0 |
| Telemetry | 29–32 | 30 | 2.0 |
| API/Frontend | 33–36 | 30 | 2.0 |
| DevOps | 37–42 | 50 | 3.5 |
| Observability | 43–46 | 25 | 1.5 |
| Community | 47–50 | 15 | 1.0 |
| **Total** | **1–50** | **~370** | **~25 weeks** |

**Full-time equivalent:** ~9 weeks at 40 hrs/week.

**Note:** Phases can be parallelized. Realistic timeline with parallel tracks: **12–16 weeks part-time** or **6–8 weeks full-time**.

---

## Final Assessment

### How This Roadmap Elevates the Project

**Before:** A sophisticated prototype with 8.2% accuracy, blocked live lifecycle, in-memory checkpointing, and zero community.

**After:** A production-hardened AIOps platform with:
- **>50% root-cause accuracy** (6x improvement)
- **Durable, distributed orchestration** that survives worker crashes
- **Real telemetry grounding** from live Prometheus/Loki
- **Security posture** that passes enterprise audits (no hardcoded secrets, RBAC, scanning)
- **Operational excellence** with monitoring, alerting, runbooks, and SLOs
- **Professional open-source presence** with releases, documentation, and community

### How This Roadmap Elevates Your Engineering Skills

Completing these 50 phases transforms you from a **prototype builder** into a **production engineer**:

- **Systems Design:** You'll architect for failure (circuit breakers, fallbacks, checkpointing)
- **Security:** You'll think like an attacker (secret management, input validation, RBAC)
- **Reliability:** You'll design for observability (metrics, traces, structured logs)
- **Scale:** You'll understand distributed state, caching, and horizontal scaling
- **Quality:** You'll enforce code quality through automation (linting, types, coverage gates)
- **Community:** You'll learn to build software *with* others, not just *for* yourself

**Recruiter Impact:**
- **Google/Meta:** Demonstrates distributed systems and reliability engineering
- **Stripe:** Shows security-first thinking and API design rigor
- **OpenAI/Anthropic:** Proves AI systems engineering (calibration, uncertainty, evaluation)
- **Datadog:** Directly relevant observability and incident management experience

This roadmap is not just about fixing a repository. It's about **becoming the engineer who can build and operate systems that matter.**
