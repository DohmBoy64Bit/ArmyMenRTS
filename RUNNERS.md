# Running the worker pool

From the repository root, authenticate the CLIs you plan to use and configure REA for those clients. Pi workers can use the pinned REA CLI through their shell tool. Each attempt must use a separate REA process or server whenever a tool changes the active target. The worker's prompt, tools and reference executable are local to the machine running the dispatcher. Selected remote providers receive the context their agent sends.

```powershell
Copy-Item workers.example.json workers.local.json
python runners.py --config workers.local.json --check
python runners.py --config workers.local.json
```

Use the same database path as the scheduler. The sample starts ten Codex slots. The check resolves the installed launchers and validates their configuration without making model requests. Dispatch drains the ready queue once. Add `--watch` to keep accepting jobs until interrupted. Reduce the length of `slots` to cap concurrent requests and change `timeout_seconds` to bound a single attempt. Each worker claims a job transactionally, gets a detached checkout at the job's exact commit, renews its lease, and records a candidate or diagnostic result.

## Mixed runners and model providers

Replace individual empty objects in the sample's `slots` array with any of these entries. Model names are illustrative. Use a model provided by your account or endpoint.

```json
[
  {"runner": "codex"},
  {"runner": "codex", "provider": "my-configured-provider", "model": "my-model"},
  {"runner": "pi", "provider": "anthropic", "model": "my-model"},
  {"runner": "opencode", "model": "my-provider/my-model"},
  {"runner": "api", "endpoint": "http://localhost:11434/v1", "model": "my-local-model"},
  {"runner": "api", "endpoint": "https://example.org/v1", "model": "my-model", "key_env": "WORKER_API_KEY"}
]
```

Codex uses `codex exec --sandbox workspace-write` and accepts a configured model provider name. Pi uses `pi --print --no-session`. OpenCode uses `opencode run` with its configured noninteractive permissions. API slots use Pi's tool loop with an attempt-local `models.json` and the OpenAI chat-completions protocol. Choose a model and endpoint that support tool calls. Credentials come from the named environment variable. API slots use a private Pi configuration, so have the REA CLI available to the shell for target inspection. Normal runner slots inherit the selected client's configured credentials, plugins and models.

## Reviewing a result

Each private attempt directory contains its checkout, combined CLI output in `worker.log`, and `result.json`. Successful attempts also have a Git commit and `candidate.patch`. The default location is `attempts/` beside the queue database. Use `--attempts PATH` for an alternate local directory. Keep this directory outside version control. Detached checkouts remain available for review.

Workers can change the assigned `reconstruction/<eight-digit-lowercase-rva>/` directory. Each result links a repository-relative `build.py`, `function.json`, reconstructed source and evidence. The dispatcher collects these changes into one commit at the pinned base and records its SHA for the independent verifier. A timeout, missing file, invalid manifest, or CLI failure sends the job to review. A worker whose lease expired cannot replace a newer attempt. The dispatcher never awards matching credit.

Codex, Pi and OpenCode can all act as orchestrator by invoking the same `workflow.py` and `runners.py` commands. The database, worktree and verification protocol are independent of the CLI that launched them.
