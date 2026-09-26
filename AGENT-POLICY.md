<!-- ai-generated: 80% - Claude Code drafted the justifications, I reviewed them -->
# Agent policy

The `reviewer` sub-agent (`.claude/agents/reviewer.md`) may read and comment. Each denied tool is a blast-radius
decision: what it could damage, and who would have to repair it.

- Bash(rm *): the reviewer reads and comments; deleting files is the author's decision, not the reviewer's
- Bash(git push *): a push publishes the work and is what the receipts record, so only the author decides when it happens
- Bash(git tag *): tags never move after their receipt, and a wrong or moved tag voids a graded attempt that cannot be undone
- Bash(docker *): containers and volumes hold the ticket data and use local resources; the reviewer needs none of them to read code
- WebFetch: fetching pages could pull outside content into the review or leak repository text, and the review needs only the local files
