# Partner submissions

A partner opens a pull request adding `submissions/<partner>/<name>-<version>.json`: a packed
blueprint signed with the partner's own publisher key:

```bash
nuday blueprint publish <dir or file> --key <partner key>.pem --publisher "<Partner name>" \
    -o submissions/<partner>/<name>-<version>.json
```

Do not edit a submitted file after opening the PR: the review covers exactly its content hash.
Reviewers follow nuday-manager `docs/BLUEPRINT_REVIEW_CHECKLIST.md`. **Merging the pull request
is the review**: the Publish workflow counter-signs it with the release key and lists it as
reviewed.
