<!-- ai-generated: 80% - Claude Code drafted, I reviewed -->
# svcdesk - notes for the coding agent

Course repository for ITSM 2026/27. The service is a FastAPI service desk API; the contract is in
`Laboratory 1 package-20260926/API.md` and `specs/001-svcdesk/spec.md`.

- **Specs before code.** Nothing under `src/` may be added before the `specs` receipt exists (it does, for Lab 1).
- **Decisions.** The service is C1=wallclock, C2=immutable, C3=vip. `DECISIONS.md` must always equal what the running
  service does; change both together.
- **Disclosure.** Every `.py` and `.md` file under `src/` and `specs/`, and `DECISIONS.md`, carries an
  `ai-generated: <0-100>% - <how>` line in its first ten lines.
- **Compose.** Service `svcdesk`, `build:` never `image:` alone, port 8080, `SVCDESK_TEST_CLOCK=1`, no bind mounts,
  dependencies installed at build time.
- **Tags never move.** A new attempt is a new tag (`lab1/v2`, `lab1/v3`); never re-tag or force-push a receipted tag.
- **Verify.** `./itsmlab.sh verify 1` must exit 0 and its `commit` line must not say `(dirty)`.
- **No personal data** in the repository.
