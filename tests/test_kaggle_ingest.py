"""Offline tests for src/quiver_ingest/kaggle_ingest.py.

No GPU, no network, no real provisioning: the provisioner is replaced by a
fake environment whose `bin/python` mimics extract_pdf.py, and the PDFs are
fetched through file:// URLs from the operator's local guidance/ copies.
The evidence block is checked with the remote-execution skill's own
`shard_io.completeness()`, the predicate `smoke record` applies.

Run from the workspace root:
    python3 -m unittest tests.test_kaggle_ingest -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quiver_ingest import kaggle_ingest as K  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "shard_io", ROOT / "skills/remote-execution/scripts/shard_io.py"
)
shard_io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shard_io)

SHEEHY = "Sheehy.CCCG2012.multicover-nerve"
COMMIT = "066b47fa25c97d2e11f2bccffd77d02745ad8f37"

# Stand-in for the environment's python: given extract_pdf.py's argv, write
# <stem>/<stem>.md (+ a figure) for every PDF and move the PDF into it, the
# way extract_pdf.py files a loose PDF. FAKE_MD and FAKE_LOG steer it.
FAKE_PYTHON = """#!/usr/bin/env bash
shift
for a in "$@"; do
  case "$a" in
    *.pdf) d="${a%.pdf}"; s="$(basename "$d")"; mkdir -p "$d"
           printf '%s\\n' "${FAKE_MD:-# T  \\$x^2\\$ and \\$\\$y\\$\\$}" > "$d/$s.md"
           echo fig > "$d/fig.png"; mv "$a" "$d/" ;;
  esac
done
[ -n "$FAKE_LOG" ] && echo "$FAKE_LOG"
echo "surya-backend=${SURYA_INFERENCE_BACKEND:-unset}"
exit "${FAKE_EXIT:-0}"
"""

CUDA_FACTS = {
    "llama.cpp": "11860 cuda134_fake",
    "torch_probe": "True 13.0",
    "torch_cuda": True,
    "llama_cuda": True,
}


def local_rows():
    """PAPERS with each URL pointed at the operator's local copy."""
    rows = []
    for topic, stem, _url, sha in K.PAPERS:
        hits = sorted((ROOT / "guidance" / topic).glob(f"**/{stem}.pdf"))
        if not hits:
            hits = sorted((ROOT / ".scratch").glob(f"**/{stem}.pdf"))
        rows.append((topic, stem, hits[0].as_uri() if hits else "file:///missing", sha))
    return rows


class IngestRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kingest-"))
        self.out = self.tmp / "working"
        self.out.mkdir()
        (self.out / "run-config.json").write_text(json.dumps({"commit": COMMIT}))
        self.ws = self.tmp / "scratch"
        self.cwd = os.getcwd()
        os.chdir(self.out)
        self.patches = [
            mock.patch.object(K, "PAPERS", local_rows()),
            mock.patch.object(K, "_gpu", lambda: "GPU 0: Fake T4"),
            mock.patch.object(K, "_sh", self.fake_provision),
            mock.patch.object(K, "env_facts", lambda env_dir: dict(CUDA_FACTS)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)
        for var in ("FAKE_MD", "FAKE_LOG", "FAKE_EXIT"):
            os.environ.pop(var, None)

    def fake_provision(self, cmd, **kw):
        # cmd is [python, <ws>/scripts/setup_env.py, install, --cuda]
        bin_dir = Path(cmd[1]).parents[1] / K.ENV_REL / "bin"
        bin_dir.mkdir(parents=True)
        py = bin_dir / "python"
        py.write_text(FAKE_PYTHON)
        py.chmod(py.stat().st_mode | stat.S_IXUSR)

    def shard(self):
        return json.loads((self.out / "shard.json").read_text())

    def verdict(self):
        return shard_io.completeness(self.shard(), K.REQUIRED_EVIDENCE)

    def test_happy_path_passes_the_skills_own_predicate(self):
        # smoke() as the runner calls it, with only the scratch dir redirected.
        real_run = K.run
        with mock.patch.object(
            K, "run", lambda **kw: real_run(scratch=str(self.ws), **kw)
        ):
            summary = K.smoke()
        self.assertEqual(summary["requested"], [SHEEHY])
        self.assertEqual(self.verdict(), {"complete": True, "missing": []})
        ev = self.shard()["evidence"]
        self.assertEqual(ev["commit"], COMMIT)
        self.assertEqual(ev["allIngested"], [SHEEHY])
        self.assertGreater(ev["mathFound"][SHEEHY], 0)
        folder = self.out / "ingested/reference-papers" / SHEEHY
        self.assertTrue((folder / f"{SHEEHY}.md").is_file())
        self.assertTrue((folder / "fig.png").is_file())
        self.assertEqual(list(folder.glob("*.pdf")), [], "PDFs must not come back")
        self.assertTrue((self.out / "ingest-summary.json").is_file())

    def test_all_nine_papers_round_trip(self):
        K.run(scratch=str(self.ws))
        self.assertEqual(self.verdict()["complete"], True)
        self.assertEqual(len(self.shard()["evidence"]["allIngested"]), 9)

    def test_no_gpu_fails_before_touching_anything(self):
        with mock.patch.object(K, "_gpu", lambda: None):
            with self.assertRaisesRegex(RuntimeError, "no GPU"):
                K.run(papers=[SHEEHY], scratch=str(self.ws))
        self.assertFalse(self.ws.exists())
        self.assertEqual(self.shard()["evidence"], {"commit": COMMIT})
        self.assertIn("evidence.gpu", self.verdict()["missing"])
        self.assertIn("no GPU", self.shard()["summary"]["error"])

    def test_cpu_environment_stops_before_ingesting(self):
        cpu = {
            "llama.cpp": "11351 cpu_mkl_x",
            "torch_probe": "False None",
            "torch_cuda": False,
            "llama_cuda": False,
        }
        with mock.patch.object(K, "env_facts", lambda env_dir: cpu):
            with self.assertRaisesRegex(RuntimeError, "not on CUDA"):
                K.run(papers=[SHEEHY], scratch=str(self.ws))
        self.assertEqual(self.shard()["summary"]["papers"], {})
        self.assertFalse((self.out / "ingest.log").exists())
        self.assertEqual(
            self.verdict()["missing"],
            [
                "evidence.cuda",
                "evidence.allIngested",
                "evidence.mathFound",
                "evidence.cleanInference",
            ],
        )

    def test_logged_timeouts_fail_clean_inference_only(self):
        os.environ["FAKE_LOG"] = "Inference error: Request timed out."
        with self.assertRaisesRegex(RuntimeError, "evidence.cleanInference"):
            K.run(papers=[SHEEHY], scratch=str(self.ws))
        self.assertEqual(self.verdict()["missing"], ["evidence.cleanInference"])
        self.assertEqual(self.shard()["summary"]["inference_errors"], 1)

    def test_markdown_without_math_fails_math_found(self):
        os.environ["FAKE_MD"] = "# only prose"
        with self.assertRaises(RuntimeError):
            K.run(papers=[SHEEHY], scratch=str(self.ws))
        self.assertEqual(self.verdict()["missing"], ["evidence.mathFound"])

    def test_nonzero_extractor_exit_withholds_all_ingested(self):
        os.environ["FAKE_EXIT"] = "3"
        with self.assertRaises(RuntimeError):
            K.run(papers=[SHEEHY], scratch=str(self.ws))
        self.assertEqual(self.shard()["summary"]["ingest_exit"], 3)
        self.assertIn("evidence.allIngested", self.verdict()["missing"])

    def test_sha_mismatch_is_refused_and_recorded(self):
        rows = [
            (t, s, u, "0" * 64) if s == SHEEHY else (t, s, u, h)
            for t, s, u, h in local_rows()
        ]
        with mock.patch.object(K, "PAPERS", rows):
            with self.assertRaisesRegex(RuntimeError, "sha256 mismatch"):
                K.run(papers=[SHEEHY], scratch=str(self.ws))
        self.assertIn("sha256 mismatch", self.shard()["summary"]["error"])
        self.assertFalse(
            (self.ws / "guidance/reference-papers" / f"{SHEEHY}.pdf").exists()
        )

    def test_extractor_runs_on_llamacpp_never_docker_vllm(self):
        # Kaggle has no Docker, and surya picks vllm (Docker) on any NVIDIA GPU.
        with mock.patch.dict(os.environ, {"SURYA_INFERENCE_BACKEND": "vllm"}):
            K.run(papers=[SHEEHY], scratch=str(self.ws))
        self.assertIn("surya-backend=llamacpp", (self.out / "ingest.log").read_text())
        self.assertEqual(self.shard()["summary"]["inference_backend"], "llamacpp")

    def test_unknown_stem_is_refused(self):
        with self.assertRaises(ValueError):
            K.select(["nope"])


class EnvFactsTest(unittest.TestCase):
    def test_reads_builds_and_probes_torch(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d)
            meta = env / "conda-meta"
            meta.mkdir()
            for name, ver, build in [
                ("llama.cpp", "11860", "cuda134_h1"),
                ("pytorch", "2.13.0", "cuda129_py312_h2"),
                ("pytorch-gpu", "2.13.0", "cuda129_h3"),
                ("libtorch", "2.13.0", "cuda129_h4"),
            ]:
                (meta / f"{name}-{ver}-{build}.json").write_text(
                    json.dumps({"version": ver, "build": build})
                )
            (env / "bin").mkdir()
            py = env / "bin/python"
            py.write_text("#!/usr/bin/env bash\necho 'True 12.9'\n")
            py.chmod(py.stat().st_mode | stat.S_IXUSR)
            facts = K.env_facts(env)
        self.assertEqual(facts["pytorch"], "2.13.0 cuda129_py312_h2")
        self.assertTrue(facts["torch_cuda"] and facts["llama_cuda"])

    def test_the_operators_local_cpu_env_reads_as_cpu(self):
        env = ROOT / K.ENV_REL
        if not (env / "bin/python").exists():
            self.skipTest("local papersmith env not provisioned")
        facts = K.env_facts(env)
        self.assertFalse(facts["torch_cuda"])
        self.assertFalse(facts["llama_cuda"])
        self.assertIn("cpu", facts["llama.cpp"])


if __name__ == "__main__":
    unittest.main()
