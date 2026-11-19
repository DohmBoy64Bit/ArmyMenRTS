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

Open [the local ledger](http://127.0.0.1:8000/). To deploy, push this repository to GitHub and choose **Settings → Pages → Source → GitHub Actions**. The included workflow publishes the static contents of `docs/`. Commit the regenerated snapshot and proof files when publishing new progress. Visitors can inspect the proof without installing the game.
