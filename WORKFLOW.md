# Army Men RTS matching project

Follow [the operating rules](RULES.md) across all agent runtimes. REA supplies the target evidence for every function. Each worker receives the rules on every assignment. The lead reloads them at startup and after three integrations. Among eligible jobs, the scheduler grants an exclusive lease on the smallest function first, with equal sizes ordered by RVA.

## Target and definition of done

The baseline is the Steam x86 PE executable amrts.exe, 2,879,488 bytes, SHA-256 34c9cacfcd42a816a5a9e886fbe18ae69ca2b82bdb7ed95588772f3079777b59. Keep the reference installation read-only. Build in a separate directory. Completion requires a clean build from reconstructed inputs, equal file lengths and a successful whole-file binary comparison. Publish both digests and the build revision. Copying ranges from the reference into the output cannot earn matching credit.

## First milestone

Fingerprint PE sections, imports, entry point, debug records and compiler/linker clues. Record the basis for each toolchain hypothesis. Identify a bounded leaf function with a caller, recover a candidate implementation, compile it with a pinned toolchain and compare instruction bytes. Preserve the build command and first mismatch. Repeat from a fresh checkout before scaling dispatch. A function match does not establish a reproducible executable.

## Orchestrator and ten workers

Run one persistent scheduler with ten numbered worker slots. All ten can take function batches, so a stalled specialty cannot idle the pool. Schedule prerequisite jobs for toolchain experiments, shared types, data layout and link order. Reserve shared-header and linker changes for serialized integration. Each worker gets its own checkout and output directory.

Use a local SQLite queue. Each job identifies the target digest, base revision, RVA ranges, prerequisites, lease owner and lease expiry. Claim and renew leases transactionally. Store a unique attempt ID on every result. An expired attempt may retain its findings but cannot submit against a reassigned lease. A failed experiment records its flags and mismatch before retry. Stop repeatedly failing jobs for review.

Workers inspect a pinned target with REA, record addresses and evidence, edit assigned source and return a patch plus compiler invocation and comparison results. Isolate mutable REA sessions per worker or serialize access to a shared session. The orchestrator replays each patch against the integrated tree, checks previously verified ranges, and accepts only independently reproduced results.

## Runner contract

Use Codex as the default orchestrator and default worker. Put the queue and verifier outside the agent runtime. A worker adapter reads one versioned JSON job and writes a result containing attempt ID, base revision, patch location, evidence references, build log and disposition. Codex, Pi and OpenCode adapters implement the same contract. Any of the three can drive scheduler commands for claim, inspect, submit and status.

Configure runner, provider, model, endpoint and credential environment-variable name per slot. Leave model overrides optional. A direct model API adapter needs a local tool loop for scoped REA calls, source edits and builds. A text completion alone cannot complete a job. Keep API credentials in the local environment. Report unsupported provider capabilities before taking a lease.

## Public progress site

Generate a static snapshot from accepted results and deploy it to GitHub Pages using project-relative URLs. Lead with verified code bytes over the fixed executable-code denominator. Count the union of verified ranges once. Report discovered functions, matched functions and whole-file equality separately. Display unknown coverage explicitly until a denominator is established.

Use an olive field-manual cover, warm paper tables, ink-dark type and molded-plastic green for verified regions. Pair a condensed display face with monospaced RVAs. The main view contains a section map and searchable function ledger. Each function opens a stable detail link with its RVA, size, subsystem, match state, source revision and verification evidence. Provide text equivalents for map colors and keyboard access to every record. Export only public metadata and reconstructed-source links.
