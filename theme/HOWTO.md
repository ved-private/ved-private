# Theme system

`README.md` and everything in `assets/` are generated. Do not edit them by hand.

## Change colours yourself (the baseline)
Edit `theme/default.json` on GitHub (pencil icon) and commit. The Action rebuilds the profile.

| key | what it does |
|---|---|
| `accent` | main colour. Every red in the artwork and badges follows it (hue and saturation; brightness is kept so text stays readable) |
| `bg` | optional near-black background colour, for example `"#0b0f1a"`. `null` = follows the accent |
| `text` | optional light text colour, for example `"#e6edf3"`. `null` = follows the accent |
| `name` | label shown under the swatches |
| `reset_after_hours` | how long a visitor's colour stays before it reverts |
| `repo` | only used when building on your own computer. In Actions the real repo is detected |

## Visitors
The circles in the Theme section open a pre-filled issue (`theme: ocean`). When it is submitted the Action
recolours the profile, comments, and closes the issue. A scheduled run (every 3 hours) reverts it to
`default.json` once `reset_after_hours` has passed. `theme: reset` reverts at once.
Visitors can only change the accent, and only to a preset or a six-digit hex colour.

## Files you may edit
- `theme/README.template.md`: the page text and layout (`{{tag}}`, `{{swatches}}` etc. are filled in)
- `theme/presets.json`: swatch names and colours
- `theme/src/*.svg`: the artwork (draw it in the original red `#ff1e3c` family)

## Moving to another account
Copy all files to the new profile repo (`<username>/<username>`), then run the **theme** workflow once from the
Actions tab. Needs: repo public, Issues on, Actions on. If you push with git, the token needs the `workflow` scope
(uploading through the web page needs nothing extra).
