# Corporate portal — test knowledge
Authentication: integrate a corporate OIDC identity provider, use secure httpOnly session cookies and CSRF protection.
Roles / роли: Employee, Manager, Administrator. Enforce RBAC on every backend endpoint; default deny.
Audit / аудит: record actor, action, target, timestamp and outcome. Avoid storing tokens or passwords. Restrict audit reader permissions.
