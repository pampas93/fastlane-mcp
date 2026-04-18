## Git Workflow

For every logical feature implementation or bug fix in this repository:

1. Make the code or documentation change.
2. Run the relevant verification for that change.
3. Create a focused git commit with a clear message.
4. Push the commit to `origin master`.

Additional rules:

- Do not batch unrelated changes into one commit.
- If a push fails because of authentication, network, or remote state, report that clearly.
- Do not rewrite published history unless explicitly requested.

## Next Steps Workflow

Maintain a single repo-root file named `NEXT_STEPS.md`.

For every logical feature implementation or bug fix in this repository:

1. Update `NEXT_STEPS.md` before finishing the task.
2. Remove completed items that were fully handled.
3. Add the most important follow-up actions that the user should do next.
4. Prefer concrete action items such as testing, manual verification, deployment, cleanup, or known bugs.

Additional rules:

- Keep `NEXT_STEPS.md` short and current.
- Put the highest-priority unfinished actions at the top.
- If a change has not been tested manually, add an explicit test step.
- If there are no meaningful follow-ups, write `- No pending next steps right now.`
