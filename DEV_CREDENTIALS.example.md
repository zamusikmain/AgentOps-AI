# AgentOps AI — DEV CREDENTIALS public template

This file contains no real password, token or reset secret. Keep populated credentials only in DEV_CREDENTIALS.local.md.

## Browser accounts

Repeat for every actual account in each local/dev/test environment, including identical roles.

### Account

- Account ID:
- Email:
- Password: omitted from public template.
- Role: admin / operator / viewer
- Tenant:
- Status:
- Login URL:
- Environment:
- Purpose:
- Source fixture / seed:
- Login verification:
- Role verification:
- Persistent user or temporary fixture snapshot:

Passwords are salted scrypt hashes in SQLite. Browser sessions use opaque HttpOnly cookies and CSRF validation. Never place credentials in URLs or localStorage.

## API-only identities

- Identity ID:
- Tenant / role:
- Bearer credential: omitted from public template.
- Environment:
- Purpose:
- Authorization method: Authorization: Bearer (independent service credential).
- Verification:

Do not use API tokens as browser passwords. User disable/password change revokes browser sessions; independent API service credentials require separate explicit rotation.

## OAuth

List OAuth identities separately if introduced; never collect provider passwords.

## Protection / limitations

- DEV_CREDENTIALS.local.md excluded from Git/Docker/static assets/CI artifacts.
- .env unchanged.
- No production accounts or credentials.
- Temporary fixtures require their test runner and may regenerate user IDs.
- Record actual Git verification limitations if the project has no Git repository.
