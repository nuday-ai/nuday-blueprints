# NuDay Blueprints catalog

Official NuDay blueprints and reviewed partner blueprints, published as the **signed
marketplace index** every NuDay environment reads.

**To publish, merge a pull request.** That is the whole process: the Publish workflow packs and
signs every blueprint, counter-signs merged submissions, builds and signs the index, and
deploys it. It also re-signs every Monday, so the index never expires.

| Path | What it holds |
|---|---|
| `blueprints/<name>/` | Source of each official blueprint (`blueprint.yaml` plus resources) |
| `submissions/<partner>/` | Partner-signed packed files; merging one publishes it as reviewed |
| `catalog/listings.json` | Listing text: `{name: {title, description, tags, homepage}}` |
| `RELEASE_KID` | The release key id environments trust (nuday-manager `app/blueprints/release_keys.py`) |
| `scripts/publish.py` | Builds the whole signed site into `_site/` (what both workflows run) |

## Everyday tasks

| Task | How |
|---|---|
| Add an official blueprint | PR adding `blueprints/<name>/` (`uv run nuday blueprint init` or `export`) and its entry in `catalog/listings.json` |
| Change one | PR changing it **and** bumping `metadata.version` (CI refuses changed content under a live version) |
| Remove one | PR deleting its directory; the next publish drops the listing everywhere at their next refresh |
| Accept a partner blueprint | Review the PR against nuday-manager `docs/BLUEPRINT_REVIEW_CHECKLIST.md`, then merge |
| Publish right now | Actions > Publish > Run workflow |

CI builds every pull request exactly as Publish would, signed with a throwaway key, so a merged
PR publishes cleanly. Details and the one-time setup: [docs/PUBLISHING.md](docs/PUBLISHING.md).

## Pointing an environment at this catalog

Set `BLUEPRINT_CATALOG_URL` on the manager to
`https://nuday-ai.github.io/nuday-blueprints/v1/index.json` and allow the manager's outbound
HTTPS to that host. Environments check the signature, expiry and serial of the index, and each
file's hash and signatures again at install, so the hosting itself is not trusted.

**Never commit a private key.** `.gitignore` refuses `*.pem` and `*.key`.
