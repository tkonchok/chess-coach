# Customize the interface yourself

Start with one visible change, refresh, and compare desktop and phone widths. You can change the presentation without changing engine analysis or saved data.

## Where to edit

| Change | File / selector |
|---|---|
| Colors | `chess_coach/static/practice.css`, first `:root` block |
| Card spacing and corners | `.panel`, `.companion`, `.position-card`, `.game-row` |
| Desktop practice layout | Media rule with `min-width:1001px` and `min-height:700px` |
| Phone layout | Media rules with `max-width:600px` |
| Games screen text/forms | `chess_coach/templates/beta_home.html` |
| Position picker | `chess_coach/templates/beta_job.html` |
| Coaching layout/text | `chess_coach/templates/practice.html` |
| Shared navigation | `chess_coach/templates/_beta_header.html` |

The same stylesheet serves the screens. Scope a change to `.practice-screen` when it should affect only the board workspace.

## Your first useful change

Choose your own accent color. Hint: edit `--green` in the first line of the stylesheet. It controls the main buttons, selected tabs, and companion badge. Keep text readable against it. Also try `--canvas` for the page background and `--soft` for secondary surfaces.

Refresh the browser with Cmd+Shift+R. If a template change is not appearing, restart Flask; this installation runs without the reloader.

## Find the spacing you want to change

1. Right-click the element in the browser and choose **Inspect**.
2. In **Styles**, try a small change such as `padding: 12px` or `gap: 10px`. This preview is temporary.
3. In **Computed**, find which rule supplies the final value. Desktop and mobile media rules can override the base rule.
4. Copy the change into that exact CSS rule, then refresh.

Example: `.panel` has a base padding, while the compact desktop workspace overrides it with `.practice-screen .panel`. Changing only the base rule will not change that desktop panel.

## Keep the board workspace usable

The desktop board width is tied to viewport height with `calc(100dvh - 400px)`. Lowering the subtracted value makes the board larger; it also leaves less room for controls. Check that all ranks and navigation remain visible. Keep the evaluation bar in the board grid so it stays aligned with the squares.

Check at 1280 × 900 and about 390 pixels wide using the browser's device toolbar. Longer notes may scroll within the coaching panel; phone pages intentionally scroll.

Before changing the practice HTML, keep element IDs, form field names, and `data-*` attributes used by `practice.js`. They connect the interface to move validation, navigation, and saving. Rearrange wrappers and CSS classes first. Engine logic and persistence are separate from these visual choices.

## Verify a finished change

Try sign-in, game selection, a move, Reveal, Play it through, Previous/Next, and Save. Check keyboard focus as well as clicking. The optional browser suite also checks layout overflow and the central workflow:

```sh
env PLAYWRIGHT_BROWSERS_PATH=/private/tmp/chess-coach-browsers RUN_BROWSER_TESTS=1 .venv/bin/python -m unittest discover -s tests -p test_browser.py -v
```

That browser path is specific to this local installation. See README setup for a different machine.

## New library and welcome screens

- `.landing-hero` and `.landing-steps` control the signed-out welcome screen. The board is a labelled static preview.
- `.game-group`, `.group-heading`, and `.library-filters` control grouped personal puzzles.
- `_position_cards.html` is shared by Puzzles and analysis results; keep links and image URLs intact.
- `.analysis-state` and `.analysis-activity` control waiting/results feedback. The activity animation does not represent percentage progress and respects reduced-motion preferences.

Your small task: choose a background for the **Practiced** badge. Hint: find `.practiced-badge` near the end of `practice.css`, try a color in browser Styles first, and check the green text remains readable. This changes presentation only; practiced status still means a saved attempt.

The practice workspace now omits the old heading card and options dropdown. `.coach-actions` controls the unified toolbar; Self analysis uses `aria-pressed` to indicate its selected state. Keep IDs intact when changing button labels or spacing.

Archive browsing uses `templates/beta_archive.html`, shared `templates/_game_rows.html`, and `.archive-controls`, `.archive-field`, `.archive-pagination` CSS. The controls wrap on narrow screens. Practice line visibility is computed in `renderWalkthrough()` in `static/practice.js`: one line when identical, separate saved/active labels when different. A safe personal adjustment is changing the archive “Older games →” link text; retain its URL parameters so month, filter and page survive navigation.
