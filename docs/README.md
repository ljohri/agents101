# Documentation

Documentation for the **agents101** workflow-driven local agent stack.

## Start here

**New to the repo?** Read [How It All Fits Together](how-it-fits-together.md) first. It explains how A2A, MCP, local agents, workflows, OpenClaw, and NemoClaw connect in one mental model.

Then pick your path:

| If you want to… | Read |
|-----------------|------|
| Understand the system in one sitting | [how-it-fits-together.md](how-it-fits-together.md) |
| Follow the implementation roadmap | [build-plan.md](build-plan.md) |
| Go deep on a specific layer | [architecture/README.md](architecture/README.md) |
| Add a workflow, agent, or MCP server | [architecture/12-extension-cookbook.md](architecture/12-extension-cookbook.md) |
| Run and test locally | [../README.md](../README.md) |

## Architecture series

The [architecture/](architecture/) directory is a numbered reference (00–13). Each doc covers one concern: capabilities, workflows, MCP, A2A, storage, security, observability, OpenClaw, NemoClaw, and more.

Index: [architecture/README.md](architecture/README.md)

## Legacy

The original OpenClaw + NemoClaw + A2A design notes live in [legacy/openclaw_nemoclaw_a2a_cursor_implementation.md](legacy/openclaw_nemoclaw_a2a_cursor_implementation.md). That document is **superseded** by [build-plan.md](build-plan.md) and the architecture series.

## Doc drift

Fenced code blocks tagged with `file=<path>` in architecture docs must match the referenced file on disk. CI enforces this via `tests/test_docs_snippets.py`.
