# forever-db

A versioned dataset of every spell, item and piece of gear in WoW Forever, built from the game files, with the build/hotfix each entry last changed in. A static website (`site/`, live at https://ericbtaylorjr.github.io/forever-db/) browses it: filters, history, side-by-side version compare, per-build change pages, and clear marking of content the game has not revealed yet ("encrypted").

Start with [AGENTS.md](AGENTS.md). Details: [website](site/README.md) · [discovery](docs/discovery.md) · [data model](docs/data-model.md) · [update runbook](docs/update-runbook.md) · [known limitations](docs/known-limitations.md).

```sh
FOREVER_REPO=~/dev/forever scripts/scan.sh --cdn    # scan the live build and update data/
python3 pipeline/builds.py check                    # is there a new build or hotfix?
python3 -m unittest discover -s pipeline/tests      # tests
```

`data/` updates itself via a scheduled GitHub Action (every 3 h; see the runbook). Current data: see `data/state.json`.
