# Orchestrating a matching batch

Keep one `python live_dashboard.py --push` process running during the batch. It mirrors lease changes to the local site and the public Pages branch, and refreshes the verified ledger after a reconstruction is integrated. Only the dispatcher launches workers.

Run `python workflow.py rules` and read its output when starting a batch, whenever a rules document changes, and after every three successful integrations. The integration command checks the refresh checkpoint. For each candidate use REA on the pinned target to corroborate its saved instruction observation, leased entry and function boundaries. The scheduler leases shortest eligible ranges first and resolves equal sizes by RVA.

Codex is the default project lead. Pi and OpenCode can follow this same procedure. Use one project lead per checkout. The SQLite scheduler leases disjoint assignments to up to ten configured workers. The lead owns public progress, shared headers, build changes and final integration.

1. Read AGENTS.md. Verify the pinned installation with `python workflow.py baseline`. Confirm the current tracked worktree is clean before starting a batch.
2. Run `python workflow.py seed` to register the ten curated assignments. For subsequent assignments inspect the executable with REA, record the evidence for both boundaries, then run `python workflow.py enqueue RVA SIZE NAME`. Use `--after JOB_ID` for a prerequisite. The RVA and size can be decimal or hexadecimal.
3. Run `python runners.py --config workers.local.json --check`, then the same command without `--check`. Use `workers.example.json` for the default ten Codex slots. The dispatcher claims jobs and renews leases. Inspect `python workflow.py status` for results.
4. For each submitted job, inspect its patch, source, build script and evidence. Confirm the compiler generates the candidate from the reconstructed behavior, all addresses are RVAs, and function boundaries match the assignment. Reject hardcoded output or builds that depend on a copy of the reference. Run `python workflow.py integrate JOB_ID` for each reviewed candidate. Integration restricts changes to the assigned directory, rebuilds all functions from the combined revision and fast-forwards only after comparison succeeds.
5. Leave an unresolved mismatch in review. Read its attempt log and vary a specific type, calling convention or compiler hypothesis before using `python workflow.py retry JOB_ID`. Keep repeated failures for human review. Re-run the dispatcher after prerequisites integrate.
6. Run `python workflow.py report` and inspect the ledger. Commit the new snapshot and evidence files. Summarize accepted bytes, the first remaining mismatch, unresolved dependencies and whether a complete linked executable exists.

Prefix shell commands with `rtk` on the configured Windows workstation. Keep analysis sessions isolated across workers and use the current REA tool catalog to select the native provider. Use the REA CLI if a worker's client lacks the MCP connection.
