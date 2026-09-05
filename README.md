# MMO Permutations - live viewer

Shows PermuteMMO paths on a web page your friends can open, updating live from your PC.
Free: GitHub Pages hosts the page, a GitHub repo carries the data. No server, no subscription.

```
PermuteMMO.exe > results.txt        (your PC)
        |
        v
permute_publish.py  --push-->  data.json in your GitHub repo
                                        |
                                        v
                        friends open  https://YOU.github.io/mmo-live/
```

## What you need first

- **PermuteMMO working on your PC** ([kwsch/PermuteMMO](https://github.com/kwsch/PermuteMMO)) — this
  viewer only displays what PermuteMMO produces; it does not compute permutations itself.
- **A GitHub account** (free).

## Setup

1. **Make a repo** called `mmo-live`, public. Upload `index.html` to it.
2. **Turn on Pages**: repo Settings → Pages → Source: `main` branch, root. Your link becomes
   `https://WhoIsStitch.github.io/mmo-live/`.
3. **Edit `index.html`** — near the top of the `<script>`, set:
   ```js
   var DEFAULT_SRC = "https://raw.githubusercontent.com/WhoIsStitch/mmo-live/main/data.json";
   ```
4. **Make a token**: https://github.com/settings/tokens?type=beta → fine-grained token,
   only this repo, permission **Contents: Read and write**.
5. **Configure the publisher**: copy `config.example.json` to `config.json` and fill in
   `repo`, `token`, and `watch_file` (where PermuteMMO's output lands).
6. **Run it** while you hunt:
   ```
   PermuteMMO.exe > results.txt
   python permute_publish.py
   ```

## Using it

- **Friends**: send them the Pages link. It refreshes every 5 seconds on its own.
- **On stream**: add the same URL as an OBS browser source with `?overlay=1` on the end —
  transparent background, no chrome, just the table.
- **Ticking rows off** is per-person and stored in that person's browser, so your ticks
  don't wipe theirs.
- **Filters**: shiny only, alpha only, hide completed.

## Reading the grid

Same idea as the Rotom Labs table: each row is one path, read left to right.
`C` = catch that spawn, `KO` = defeat it. **Cells sharing a colour must be KO'd in a single
battle** — three blue cells means multi-battle three of them at once.

The paths come straight from PermuteMMO's step notation (`CR|B2|B3` → C, then 2 KO, then 3 KO),
so what you see is exactly what it calculated.

## If something looks wrong

`permute_publish.py` keeps the raw text too — open "Raw PermuteMMO output" at the bottom of the
page to compare against what PermuteMMO actually printed. If a line isn't parsed it still shows
up there, so nothing is silently lost.
