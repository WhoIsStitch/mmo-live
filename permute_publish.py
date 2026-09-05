#!/usr/bin/env python3
"""
permute_publish.py - watches PermuteMMO's output and publishes it so a
static web page can show it live to other people.

    PermuteMMO.exe > results.txt      (on your PC)
              |
              v
    permute_publish.py  --->  data.json committed to your GitHub repo
                                        |
                                        v
                              friends open your GitHub Pages link

Stdlib only - no pip install needed. Python 3.8+.

Setup (once):
  1. Make a GitHub repo, e.g. "mmo-live", and enable GitHub Pages on it.
  2. Make a fine-grained personal access token with "Contents: Read and write"
     for that repo:  https://github.com/settings/tokens?type=beta
  3. Copy config.example.json to config.json and fill it in.
  4. Run:  python permute_publish.py

Leave it running while you hunt. Every time PermuteMMO rewrites the output
file, this pushes the new results and the page updates within seconds.
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

# ---------------------------------------------------------------- parsing

# "* CR|B2|B3      >>> Spawn3 = <summary>"   (wave prefix optional)
RESULT_RE = re.compile(
    r"^\*\s+(?P<steps>.+?)\s+>>>\s+"
    r"(?P<wave>(?:Bonus\s+|Wave\s+\d+\s+)?)"
    r"Spawn(?P<index>\d+)\s*=\s*(?P<summary>.*?)\s*$"
)

# "α-Charizard (F):  3 ■ 31/31/30/25/31/31 Timid    -- NOT ALPHA"
SUMMARY_RE = re.compile(
    r"^(?P<alpha>\u03b1-)?\s*"
    r"(?P<name>.+?)"
    r"(?:\s+\((?P<gender>[MF])\))?"
    r"\s*:"
    r"(?:\s+(?P<rolls>\d+)\s+(?P<shiny>[\u25a0*]))?"
    r"\s+(?P<ivs>\d{1,2}(?:/\d{1,2}){5})"
    r"(?:\s+(?P<nature>[A-Za-z]+))?"
    r"(?P<rest>.*)$"
)


def parse_summary(summary):
    m = SUMMARY_RE.match(summary)
    if not m:
        return {"species": summary.strip(), "unparsed": True}

    rest = (m.group("rest") or "").strip()
    notes = [n.strip(" -") for n in rest.split("--") if n.strip(" -")]

    return {
        "species": m.group("name").strip(),
        "alpha": m.group("alpha") is not None and "NOT ALPHA" not in rest.upper(),
        "gender": m.group("gender") or "",
        "shiny": m.group("shiny") is not None,
        "square": m.group("shiny") == "\u25a0",
        "rolls": int(m.group("rolls")) if m.group("rolls") else None,
        "ivs": [int(v) for v in m.group("ivs").split("/")],
        "nature": (m.group("nature") or "").strip(),
        "notes": notes,
    }


def parse_output(text):
    """PermuteMMO prints a header block per spawner, then '*' result lines."""
    groups = []
    current = {"header": "", "context": [], "results": []}
    counts = {"total": 0, "shiny": 0, "alpha": 0}

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        m = RESULT_RE.match(line)
        if m:
            entry = parse_summary(m.group("summary"))
            entry["steps"] = [s for s in re.split(r"[|>]+", m.group("steps")) if s.strip()]
            entry["steps_raw"] = m.group("steps").strip()
            entry["wave"] = m.group("wave").strip()
            entry["spawn"] = int(m.group("index"))
            current["results"].append(entry)
            counts["total"] += 1
            if entry.get("shiny"):
                counts["shiny"] += 1
            if entry.get("alpha"):
                counts["alpha"] += 1
        else:
            # a non-result line starts a new block once we have results
            if current["results"]:
                groups.append(current)
                current = {"header": "", "context": [], "results": []}
            if not current["header"]:
                current["header"] = line.strip()
            else:
                current["context"].append(line.strip())

    if current["results"] or current["header"]:
        groups.append(current)

    return groups, counts


# ---------------------------------------------------------------- github

def github_put(cfg, content_bytes):
    owner, repo = cfg["repo"].split("/", 1)
    path = cfg.get("data_path", "data.json")
    branch = cfg.get("branch", "main")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    headers = {
        "Authorization": f"Bearer {cfg['token']}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "permute-publish",
    }

    # need the current blob sha to update an existing file
    sha = None
    try:
        req = urllib.request.Request(f"{url}?ref={branch}", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            sha = json.load(r).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    body = {
        "message": "update permutation results",
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="PUT"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


# ---------------------------------------------------------------- main

def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(
            "No config.json found.\n"
            "Copy config.example.json to config.json and fill in your repo and token."
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["token"] = os.environ.get("GITHUB_TOKEN") or cfg.get("token", "")
    missing = [k for k in ("repo", "token", "watch_file") if not cfg.get(k)]
    if missing:
        sys.exit("config.json is missing: " + ", ".join(missing))
    return cfg


def main():
    cfg = load_config()
    watch = cfg["watch_file"]
    interval = float(cfg.get("poll_seconds", 2))
    last_signature = None

    print(f"Watching {watch}")
    print(f"Publishing to {cfg['repo']}:{cfg.get('data_path', 'data.json')}")
    print("Leave this running. Ctrl+C to stop.\n")

    while True:
        try:
            if os.path.exists(watch):
                with open(watch, encoding="utf-8", errors="replace") as f:
                    text = f.read()

                signature = hash(text)
                if signature != last_signature and text.strip():
                    groups, counts = parse_output(text)
                    payload = {
                        "updated": datetime.now(timezone.utc).isoformat(),
                        "source": os.path.basename(watch),
                        "counts": counts,
                        "groups": groups,
                        "raw": text if cfg.get("include_raw", True) else "",
                    }
                    blob = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
                    github_put(cfg, blob)
                    last_signature = signature
                    stamp = datetime.now().strftime("%H:%M:%S")
                    print(
                        f"[{stamp}] published - {counts['total']} results, "
                        f"{counts['shiny']} shiny, {counts['alpha']} alpha"
                    )
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")
            return
        except urllib.error.HTTPError as e:
            print(f"GitHub rejected the push ({e.code}): {e.read()[:200]!r}")
            time.sleep(10)
        except Exception as e:  # keep running through transient errors
            print(f"error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
