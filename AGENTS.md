# Repository workflow

This is the active K-Beauty AI Support repository. Preserve the separate original archive; do not synchronize changes back into it.

## Engineering blocks

- Implement only the block currently authorized by the owner. Do not begin reranking, LLM integration or another technical block before its required acceptance.
- Preserve approved business data and frozen relevance labels unless the owner explicitly authorizes a change.
- Run checks appropriate to the change and report actual results. Distinguish local-client tests from real Qdrant Server integration.

## Git and publication

- The confirmed public remote is `https://github.com/KHABAR0611/k-beauty-ai-support.git`; the primary branch is `main`.
- After each completed and successfully tested engineering block, create a commit with a clear message and perform a normal push to `origin/main`.
- Before pushing, inspect staged changes and the history being published for secrets, personal information, local learning materials and temporary files. Keep `learning/`, `.env`, model caches and runtime artifacts out of Git.
- Verify that the remote branch SHA matches the local committed SHA after pushing. Report the commit hash and GitHub link.
- If authentication fails or branch histories conflict, stop publication and explain the reason. Never force push, overwrite unrelated remote history or publish to an unconfirmed remote.
- Keep credentials in the operating-system credential store. Do not request passwords or tokens in chat or embed credentials in repository URLs.


## Closed development cycle

The owner closed the current cycle after442c028 as Engineering Prototype / MVP PARTIAL. Do not start another corrective sprint, tune against frozen evaluations, or change business1.1 for presentation. Preserve runtime and research history. Any future technical work requires a separate explicit owner task; documentation closure does not accept unrestricted customer support or production readiness.
