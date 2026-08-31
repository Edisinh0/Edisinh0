"""Recolecta estadisticas de GitHub via la API GraphQL y REST.

Usa el gh CLI como transporte: local toma la sesion de `gh auth`, y en el
workflow toma GH_TOKEN. Salida: JSON por stdout.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone



def gh(args, payload=None):
    """Llama al gh CLI. Funciona igual local y en Actions (gh viene preinstalado)."""
    r = subprocess.run(
        ["gh", *args],
        input=payload,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)


def gql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}})
    out = gh(["api", "graphql", "--input", "-"], payload)
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


def rest(path, intentos=6, espera=3):
    """Devuelve (data, ok).

    /stats/* responde 202 la primera vez porque GitHub calcula las cifras en
    segundo plano; hay que reintentar hasta que devuelva el arreglo listo.
    """
    for i in range(intentos):
        try:
            data = gh(["api", path])
        except RuntimeError:
            data = None
        if isinstance(data, list) and data:
            return data, True
        if i < intentos - 1:
            time.sleep(espera)
    return None, False


REPOS_Q = """
query($cursor: String) {
  viewer {
    login
    name
    createdAt
    followers { totalCount }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        isFork
        stargazerCount
        languages(first: 20) { edges { size node { name color } } }
      }
    }
  }
}
"""

CONTRIB_Q = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
      totalRepositoryContributions
    }
  }
}
"""


def collect():
    cursor, repos, meta = None, [], {}
    while True:
        d = gql(REPOS_Q, {"cursor": cursor})["viewer"]
        meta = {
            "login": d["login"],
            "name": d["name"],
            "created_at": d["createdAt"],
            "followers": d["followers"]["totalCount"],
            "repos_total": d["repositories"]["totalCount"],
        }
        repos += d["repositories"]["nodes"]
        page = d["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]

    # Commits: contributionsCollection cubre 1 año por consulta -> iterar por año
    start = datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    commits, contributed = 0, 0
    year = start.year
    while year <= now.year:
        frm = max(start, datetime(year, 1, 1, tzinfo=timezone.utc))
        to = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        c = gql(
            CONTRIB_Q,
            {"from": frm.isoformat(), "to": to.isoformat()},
        )["viewer"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        contributed += c["totalRepositoryContributions"]
        year += 1

    # Lineas de codigo y commits propios: /stats/contributors por repo.
    added = deleted = commits_repos = 0
    sin_datos = []
    yo = meta["login"].lower()
    for r in repos:
        if r["isFork"]:
            continue
        data, ok = rest(f"/repos/{r['nameWithOwner']}/stats/contributors")
        if not ok:
            sin_datos.append(r["nameWithOwner"])
            continue
        for c in data:
            if ((c.get("author") or {}).get("login") or "").lower() != yo:
                continue
            commits_repos += c.get("total", 0)
            for w in c.get("weeks", []):
                added += w.get("a", 0)
                deleted += w.get("d", 0)

    langs = {}
    for r in repos:
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, {"size": 0, "color": e["node"]["color"]})
            langs[n]["size"] += e["size"]

    return {
        **meta,
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": max(commits, commits_repos),
        "commits_contribuciones": commits,
        "commits_repos": commits_repos,
        "repos_sin_stats": sin_datos,
        "contributed": contributed,
        "lines_added": added,
        "lines_deleted": deleted,
        "lines_total": added - deleted,
        "languages": sorted(
            ({"name": k, **v} for k, v in langs.items()),
            key=lambda x: -x["size"],
        ),
        "generated_at": now.isoformat(),
    }


if __name__ == "__main__":
    json.dump(collect(), sys.stdout, indent=2, ensure_ascii=False)
    print()
