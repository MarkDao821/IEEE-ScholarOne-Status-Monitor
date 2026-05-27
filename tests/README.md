# Test Data Guidelines

Tests should use synthetic data only.

When adding or updating fixtures:

- Use fake manuscript IDs such as `DEMO-E-2026-04-0001`.
- Use fake titles such as `Example Manuscript Title for Parser Tests`.
- Use fake people such as `Example Author` or `Example Editor`.
- Use fake internal ScholarOne-like IDs such as `REX-PROD-DEMO-00000000-0000-0000-0000-000000000001`.
- Use `example.com` or `example.test` for email addresses and URLs.
- Do not paste real diagnostic HTML, screenshots, manuscript IDs, author names, paper titles, tokens, passwords, or account details.

If a bug requires a real page sample to reproduce, reduce it to the smallest synthetic fixture before committing.
