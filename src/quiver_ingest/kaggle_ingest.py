"""Re-ingest this workspace's reference PDFs on a remote GPU worker.

The PDFs are not in the repository (``guidance/*/*`` is gitignored, and the
repository is public). The worker downloads each one from its public source
and checks it against the sha256 of the copy already on the operator's
machine. A file that does not match is refused instead of ingested, so the
Markdown that comes back describes the same bytes the operator has.

Called by the remote-execution runner (cell 1) with the kwargs from the job's
``run-config.json``. The runner's working directory is the only thing a fetch
returns, so the work happens in a scratch copy outside it, and only the
ingested paper folders plus ``ingest-summary.json`` are copied back.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# The PDFs to ingest: topic folder under guidance/, file stem, public source
# URL, and the sha256 of the operator's local copy.
PAPERS = [
    (
        "paper-guide",
        "2603.23560v1",
        "https://arxiv.org/pdf/2603.23560v1",
        "237c445caf7c215fd7ef607dc32e003bd0df0e7df2ac286124bfb795692a64f7",
    ),
    (
        "paper-guide",
        "LIPIcs.SoCG.2026.47",
        "https://drops.dagstuhl.de/storage/00lipics/lipics-vol367-socg2026/"
        "LIPIcs.SoCG.2026.47/LIPIcs.SoCG.2026.47.pdf",
        "c56266ffa219646911bf113e99df06c0b4bd9ca915da2642e5f1e16ba128566b",
    ),
    (
        "paper-guide",
        "2303.16075v1",
        "https://arxiv.org/pdf/2303.16075v1",
        "e6328023812421808834f2fee74cdb1e96aa75361af709db72632b385a087dee",
    ),
    (
        "reference-papers",
        "1812.05261v2",
        "https://arxiv.org/pdf/1812.05261v2",
        "880e8b1ab46281b7ace55b9cac43e29067ef48997cbce69fd7f46ba9d56526f2",
    ),
    (
        "reference-papers",
        "2010.09628v3",
        "https://arxiv.org/pdf/2010.09628v3",
        "9cbd165819b14238856f04ec0f1ea906efc51aaeea7de24a0a3c8d1c7887c00e",
    ),
    (
        "reference-papers",
        "2211.15306v3",
        "https://arxiv.org/pdf/2211.15306v3",
        "d38013e66060a9c821db5a23c0166aeb648749a73e116c24017e74bd8e52d03b",
    ),
    (
        "reference-papers",
        "2406.05069v1",
        "https://arxiv.org/pdf/2406.05069v1",
        "69d9e8412668603bd5b2c2c4d3b3088a1c73bc627d003405b191a17f34e9871f",
    ),
    (
        "reference-papers",
        "2504.08119v2",
        "https://arxiv.org/pdf/2504.08119v2",
        "6c19709ad354d1de33cad22f26bfea7f6c6aac35e2199e842375eb534c29b548",
    ),
    (
        "reference-papers",
        "Sheehy.CCCG2012.multicover-nerve",
        "http://2012.cccg.ca/papers/paper52.pdf",
        "168ed88382d23b8a96885bad85f967745452368e251e6141b780eef0270b7b4a",
    ),
]

# What the scratch workspace needs from the clone to provision and ingest.
COPY_PATHS = ["papersmith.yaml", "scripts/setup_env.py", "skills/paper-ingestion"]

# The runner clones into <cwd>/clone; this file is <clone>/src/quiver_ingest/.
CLONE_ROOT = Path(__file__).resolve().parents[2]


def _log(msg: str) -> None:
    print(f"[ingest {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _sh(cmd: list[str], **kw) -> None:
    _log("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, **kw)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def select(stems: list[str] | None) -> list[tuple[str, str, str, str]]:
    """The PAPERS rows to run, in PAPERS order. None means all of them."""
    if stems is None:
        return list(PAPERS)
    known = {p[1] for p in PAPERS}
    unknown = [s for s in stems if s not in known]
    if unknown:
        raise ValueError(f"unknown paper stems: {unknown}")
    return [p for p in PAPERS if p[1] in stems]


def _fetch(url: str, dest: Path, expected: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "quiver-tda-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)
    got = _sha256(dest)
    if got != expected:
        dest.unlink()
        raise RuntimeError(f"sha256 mismatch for {url}: got {got}, expected {expected}")


def _count_math(md: Path) -> dict:
    text = md.read_text(encoding="utf-8", errors="replace")
    return {"chars": len(text), "dollar_signs": text.count("$")}


def run(
    papers: list[str] | None = None,
    mode: str = "balanced",
    force_ocr: bool = True,
    scratch: str = "/tmp/quiver-ingest",
) -> dict:
    out_dir = Path.cwd()
    ws = Path(scratch)
    summary: dict = {"mode": mode, "force_ocr": force_ocr, "papers": {}}
    t0 = time.time()

    # 1. Scratch workspace outside the returned directory: the micromamba
    #    environment (several GB) lands in <ws>/.micromamba and must not
    #    come back as output.
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    for rel in COPY_PATHS:
        src, dst = CLONE_ROOT / rel, ws / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)

    try:
        smi = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True)
        summary["gpu"] = smi.stdout.strip() or smi.stderr.strip()
    except FileNotFoundError:
        summary["gpu"] = "nvidia-smi not found"
    _log(f"gpu: {summary['gpu']}")

    # 2. Provision the same environment the operator uses, with CUDA torch.
    t = time.time()
    _sh([sys.executable, str(ws / "scripts/setup_env.py"), "install", "--cuda"], cwd=ws)
    summary["setup_seconds"] = round(time.time() - t)

    # 3. Download and verify the PDFs as loose files in their topic folders.
    rows = select(papers)
    pdfs = []
    for topic, stem, url, sha in rows:
        dest = ws / "guidance" / topic / f"{stem}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _log(f"fetch {url}")
        _fetch(url, dest, sha)
        pdfs.append(dest)

    # 4. Ingest them all in one process, so the models load once.
    env_bin = ws / ".micromamba/envs/papersmith/bin"
    env = dict(os.environ)
    env["PATH"] = f"{env_bin}{os.pathsep}{env.get('PATH', '')}"
    env["LLAMA_CPP_BINARY"] = str(env_bin / "llama-server")
    cmd = [
        str(env_bin / "python"),
        "skills/paper-ingestion/scripts/extract_pdf.py",
        "--mode",
        mode,
        *(["--force-ocr"] if force_ocr else []),
        *map(str, pdfs),
    ]
    t = time.time()
    log_path = out_dir / "ingest.log"
    _log("$ " + " ".join(cmd) + f"  (log: {log_path.name})")
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            cmd, cwd=ws, env=env, stdout=log, stderr=subprocess.STDOUT
        )
    summary["ingest_seconds"] = round(time.time() - t)
    summary["ingest_exit"] = proc.returncode
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    for key, needle in [
        ("equation_failures", "Equation recognition failed"),
        ("ocr_failures", "OCR failed"),
        ("inference_errors", "Inference error"),
    ]:
        summary[key] = log_text.count(needle)

    # 5. Copy each ingested paper folder back into the returned directory.
    for topic, stem, _url, _sha in rows:
        folder = ws / "guidance" / topic / stem
        md = folder / f"{stem}.md"
        entry: dict = {"topic": topic, "ingested": md.is_file()}
        if md.is_file():
            entry.update(_count_math(md))
            dst = out_dir / "ingested" / topic / stem
            shutil.copytree(
                folder, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdf")
            )
        summary["papers"][stem] = entry

    summary["total_seconds"] = round(time.time() - t0)
    (out_dir / "ingest-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    _log(json.dumps(summary, indent=2))
    if proc.returncode != 0 or not all(
        p["ingested"] for p in summary["papers"].values()
    ):
        raise RuntimeError(
            f"ingestion incomplete (exit {proc.returncode}); see ingest.log"
        )
    return summary


def smoke() -> dict:
    """The rehearsal: the 6-page Sheehy paper only, same path end to end."""
    return run(papers=["Sheehy.CCCG2012.multicover-nerve"])
