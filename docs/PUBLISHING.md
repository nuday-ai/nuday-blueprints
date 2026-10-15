# Publishing

Publishing is automatic. This page explains what the automation does and how to set it up once.

## What happens

**Pull request (CI workflow).** `scripts/publish.py --dry-run-key` builds the entire catalog
with a throwaway key: every blueprint validates, packs and signs; every submission validates and
counter-signs; the index builds, signs and verifies. It also compares against the live index and
fails when a name and version that is already published has different content.

**Merge to main, and every Monday (Publish workflow).** The same script runs with the real
release key from the `catalog-release` environment:

1. Each `blueprints/<name>/` is validated, packed and signed (`--expect-sha256` binds the
   signature to exactly that content).
2. Each `submissions/**/*.json` is validated and counter-signed. Merging its pull request is the
   review, which is why CODEOWNERS requires the platform team's approval.
3. The index is built with serial = the current Unix time (always higher than the last), a
   30-day expiry, signed, and verified from the output.
4. The output (`_site/`, public signed files only) is deployed to GitHub Pages.

The weekly run re-signs with a fresh 30-day expiry, so the index is never older than about a
week. If publishing breaks, there are three weeks to notice (GitHub emails on failed scheduled
runs) before environments stop listing the catalog.

Nothing is committed back to the repository; every publish rebuilds the site from source.

## One-time setup

1. **Pages:** Settings > Pages > Source: GitHub Actions.
2. **The release key:** Settings > Environments > New environment `catalog-release`.
   - Deployment branches and tags: **Selected branches**, add `main` only.
   - Add the secret `NUDAY_RELEASE_KEY`: the full text of the release key PEM, including the
     `BEGIN` and `END` lines.
   - Do not add required reviewers: the Monday re-sign must run unattended.
3. **Branch protection on main:** require pull requests, the CI check, and review from Code
   Owners (`.github/CODEOWNERS`; make sure the team it names exists).
4. **Optional:** a repository variable `CATALOG_URL` if the site is served elsewhere (a custom
   domain). It defaults to the GitHub Pages URL.

Then run Actions > Publish > Run workflow once, and check
`https://nuday-ai.github.io/nuday-blueprints/v1/index.json`.

## The key in CI: the trade-off

nuday-manager `docs/BLUEPRINT_RELEASE_KEY.md` was written for an offline key. Holding it in a
GitHub environment secret instead was decided on 2026-10-15 so that publishing needs no manual
steps. What protects it now:

- Only workflows running on `main` can read it (environment branch policy). Pull requests,
  including from forks, run CI with a throwaway key.
- Changes to `main` need a reviewed pull request and Code Owners' approval, so nobody can merge
  a workflow change that exfiltrates the key without review.
- The key is written to a 0600 file for one step and deleted.
- Anything signed is also verified by every environment: it is still the platform team's key,
  and a leak is handled as in `BLUEPRINT_RELEASE_KEY.md` "Compromise" (remove the kid from
  `release_keys.py`, deploy everywhere, new key, update the secret and `RELEASE_KID` here).

## Key rotation

Add the new key to nuday-manager `app/blueprints/release_keys.py` and deploy. Then change
`NUDAY_RELEASE_KEY` and `RELEASE_KID` here in one PR and run Publish. After every environment
has the new release, remove the old kid from `release_keys.py`.

## Air-gapped environments

Download `v1/index.json` and `v1/files/` from the site and run
`nuday blueprint catalog import --index index.json --files <dir>` there.
