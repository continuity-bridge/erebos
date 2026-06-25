<!-- Migrated from Notion (Cognate Quarters, loose page) 2026-06-25 by Vector (Dom1).
     Source: https://app.notion.com/p/389c4ef87ccc81839f64df3f4c3a94a6 -->

# Erebos: Pipeline-Parallel Composite Nodule

**Purpose:** Extend nodule selection to *combine* under-spec'd nodes for models neither can run alone, rather than only choosing among whole-node candidates.

## Relationship to Use Case 9
Use Case 9 (Network Resource Leverage) solves selection: pick the single best-fitting whole node for a model. It does not solve the case where no single node fits but two or more together would.

This use case adds a new nodule *type* — a composite/virtual nodule — sitting one tier above plain selection. `select_nodule_for_model` gains a fallback: if no single node's VRAM covers the model, check whether a registered composite nodule covers it before failing or going to cloud.

## Topology (concrete instance)
```
Tailnet
 ├─ Node A: Laptop — Quadro P3000 (MXM), 6GB VRAM
 └─ Node B: Home server — GTX 1080, 8GB VRAM
    (Node B is reachable ONLY via tailnet — no LAN-segment or
     public access exists, even from the same physical network
     as Node A. This is a hard topology constraint, not a routing policy.)
```
Neither node alone covers a model requiring ~12GB+. Pipeline parallelism splits the model's layers across both: e.g. layers 1–N on Node A, N+1–end on Node B, with activations handed off over the tailnet between stages.

## What Pipeline Parallelism Actually Buys (and Doesn't)
- **Buys:** capacity — running a model too large for either card alone.
- **Does NOT buy:** speed, in the naive single-request case. Each node sits idle waiting for the other's activations (the classic pipeline "bubble"). Throughput only improves if multiple requests are in flight concurrently, filling the bubble with other work. For a single-user dev harness, capacity is the relevant win; don't market this as a speedup.

## Candidate Tooling
- **llama.cpp `--tensor-split`** — splits layers across multiple GPUs, weighting for mismatched VRAM sizes. Built for GPUs visible to one process/host, not two separate machines.
- **llama.cpp `rpc-server` (experimental RPC backend)** — purpose-built for distributing layers across *networked* machines. This is the better fit for the Node A / Node B topology, since the two GPUs are never visible to a single process.
- **Ollama multi-GPU split** — exists, but assumes all GPUs are visible to one process on one host. Not a fit here without the RPC backend underneath.

## Composite Nodule Config Shape (draft)
```yaml
nodules:
  pipeline-laptop-server:
    type: composite
    strategy: pipeline-parallel
    location: network          # see Privacy Aggregation below
    members:
      - node: ollama-laptop-p3000
        vram_gb: 6
        layer_range: "0-N"
      - node: ollama-server-1080
        vram_gb: 8
        layer_range: "N-end"
    transport: tailnet
    backend: llama.cpp-rpc
```

## Privacy Aggregation Rule
A composite nodule's privacy tier is the **minimum tier among its members**, not an independently chosen value. This matters once a composite nodule might span more than two legs:
- Two tailnet-only members → tier stays Network-Local, and in this concrete instance is structurally enforced (Node B has no path outside the tailnet, so misconfigured routing can't leak it to a wider tier).
- If a future third leg is ever a cloud-burst node, the *aggregate* tier must drop to Cloud even if the other two legs are network-local — the rule exists specifically to prevent "this composite *looks* network-only but actually contains a cloud leg" mistakes.

This rule should live in the same privacy-routing logic as `PrivacyPolicy.max_allowed_tier()`, applied to composite nodules before whole-node nodules are even considered.

## Open Questions
- Health-check semantics for a composite nodule: available only if *all* members report healthy, or degrade gracefully (smaller model on whichever single leg remains)?
- Where does the RPC backend's connection-loss behavior surface as a `ProviderError` subclass — does a mid-pipeline tailnet hiccup look like `ProviderConnectionError` or something new?
- Bubble-filling: worth queuing multiple smaller requests through the pipeline concurrently, or out of scope until there's an actual multi-request workload (v0.2 multi-session)?

---
**Created:** 2026-06-24
**By:** The Architect, drafted with Chatelaine (Dom4)
**Status:** Idea captured post-breakthrough (Claude-auth + 4-in-1 erebos POC session). Not yet implemented — sits behind HookExecutor wiring and current Claude-provider integration work.
