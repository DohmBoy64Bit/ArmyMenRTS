# Army Men RTS matching decompilation

All orchestrators and workers share the [operating rules](RULES.md). Run `python workflow.py rules` to load the current instructions and record the orchestrator checkpoint.

This project reconstructs the Steam x86 version of Army Men RTS from source. The first verified C++ function is an inferred nested-field accessor at RVA `0x4560`. The project includes ten additional REA-identified assignments and a static progress ledger.

## Verify the first match

Use Windows, Python 3.10+, Git and the x86 MSVC tools listed in [the pilot evidence](reconstruction/read_nested_word.md). The installation at `C:\Program Files (x86)\Steam\steamapps\common\Army Men RTS\amrts.exe` is the default reference. Set `AMRTS_TARGET` to the full executable path for another installation of the same build.

```powershell
rtk proxy python workflow.py baseline
rtk proxy python workflow.py report
rtk proxy python -m unittest -v
```

The verifier exports the current Git commit to a temporary directory, runs each function's builder, compares its output with the corresponding file-backed code range, and writes the ledger only after all comparisons pass. Commit changes to reconstruction inputs before verifying them. The code denominator is 2,523,677 bytes in the file-backed virtual extent of the PE code section. Run `compare-image PATH` through workflow.py to compare an independently built executable. When a full linker build exists, add `reconstruction/build_image.py --output PATH` to have the report reproduce and compare it.

## Run a batch

Start Codex, Pi or OpenCode in this checkout and ask it to follow [the orchestrator instructions](ORCHESTRATOR.md). The default pool has ten Codex workers. [Runner setup](RUNNERS.md) covers mixed pools, custom models, compatible API endpoints and local credentials. The initial queue is local and can be recreated on a new machine.

## View the ledger

```powershell
rtk proxy python -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Open [the local ledger](http://127.0.0.1:8000/) or the [public dashboard](https://dohmboy64bit.github.io/ArmyMenRTS/). The browser checks both snapshots every 15 seconds and on return to the tab. Ten slots show their currently leased functions.

Run one `python live_dashboard.py --push` process on the scheduler machine during a batch. It checks the SQLite queue every five seconds, refreshes verification when the reconstruction tree changes, and coalesces public updates to at most one push per minute. GitHub Pages serves the root of `gh-pages`. The publisher uses a separate Git checkout under `.army/pages`. Only the public dashboard, snapshots and linked proof are published there. Push source changes to `main` separately. Omit `--push` for local-only updates or add `--once` for one export. Restart the publisher after reboot.
