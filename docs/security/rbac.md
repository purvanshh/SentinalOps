# Role-Based Access Control (RBAC) Matrix

## Permissions mapping
| Role | Permissions |
| --- | --- |
| viewer | `incident:read`, `config:read` |
| operator | `incident:read`, `incident:write`, `approval:approve`, `approval:reject`, `execution:trigger` |
| admin | `*` (All permissions) |
