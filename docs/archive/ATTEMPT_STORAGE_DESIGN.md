> Historical design, superseded by the implemented storage in `chess_coach/storage.py` and [architecture](../ARCHITECTURE.md). Statements about missing endpoints describe the old prototype.

# Completed-attempt storage — proposed design

Status: SQLite and Python's `sqlite3` approved; design only, no storage code or
database created. This is milestone 7A, not adaptive coaching. Existing practice,
review validation, and versioning stay in place.

## Reconciliation with the code

- Finish only shows a browser message. There is no attempt endpoint/store/history.
- `review_candidate()` produces an accepted snapshot with source PGN, headers,
  analysis metadata, review, card and a full `version_id`. `card_from_review()`
  already checks consistency and reconstructs it without an engine; reuse it.
- `create_app_from_review()` currently discards that snapshot after deriving a
  TrainingCard and shortened display label. Carry the complete validated snapshot
  into the persistence boundary instead. Never recover identity from label text.
- The web `card_id` hashes card content only; it is not the full review version.
  Two reviews can display the same board/card while having distinct provenance.
- The default demo builds a TrainingCard directly and has no accepted analysis
  snapshot. Preserve that demo; do not fabricate engine metadata to make it savable.
  First storage tests use genuine accepted-snapshot-shaped fixtures. Before UI
  integration, either load a genuine retained review for the default or explicitly
  keep snapshot-less demo mode unsavable, with clear wording.
- Notes remain optional. The handoff's learning loop is not a new requirement to
  explain every attempt. Old offline-card prompt text still suggests explanation;
  wording cleanup must not silently rewrite saved reviewed versions.

## Two tables, two responsibilities

| Table | Proposed fields | Meaning |
| --- | --- | --- |
| reviewed_cards | version_id (primary key), snapshot_json | One immutable, complete accepted review per version, including the source game and exact exercise |
| attempts | submission_id (primary key), review_version_id (foreign key), proposed_move_uci, original_reasoning, dont_remember, practice_reasoning, takeaway, completed_at | One completed attempt; separate typed statements, memory choice and server-recorded UTC completion time |

UCI is the machine-readable move, such as `c5c4`. Derive display SAN from the saved
starting board, and validate legality there, not on the current exploration board.
The proposed move must remain separate from the moves used to explore the example.
No inferred profile fields, right/wrong labels, or puzzle difficulty are stored.

Blank text plus `dont_remember=false` means unanswered, not remembered. A checked
choice means explicitly not remembered. Preserve any existing draft verbatim but
label it as an unconfirmed draft in history; do not present it as recalled intent.
Normalize only for blank checks/validation, not to rewrite the user's statement.

## Transactions and retries

A transaction is an all-or-nothing write: save the snapshot if absent and the
attempt together; roll back if any part fails. Return success only after commit.
Never replace/update the contents of an existing reviewed version. If a version
key exists, verify its stored content agrees with the incoming validated snapshot.

Create one submission UUID per practice attempt in the browser. Reuse it and the
same captured save payload on retries, including a lost-response retry. The server
uses its unique key rather than relying on disabling a button:

- Same key and same content: return the original saved attempt and timestamp.
- Same key with different content: conflict, never silently overwrite notes.
- New attempt: new key, even when every answer happens to be identical.

Use a transaction/unique constraint to make competing requests safe. Freeze the
outgoing payload while a save/retry is unresolved; keep visible drafts intact and
explain conflicts instead of silently discarding edits. No persistent draft cache.
Timestamps are created on the first successful save, not accepted from the client.

## Storage boundary and validation

- Proposed path: repository-root `instance/chess-coach.sqlite3`, configurable for
  tests. Add `/instance/` to Git ignore before creating it. Do not put durable
  history in `generated/`, which also holds disposable cache artifacts.
- Use a small `storage.py` with explicit operations, not an ORM or generic repository
  abstraction. Open/close short-lived connections; parameterize data in queries.
- Create schema version 1 atomically for a new database. Record the application
  version with `PRAGMA user_version`; refuse unknown versions or an unexpected
  nonempty unversioned database instead of recreating user data. Later changes
  require explicit tested migrations. Snapshot schema version is a separate concept.
- Enable/check foreign keys on every connection, outside a transaction, and bound
  lock waits. These mechanisms follow [SQLite's version pragma documentation](https://www.sqlite.org/pragma.html#pragma_user_version)
  and [foreign-key documentation](https://www.sqlite.org/foreignkeys.html).
- Validate accepted snapshot, full review identity, UUID, exact field types,
  text lengths and legal proposed move server-side. Never accept a browser-supplied
  replacement snapshot as trusted current-card data. Keep HTML escaping for notes.
- Existing 8 KiB move-request limit is not enough for three maximum-length Unicode
  notes. Define a bounded save-specific byte limit and test Unicode payloads without
  weakening existing move-route limits; retain the 2,000-character field limits.
- The app must open history without rereading the original review file. A missing
  active review may prevent starting that exercise, but must not prevent browsing
  saved history. Refactor factory/route boundaries accordingly during integration.
- Keep local-only access protections; durable private notes increase the cost of
  accidental exposure. No external notes transmission, logging of note bodies,
  authentication expansion, or deployment in this slice.

## History and deletion

Provide a recent-first list, clear empty state, detail view of all saved inputs,
and original-exercise replay from the stored snapshot. Opening history is not a
fresh attempt; an explicit Try again action should start a new one.

Deletion requires a deliberate confirmation and a state-changing request, never
a GET link. Delete only the requested attempt; keep any snapshot referenced by
other attempts. Do not add inferred memory or a learner profile to this store.
Define handling of unused snapshots and old submission retries after deletion
before completing deletion tests; do not let a retry unexpectedly resurrect a
deleted attempt. Application deletion is not a promise of forensic disk erasure
or removal from previously made backups.

## Small implementation slices and verification

1. **First: retain and reopen one reviewed snapshot.** Add `storage.py` and
   `tests/test_storage.py`. Use a temporary on-disk database; initialize schema,
   validate/store a review, close the connection, reopen, load and reconstruct
   the exact card. Also test repeated initialization, unknown schema version,
   tampered snapshot rejection and replacement of the source review with a new
   version without altering the old version. No Flask/UI changes yet.
2. Save/read attempts transactionally; test all distinct fields, legal moves,
   rollback, duplicate/concurrent/lost-response retries, changed-payload conflicts,
   separate attempts, shared references and deletion. No real user data in tests.
3. Carry snapshots through the web adapter, implement validated Save and finish,
   accurate local-storage wording, retry feedback and history/detail/replay/delete.
   Handle absent source files without blocking history. Test route failures and
   escaping; keep incomplete page drafts only in memory.
4. Browser smoke: save with no notes and with each note/choice, repeat submission,
   fail/retry without input loss, open/delete history and restart the app. Verify
   history after source review removal. Record actual results, not intended behavior.

Exclusions: autosaved unfinished drafts, AI interpretation, grading, spaced
repetition, user accounts, broader game-library persistence and release backup
tooling. Backup/restore remains a required 7B/8 gate before deployable completion.
