# Chess Coach v1 release boundary

## Required today

- Keep the complete existing game → analysis → practice → optional reflection workflow.
- Remove confirmed dead code; preserve CLI tools, saved data and immutable versions.
- Verify tests, both-color browser workflows, six engine-fact positions, Docker, cleanup, persistence and backup restore.
- Publish reviewed code to `tkonchok/chess-coach`; deploy one Railway instance with `/data` storage.
- Verify live Google sign-in with two accounts, account isolation and deployed persistence.
- Keep public AI commentary disabled and document performed versus pending checks.

## Optional

- Additional visual polish after release verification.
- User-owned badge text or spacing adjustment; see the UI customization guide.

## Deferred

Automatic whole-history scanning, generated similar puzzles, graded completion, conversational AI, adaptive scheduling, rating diagnoses, multiple instances, and the long learning guide. Maintain and scale after measuring real usage.

Budget: 4–6 focused hours, excluding account setup and unresolved release failures. Railway trial first; no upgrade or extra service needed for initial verification. Hosting ceiling is $15/month, with a $10 alert and $15 compute hard cap where available.
