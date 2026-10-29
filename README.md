# AI-Skills-Digital-Passport
Hackathon project for BTU students

## Local blockchain video demo

Following the team's mentor guidance, the submission can demonstrate the running
website locally in a video. Use **Anvil (chain 31337)** with real transactions;
no public hosting or test POL is needed for this demonstration. The UI must
identify verified local proofs as **Blockchain verified · Local Anvil**.

- [Setup checks and video walkthrough](blockchain/VIDEO_DEMO.md)
- [Fresh recording session if local chain state was lost](blockchain/VIDEO_DEMO.md#if-the-saved-anvil-state-is-empty-or-missing)
- [Blockchain architecture and tests](blockchain/README.md)
- [Website/extension API contract](blockchain/API_CONTRACT.md)
- [Recorded local website acceptance](ops/LOCAL_WEBSITE_ACCEPTANCE_2026-10-28.md)

Polygon Amoy configuration and a read-only deployment preflight are retained.
**No public Amoy contract has been deployed or public lifecycle tested by this
handoff.** Amoy deployment remains pending funding, signing setup and separate
transaction approval; it is not required to record the mentor-approved local
demo. Institutional records and approval used in the demo are synthetic.

# Production hosting

Use [Render production setup](ops/RENDER_PRODUCTION.md) for the main-based release,
exact build/start commands, environment settings and remaining live acceptance
gates. Provider settings and shared database migrations remain explicit release
operations; no automatic deployment is performed by these setup scripts.
