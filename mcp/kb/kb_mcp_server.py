from __future__ import annotations
import json, math, re, os, subprocess
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

KB_ROOT = Path("/Users/srlanka/Documents/KB-sree")
INDEX = KB_ROOT / "_index" / "bm25_index.json"

mcp = FastMCP("Sree KB MCP")

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())

def _score_doc(q_terms, doc_tf, idf, dl, avgdl, k1, b) -> float:
    score = 0.0
    for t in q_terms:
        if t not in doc_tf:
            continue
        tf = doc_tf[t]
        denom = tf + k1 * (1 - b + b * (dl / avgdl if avgdl else 1.0))
        score += idf.get(t, 0.0) * (tf * (k1 + 1)) / (denom if denom else 1.0)
    return score

def _load_index() -> Dict[str, Any]:
    if not INDEX.exists():
        raise FileNotFoundError(f"Index not found at {INDEX}. Run kb_update first.")
    return json.loads(INDEX.read_text(encoding="utf-8"))

@mcp.tool()
def kb_search(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Search Sree's private local knowledge base (BM25). Returns top matches with file paths + snippets.
    """
    query = (query or "").strip()
    if not query:
        return {"error": "query is empty"}

    data = _load_index()
    idf = data["idf"]
    docs = data["docs"]
    lengths = data["lengths"]
    avgdl = data["avgdl"]
    k1 = data.get("k1", 1.5)
    b = data.get("b", 0.75)

    q_terms = _tokenize(query)
    scored = []
    for i, d in enumerate(docs):
        s = _score_doc(q_terms, d["tf"], idf, lengths[i], avgdl, k1, b)
        if s > 0:
            scored.append((s, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: max(1, min(int(top_k), 20))]

    results = []
    for s, d in top:
        results.append({
            "score": round(float(s), 4),
            "path": d["path"],
            "chunk_id": d["chunk_id"],
            "id": d["id"],
            "snippet": (d["text"] or "").replace("\n", " ")[:500],
        })

    return {
        "query": query,
        "top_k": top_k,
        "index_chunks": data.get("N"),
        "results": results,
    }

@mcp.tool()
def kb_update() -> Dict[str, Any]:
    """
    Run kb_update to refresh derived text + indexes on this Mac.
    """
    cmd = ["/bin/zsh", "-lc", "kb_update"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "stdout": p.stdout[-4000:],
        "stderr": p.stderr[-4000:],
    }

def main():
    # stdio transport is the most reliable across MCP clients
    mcp.run()

if __name__ == "__main__":
    main()
