# forever-db

A versioned dataset of every spell, item and piece of gear in WoW Forever, built from the game files, with the build/hotfix each entry last changed in. A searchable browser with build-to-build diffs will sit on top (planned; hosted on GitHub Pages).

Start with [AGENTS.md](AGENTS.md). Details: [data model](docs/data-model.md) · [update runbook](docs/update-runbook.md) · [known limitations](docs/known-limitations.md).

```sh
FOREVER_REPO=~/dev/forever scripts/scan.sh          # scan the local client and update data/
python3 -m unittest discover -s pipeline/tests      # tests
```

Current data: see `data/state.json`.
