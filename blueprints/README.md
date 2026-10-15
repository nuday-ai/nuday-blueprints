# Official blueprints (source)

One directory per official NuDay blueprint, each holding a `blueprint.yaml`:

```bash
uv run nuday blueprint init blueprints/<name> --name <name> --description "<one line>"
# or start from a working agent:
uv run nuday blueprint export --agent-id <id> -o blueprints/<name>
```

Add its text to `catalog/listings.json`. Open a pull request: CI builds the whole catalog with a
throwaway key. On merge it is signed and published automatically. To change a published
blueprint, also bump `metadata.version`.
