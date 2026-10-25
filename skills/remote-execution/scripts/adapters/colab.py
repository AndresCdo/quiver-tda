#!/usr/bin/env python3
"""The Colab backend adapter — this file's own service is named here and
nowhere above the seam.

Every module above `adapter.py` (`ledger.py`, `packer.py`, `remote_cli.py`)
stays deliberately blind to what backend, if any, is behind a given worker.
This module is where that blindness ends: it is the one place permitted to
say "Colab", to spawn the one child that speaks to it, and to know that
service's own vocabulary well enough to translate it into the seam's.

Structural guarantees, held by what this file's own dependency graph can
even reach — never by convention:

1. This module imports `hashlib`, `json`, `os`, `re`, `subprocess`, `sys`,
   `tempfile` and `pathlib` — nothing else. It names no packaged SDK, and
   the one thing it shells out to is the official `colab` command line
   (`google-colab-cli`), which is the service's own headless client.

   2. Colab authentication is the CLI's own business, read by the CLI's own
    child process: it resolves `~/.config/colab-cli/token.json` from the
    `HOME` this adapter forwards, and this module never opens that file,
    never learns a path to it, and never sees a token value. There is no
    `credentials` parameter on this adapter and no `CREDENTIAL_CLI` class
    attribute, so `remote_cli._construct_adapter()` never hands it a
    credential provider at all.

   The CLI's own session STATE file (`~/.config/colab-cli/sessions.json`)
    is credential-grade too, and for a measured reason: it carries a live
    per-session access token beside the session record (spike S0). Nothing
    here reads it, copies it or prints it — every session fact this module
    uses comes from the CLI's own stdout, and the only environment this
    module ever forwards is `PATH` and `HOME`.

   The repo-credential route (S3) does not change any of that: the
   operator's token file arrives as `repo_credential_path`, and its bytes
   are read at exactly ONE expression in this module — `submit()`'s
   staging, below — then written into a per-call temp directory and
   uploaded as `git-askpass-token` (0o600, stripped, no trailing
   newline). The path is what `remote_cli` threads; the bytes never touch
   argv, `run-config.json`, the job folder, the ledger or any log.

3. Every subprocess call is `shell=False` with a list argv, an explicit
   timeout, and that same two-variable environment. A non-zero exit, an
   expired timeout, or output this module cannot honestly read is a
   refusal — `ColabAdapterError`, never a fabricated `Status`, `Submission`
   or `Fetched` the service never confirmed.

Slice status, stated so a refusal is never a mystery: this file owns the
S1 surface (registration, the static worker, `list_active()`, `cancel()`),
the S2 session lifecycle (`submit()`, `poll()`, `fetch()` — uploads,
the detached launch, the `/content/.psmith/<session>/` sentinel protocol,
downloads, release), the S3 repo-credential route
(`REPO_CREDENTIAL_CARRIER`, the `repo_credential_path` constructor
parameter, the staged askpass material), and the D13 accelerator mapping
(`COLAB_ACCELERATOR_VARIANTS`: a declared `sm_*` architecture becomes the
matching `--gpu` variant on `new`, and anything the table cannot map
refuses by name rather than silently running on CPU).

Measured against `google-colab-cli` 0.6.0, live (spike S0; evidence in
`proposals/colab-cli-spike/findings.md`):
    [name] m-... | Hardware: CPU | Variant: DEFAULT          (sessions)
    [psmith-s0] m-... | Hardware: CPU | Variant: DEFAULT | Status: IDLE
    [colab] Session 'x' not found.                            (stop, exit 0)
    [colab] Creating session 'x'... / [colab] Session READY.  (new, exit 0)
Run with any Python 3.10+ (stdlib-only):
    python3 -m unittest tests.test_remote_execution
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


def _load_adapter_seam():
    """Path-import `adapter.py`, one directory up from this file, reusing
    an already-loaded copy under `remote_execution_adapter` when one
    exists.

    Same `sys.modules`-reuse technique `kaggle.py` uses, and the same
    correctness reason: a second, separately exec'd copy of `adapter.py`
    would define a second, distinct `Adapter` class with the same name,
    and `isinstance(colab_adapter, ADAPTER.Adapter)` checks made by a
    caller holding the first copy would silently fail against an instance
    built from the second.
    """
    module_name = "remote_execution_adapter"
    if module_name in sys.modules:
        return sys.modules[module_name]
    script = Path(__file__).resolve().parent.parent / "adapter.py"
    spec = importlib.util.spec_from_file_location(module_name, script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ADAPTER = _load_adapter_seam()


class ColabAdapterError(ADAPTER.AdapterError):
    """A refusal: the service CLI failed, timed out, or answered with
    something this adapter will not guess at.

    Never raised to report a guess — only to report that this adapter
    declined to fabricate an answer the service never actually confirmed.
    """


class ColabTransportError(ColabAdapterError):
    """The RETRYABLE half of this adapter's refusals: the request died in
    flight (an expired subprocess timeout, or the CLI's own
    `Connection was lost.` transport message) rather than the service
    answering with a state.

    Only idempotent READS are retried on this class, once (S0 obligation
    4: `exec` can hang after `Connection was lost`, and retry-once is
    justified for reads alone). A launch is never retried — a second
    launch could spawn a second executor — and neither is `new`, an
    upload, an install or a stop.
    """


# The one worker this backend exposes: the operator's own Colab account.
WORKER_ID = "colab"

# The concurrent-job figure this backend claims, and the honest reason it
# is 1 rather than a discovered number: this adapter serializes its work
# on purpose (one named session per submission, one submission in flight
# per account), and the CLI reports no concurrency allowance to read.
# Revise only alongside a measured reason.
COLAB_WORKER_CAPACITY = 1

# Every session this adapter creates carries this name prefix. The CLI
# lists the ACCOUNT's sessions, not this skill's — `list_active()` claims
# only the prefixed ones, so a session some other tooling created can
# never be reported as a submission this adapter issued.
SESSION_NAME_PREFIX = "psmith-"

# The job-folder slug's own cap, chosen against the measured accepted
# name length (a 56-character name was accepted live; this construction's
# own maximum is 6 + 40 + 1 + 8 = 55).
SESSION_SLUG_MAX_CHARS = 40
SESSION_NAME_MAX_CHARS = 55

# The VM-side root every session's directory lives under, from the parent
# plan's protocol §4. A constructor parameter (below) rather than a bare
# literal, because it is the VM's mount root and the offline suite
# executes the REAL rendered templates against a temp directory standing
# in for it — no path literal here is test-only, and the production
# default is exactly the plan's.
DEFAULT_REMOTE_ROOT = "/content/.psmith"

# The token the two RENDERED asset templates carry in place of their
# session directory (`assets/colab/launch.py`, `read_state.py`), and the
# inline mkdir source below. `exec -f` has no argument channel, so the
# directory is substituted into the source before the file is executed.
SESSION_DIR_TOKEN = "__SESSION_DIR__"

# Timeout classes (parent plan D7), each its own named number:
#   control   — `sessions`, `status`, `stop`: small requests whose answer
#               the service produces immediately; failing fast is right.
#   new       — provisioning a machine, measured at ~14 s live.
#   transfer  — per-file upload/download, sized for real artifacts.
#   install   — `colab install`: its own operation class, same magnitude
#               as a transfer because it moves packages and runs pip.
#   kernel    — the `--timeout` every in-kernel helper execution passes to
#               `exec`, and the subprocess timeout is that plus slack.
COLAB_CONTROL_TIMEOUT_SECONDS = 120.0
COLAB_NEW_TIMEOUT_SECONDS = 300.0
COLAB_TRANSFER_TIMEOUT_SECONDS = 1800.0
COLAB_INSTALL_TIMEOUT_SECONDS = 1800.0
COLAB_KERNEL_TIMEOUT_SECONDS = 600.0
COLAB_SUBPROCESS_SLACK_SECONDS = 30.0

# The three distributions `executor.py` needs on the VM (measured present
# live; the probe exists for the machines where they are not).
PROBE_PACKAGES = ("nbclient", "nbformat", "jupyter_client")

# D13's declared-architecture → GPU-variant table: the `sm_*` names this
# project's dual-architecture torch builds declare, mapped to the variant
# names `colab new --gpu` accepts (all three are in the captured
# `help-new.log` surface, S0 fact 4). A declared architecture outside this
# table refuses by name — never a fallback to CPU — and TPU kinds are
# refused outright, because no `--tpu` mapping is invented here. This table
# only decides which machine arrives; the VM-side `check_accelerator()`
# remains the authority on whether that machine can run the build.
COLAB_ACCELERATOR_VARIANTS = {"sm_75": "T4", "sm_80": "A100", "sm_90": "H100"}

# The two job-folder names this adapter knows: `run-config.json` beside
# the entrypoint is what makes a submission shaped like this backend's
# protocol at all, and `runner.ipynb` is the entrypoint's own fixed name
# (jobfolder.py's constants, duplicated here the way kaggle.py duplicates
# its own — this module may not import jobfolder).
RUN_CONFIG_FILENAME = "run-config.json"
RUNNER_FILENAME = "runner.ipynb"

# The rendered/uploaded assets under `assets/colab/`.
LAUNCH_ASSET = "launch.py"
EXECUTOR_ASSET = "executor.py"
READ_STATE_ASSET = "read_state.py"

# The credential material a credentialed submission stages beside the
# executor (S3): an askpass script (uploaded verbatim; the executor makes
# it executable) and the token file it prints. The names are declared in
# THREE files by convention — this one (the uploader and the fetch-time
# refusal), `assets/colab/executor.py` (chmod, deletion, manifest
# exclusion) and `assets/runner_bootstrap.py` (the clone's own use and
# deletion) — deliberately not shared by import, for the same reason no
# module above the seam may name a backend.
REPO_CREDENTIAL_ASKPASS_FILENAME = "git-askpass.sh"
REPO_CREDENTIAL_TOKEN_FILENAME = "git-askpass-token"

# The two names `fetch()` refuses to download: the executor deletes this
# material after the run and excludes it from its manifest, so a manifest
# naming either one at the top level is a manifest this protocol never
# produces.
CREDENTIAL_MATERIAL_FILENAMES = frozenset(
    {REPO_CREDENTIAL_ASKPASS_FILENAME, REPO_CREDENTIAL_TOKEN_FILENAME}
)

# The askpass script uploaded as `git-askpass.sh`: prints the staged token
# file's bytes for whichever prompt git asks. HTTPS token auth on the
# hosts this skill targets accepts the token as the username with any
# password, so one answer serves both prompts (recorded in the slice
# plan's §4, and verified live only at S5's credential differential —
# until then this is a unit-asserted convention, never an assumption
# dressed as a measurement).
REPO_CREDENTIAL_ASKPASS_SOURCE = """#!/bin/sh
# Prints the staged repo credential for both prompts git may ask. HTTPS
# token auth on the hosts this skill targets accepts the token as the
# username with any password, so one answer serves both prompts.
cat "$(dirname "$0")/git-askpass-token"
"""

# The tokens a hand-typed launch would carry without ever routing through
# `remote_cli.py submit`. Read by `hooks/refuse_offpath_push.py`; a second
# service is covered by declaring its own tuple beside its own adapter,
# never by editing the hook. Deliberately absent: `sessions`, `status`,
# `ls` and `stop` are reads or cleanup, not launches.
PUSH_SURFACE: tuple[str, ...] = ("colab new", "colab exec", "colab run", "colab upload")

# The sessions listing's own line shape, measured in spike S0:
#     [name] m-... | Hardware: X | Variant: Y
# A machine whose name the CLI can no longer resolve is rendered `[?]`;
# it is deliberately NOT converted into a submission id below — there is
# no name to address it by.
_SESSION_LINE_RE = re.compile(r"^\[(?P<name>[^\]]+)\]\s+(?P<endpoint>\S+)\s*\|")

# The names a session may carry: lowercase alphanumerics and hyphens,
# starting with an alphanumeric. This module GENERATES exactly this shape
# (`SESSION_NAME_PREFIX` + slug + digest), so a submission id that does
# not match cannot have come from here — and the name is substituted into
# rendered sources, so accepting an arbitrary string from argv would be
# accepting an injection into a file executed on the VM. Refused at the
# boundary, before any substitution (ledger S2-J7).
_SESSION_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# The inline helper sources: rendered per submission into the temp dir,
# exactly like the two asset templates, and for the same reason — they
# must know their session directory and `exec -f` cannot tell them.
_MKDIR_SOURCE = '''\
"""Create the session's remote directory (rendered per submission)."""
import json
from pathlib import Path

SESSION_DIR = Path("__SESSION_DIR__")


def main() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"created": str(SESSION_DIR), "exists": SESSION_DIR.is_dir()}))


if __name__ == "__main__":
    main()
'''

_PROBE_SOURCE = '''\
"""Report the executor's three dependencies without importing them
(rendered per submission; an import would be the failure it reports)."""
import json
from importlib import metadata

PACKAGES = ("nbclient", "nbformat", "jupyter_client")


def main() -> None:
    found = {}
    for package in PACKAGES:
        try:
            found[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            found[package] = None
    print(json.dumps(found))


if __name__ == "__main__":
    main()
'''


def _slugify(text: str) -> str:
    """A deterministic slug from raw text — never a lookup, never state
    kept anywhere in this process. Used on the job folder's own name
    (`entrypoint.parent.name`), which is the one fact that separates two
    generated job folders before their bytes are hashed.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:SESSION_SLUG_MAX_CHARS] or "job"


def _mode_token(run_config) -> str:
    """The submit-time mode, as it enters the session name's digest.
    `run_config` is the in-memory job's opaque mapping; `--smoke` is the
    one mode `cmd_submit` ever sets (`"smoke"`), everything else is a
    full run. The mode is NOT persisted in `run-config.json`, which is
    exactly why it must be hashed here: a rehearsal and a full run of the
    same job folder are different submissions and must never collide on
    one session name.
    """
    return "smoke" if run_config.get("mode") == "smoke" else "full"


def _digest8(entrypoint_bytes: bytes, commit: str, mode: str) -> str:
    """The submission digest: `sha256(entrypoint bytes NUL commit NUL
    mode)[:8]`. The NUL separators are this construction's own
    disambiguation of the parent plan's "entrypoint bytes + commit +
    mode" prose — recorded as a refinement in the slice plan (SD1) — so
    two different triples can never hash the same concatenated byte
    string.
    """
    joined = b"\0".join((entrypoint_bytes, commit.encode("utf-8"), mode.encode("utf-8")))
    return hashlib.sha256(joined).hexdigest()[:8]


def _escape_source_literal(text: str) -> str:
    """Escape a value for inclusion inside a double-quoted Python literal
    in a rendered source file. The session directory is composed of this
    module's own validated parts (prefixed name, VM root), so this is
    belt-and-braces rather than the load-bearing check — the load-bearing
    check is `_SESSION_NAME_RE` at the boundary.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _append_note(exc: BaseException, note: str) -> None:
    """Append a cleanup note to a refusal about to be re-raised, without
    changing its type and without ever swallowing it: the caller sees the
    original failure AND the fact that cleanup also failed.
    """
    if exc.args and isinstance(exc.args[0], str):
        exc.args = (f"{exc.args[0]} [{note}]", *exc.args[1:])
    else:
        exc.args = (*exc.args, note)


class ColabAdapter(ADAPTER.Adapter):
    """The official `colab` CLI, behind the seam's six operations."""

    # Read off the CLASS by `remote_cli` exactly the way it reads
    # `CREDENTIAL_CLI` — an ordinary class attribute, never one of the
    # ABC's six operations, so this module still never has to be named by
    # anything above the seam. A backend that can stage a runner-side repo
    # credential declares it; a backend that cannot declares nothing, and
    # `--repo-credential` refuses there rather than authenticating a probe
    # whose runner still could not clone (S3/D6).
    REPO_CREDENTIAL_CARRIER = True

    def __init__(
        self,
        *,
        colab_executable: str = "colab",
        timeout: float = COLAB_CONTROL_TIMEOUT_SECONDS,
        new_timeout: float = COLAB_NEW_TIMEOUT_SECONDS,
        transfer_timeout: float = COLAB_TRANSFER_TIMEOUT_SECONDS,
        install_timeout: float = COLAB_INSTALL_TIMEOUT_SECONDS,
        kernel_timeout: float = COLAB_KERNEL_TIMEOUT_SECONDS,
        subprocess_slack: float = COLAB_SUBPROCESS_SLACK_SECONDS,
        remote_root: str = DEFAULT_REMOTE_ROOT,
        assets_dir: Path | None = None,
        repo_credential_path: str | Path | None = None,
    ) -> None:
        self._colab_executable = colab_executable
        self._control_timeout = timeout
        self._new_timeout = new_timeout
        self._transfer_timeout = transfer_timeout
        self._install_timeout = install_timeout
        self._kernel_timeout = kernel_timeout
        self._subprocess_slack = subprocess_slack
        self._remote_root = remote_root.rstrip("/")
        self._assets_dir = (
            Path(assets_dir)
            if assets_dir is not None
            else Path(__file__).resolve().parents[2] / "assets" / "colab"
        )
        # The PATH, never the bytes: the token itself is read at the one
        # staging expression in `submit()`, and a `None` here (every
        # credentialless caller) makes the whole route inert.
        self._repo_credential_path = (
            Path(repo_credential_path) if repo_credential_path is not None else None
        )

    # -- the repo credential (S3) ------------------------------------------

    def _read_repo_credential(self) -> str:
        """The ONE expression in this module that reads the credential
        bytes (D6's two-site rule: here and `jobfolder`'s probe env
        builder, nothing else skill-wide).

        `.strip()` because a trailing newline in a token file is an
        editing artifact, and an unreadable-or-empty value refuses HERE,
        naming the path — an empty credential would be uploaded as a
        token that is nothing but whitespace, a configuration accident
        this method must not launder into a VM-side clone failure after
        quota is spent.
        """
        path = self._repo_credential_path
        assert path is not None, "_read_repo_credential called with no path"
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ColabAdapterError(
                f"the repository credential at {path} could not be read: {exc}"
            ) from exc
        if not value:
            raise ColabAdapterError(
                f"the repository credential at {path} is empty after "
                "stripping whitespace; refusing to stage an empty credential "
                "(git would present it as the token)"
            )
        return value

    # -- the subprocess boundary ------------------------------------------

    def _env_for(self) -> dict[str, str]:
        """The child's WHOLE environment, from a two-name allowlist:
        `PATH` and `HOME`. Nothing else is ever forwarded.

        `HOME` is load-bearing, not convenience: the CLI authenticates
        ITSELF out of `~/.config/colab-cli/token.json`, and it resolves
        that directory from the child's own `HOME`. This adapter never
        touches that file or its contents — the child is the only party
        that does. A process with no `HOME` is refused here rather than
        passed a child that would fail authentication for a reason no
        caller could read.
        """
        home = os.environ.get("HOME")
        if not home:
            raise ColabAdapterError(
                "HOME is not set in this process's environment; the colab "
                "CLI resolves its own credential file from HOME, and "
                "forwarding a child without one only moves the failure "
                "somewhere harder to read"
            )
        return {"PATH": os.environ.get("PATH", ""), "HOME": home}

    def _run(
        self,
        argv: list[str],
        *,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess:
        """One subprocess boundary for every child this adapter starts.

        `timeout=None` means the control-plane budget. A timeout is a
        `ColabTransportError` (the request died in flight — retry-eligible
        for reads alone), and a missing executable is a refusal naming the
        exact install command: this skill's `## Environment` section in
        `SKILL.md` is where a reader would look, and the sentence lives
        here, in the one file this skill lets name a service.
        """
        effective_timeout = self._control_timeout if timeout is None else timeout
        try:
            return subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=self._env_for(),
            )
        except subprocess.TimeoutExpired as exc:
            raise ColabTransportError(
                f"{argv[0]} timed out after {effective_timeout}s: refusing to "
                "guess at a state this process never confirmed"
            ) from exc
        except OSError as exc:
            remedy = ""
            if argv and argv[0] == self._colab_executable:
                remedy = (
                    f" — this adapter shells out to the {argv[0]!r} command "
                    "line, which arrives with `uv tool install --python 3.14 "
                    'google-colab-cli --with "jupyter-kernel-client<1"`; '
                    "install it and make sure the tool bin directory it "
                    "reports is on PATH"
                )
            raise ColabAdapterError(f"could not run {argv[0]}: {exc}{remedy}") from exc

    def _run_read(
        self,
        argv: list[str],
        *,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess:
        """`_run`, with the ONE retry this adapter ever performs: an
        idempotent read that died in flight is retried once, then
        refused. The transport class is explicit — an expired subprocess
        timeout, or the CLI's own `Connection was lost.` message in the
        child's output — and nothing about a state the service actually
        ANSWERED is ever retried into a different answer.
        """
        retried = False
        while True:
            try:
                result = self._run(argv, timeout=timeout)
            except ColabTransportError:
                if retried:
                    raise
                retried = True
                continue
            combined = f"{result.stdout}\n{result.stderr}".lower()
            if not retried and "connection was lost" in combined:
                retried = True
                continue
            return result

    def _parse_json_line(self, result: subprocess.CompletedProcess, action: str) -> dict:
        """Read the one compact JSON line a helper execution prints as its
        LAST non-empty output line. The CLI's own surrounding prose is
        tolerated, never parsed; a non-zero exit, no output, a final line
        that is not JSON, or JSON that is not an object are each a
        refusal — never a half-read state.
        """
        if result.returncode != 0:
            raise ColabAdapterError(
                f"{action} refused (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise ColabAdapterError(
                f"{action} printed nothing this adapter can read: "
                f"{result.stderr.strip()}"
            )
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise ColabAdapterError(
                f"{action}: the last output line is not JSON ({exc}): "
                f"{lines[-1]!r}"
            ) from exc
        if not isinstance(payload, dict):
            raise ColabAdapterError(
                f"{action}: the JSON line is {type(payload).__name__}, not an object"
            )
        return payload

    # -- session vocabulary -----------------------------------------------

    def _session_dir(self, session_name: str) -> str:
        return f"{self._remote_root}/{session_name}"

    def _session_name_from(self, submission_id: str) -> str:
        """Split `"<worker>/<session-name>"` and validate BOTH halves: the
        worker must be this adapter's own, and the name must match the
        shape this adapter generates (`SESSION_NAME_PREFIX` + slug +
        digest). The name is substituted into rendered sources that run
        on the VM, so anything else is refused here, before any
        substitution (ledger S2-J7).
        """
        worker, separator, session_name = submission_id.partition("/")
        if not separator or not session_name:
            raise ColabAdapterError(
                f"{submission_id!r} is not '<worker>/<session-name>'; "
                "refusing to guess which session this names"
            )
        if worker != WORKER_ID:
            raise ColabAdapterError(
                f"{submission_id!r} names worker {worker!r}, but this adapter "
                f"issues ids for {WORKER_ID!r} only"
            )
        if (
            len(session_name) > SESSION_NAME_MAX_CHARS
            or not session_name.startswith(SESSION_NAME_PREFIX)
            or _SESSION_NAME_RE.match(session_name) is None
        ):
            raise ColabAdapterError(
                f"{submission_id!r} carries {session_name!r}, which is not a "
                "session name this adapter generates; refusing before that "
                "name could reach a rendered source"
            )
        return session_name

    def _status_line(self, stdout: str, session_name: str) -> tuple[str, str] | None:
        """The measured status line for `session_name`, or `None` when the
        output carries no such line. Returns `(line, endpoint)`.
        """
        for line in stdout.splitlines():
            match = _SESSION_LINE_RE.match(line.strip())
            if match is None:
                continue
            if match.group("name") != session_name:
                continue
            return line.strip(), match.group("endpoint")
        return None

    @staticmethod
    def _looks_like_not_found(result: subprocess.CompletedProcess) -> bool:
        """The CLI's own "no such session" family, matched on OUTPUT and
        never on the exit code (measured: `stop` on an unknown session
        exits 0 — S0 obligation 3).
        """
        combined = f"{result.stdout}\n{result.stderr}".lower()
        return "not found" in combined

    @staticmethod
    def _service_prose_only(
            result: subprocess.CompletedProcess) -> subprocess.CompletedProcess:
        """The same result with the HELPER'S PAYLOAD LINE removed, so the
        wording test above reads only what the service itself said.

        A helper execution prints one compact JSON line last
        (`_parse_json_line`), and that line carries the RUN's own words --
        `status.json` verbatim, the error text the executor recorded
        included. `_looks_like_not_found()` matches its phrase anywhere in
        the output, so scanning that line let the run answer a question
        about the SERVICE: a run whose recorded error happened to contain
        that phrase was reported as a vanished session. Measured: changing
        only the wording of a recorded error, every other byte of the
        scenario identical, flipped the verdict from `failed` to
        `unknown` -- and `unknown` means evidence is MISSING, so a caller
        waiting for a terminal state keeps polling instead of stopping to
        look. The wording test itself is right to read output rather than
        the exit code (measured: 0 even for a session that does not
        exist); what was wrong is which output it was allowed to read.

        The last line is dropped ONLY when it parses as JSON. When the
        session really is gone there is no payload, and the service's own
        sentence IS the last line -- dropping it unconditionally would
        blind the very check this protects.
        """
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if lines:
            try:
                json.loads(lines[-1])
            except ValueError:  # not the payload, so it is the service talking
                pass
            else:
                lines = lines[:-1]
        return subprocess.CompletedProcess(
            result.args, result.returncode, "\n".join(lines), result.stderr
        )

    # -- rendering and helper execution -----------------------------------

    def _render(self, source: str, session_name: str) -> str:
        return source.replace(
            SESSION_DIR_TOKEN, _escape_source_literal(self._session_dir(session_name))
        )

    def _render_asset(self, asset_name: str, session_name: str, destination: Path) -> Path:
        """Render one `assets/colab/` template for this submission into
        `destination`. A missing asset is a refusal naming the path —
        never an empty file that would run as a no-op helper.
        """
        asset = self._assets_dir / asset_name
        try:
            source = asset.read_text(encoding="utf-8")
        except OSError as exc:
            raise ColabAdapterError(
                f"cannot read the {asset_name!r} template at {asset}: {exc}"
            ) from exc
        destination.write_text(self._render(source, session_name), encoding="utf-8")
        return destination

    def _write_helper(self, source: str, destination: Path, session_name: str) -> Path:
        destination.write_text(self._render(source, session_name), encoding="utf-8")
        return destination

    def _exec_result(
        self,
        helper: Path,
        session_name: str,
        *,
        retry_read: bool = False,
    ) -> subprocess.CompletedProcess:
        """One in-kernel helper execution: `exec -f <rendered file>`, with
        the kernel budget passed to the CLI explicitly (the CLI's own
        default is 30 s — never reachable from here) and the subprocess
        timeout set to that budget plus slack, so the CLI's own timeout
        fires first and its message is the one a caller reads.
        """
        argv = [
            self._colab_executable,
            "exec",
            "-s",
            session_name,
            "-f",
            str(helper),
            "--timeout",
            str(self._kernel_timeout),
        ]
        timeout = self._kernel_timeout + self._subprocess_slack
        runner = self._run_read if retry_read else self._run
        return runner(argv, timeout=timeout)

    # -- lifecycle pieces --------------------------------------------------

    def _refuse_existing_session(self, session_name: str) -> None:
        """S0 obligation 1: `colab new` on an existing name REPLACES the
        machine and orphans the old one, which has no CLI release path
        and burns compute until idle reclaim. The listing is read BEFORE
        `new`, and a name already on it is a refusal — never a replace.
        """
        result = self._run_read([self._colab_executable, "sessions"])
        if result.returncode != 0:
            raise ColabAdapterError(
                f"colab sessions refused (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        for line in result.stdout.splitlines():
            match = _SESSION_LINE_RE.match(line.strip())
            if match is None or match.group("name") != session_name:
                continue
            raise ColabAdapterError(
                f"a session named {session_name!r} already exists on this "
                "account, and `colab new` would REPLACE it — silently "
                "orphaning the running machine, which has no CLI release "
                "path. Fetch, stop, or let that session expire before "
                "resubmitting this same job."
            )

    def _accelerator_variant(self, accelerator: object) -> str | None:
        """The `--gpu` variant a declared `accelerator` block maps to, or
        `None` when the run-config declares no block at all (CPU, exactly
        as before this existed).

        Fail-closed in every direction (SD18/D13), because every failure
        here is one the VM-side gate could not catch except after session
        spend: `kind` must be `cuda` (a TPU refuses — no `--tpu` mapping
        is invented), exactly one architecture string is required (zero
        or two cannot choose a machine, and a non-list is not a shape
        this protocol writes), and an architecture absent from
        `COLAB_ACCELERATOR_VARIANTS` refuses naming both the declared
        value and the table. The declared block still travels unchanged
        to the VM, where `check_accelerator()` remains the authority: it
        compares the declared `sm_*` names against the torch build
        actually installed on the arriving machine.
        """
        if accelerator is None:
            return None
        if not isinstance(accelerator, dict):
            raise ColabAdapterError(
                f"run-config.json's 'accelerator' block is "
                f"{type(accelerator).__name__}, not an object; refusing to "
                "guess at which machine this job needs"
            )
        kind = accelerator.get("kind")
        if kind != "cuda":
            raise ColabAdapterError(
                f"run-config.json declares accelerator kind {kind!r}, and "
                "this backend maps only 'cuda' architectures to a GPU "
                "variant (D13); a TPU is never requested here. Refusing "
                "rather than silently running the job on CPU."
            )
        architectures = accelerator.get("architectures")
        if (
            not isinstance(architectures, list)
            or len(architectures) != 1
            or not isinstance(architectures[0], str)
        ):
            raise ColabAdapterError(
                f"run-config.json declares accelerator architectures "
                f"{architectures!r}; exactly one architecture string is "
                "required to choose a GPU variant. Refusing rather than "
                "guessing."
            )
        architecture = architectures[0]
        variant = COLAB_ACCELERATOR_VARIANTS.get(architecture)
        if variant is None:
            raise ColabAdapterError(
                f"run-config.json declares accelerator architecture "
                f"{architecture!r}, which is not in this backend's variant "
                f"table {COLAB_ACCELERATOR_VARIANTS!r}; refusing rather than "
                "silently running the job on CPU."
            )
        return variant

    def _new_session(
        self, session_name: str, *, accelerator_variant: str | None = None
    ) -> None:
        """Provision one machine, requiring the measured positive
        confirmation (`Session READY`) rather than a bare exit code. A
        mapped accelerator is requested with `--gpu <variant>`; the flag
        and all three mapped variants are in the captured `help-new.log`
        surface (S0 fact 4).
        """
        argv = [self._colab_executable, "new", "-s", session_name]
        if accelerator_variant is not None:
            argv += ["--gpu", accelerator_variant]
        result = self._run(argv, timeout=self._new_timeout)
        combined = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or "session ready" not in combined.lower():
            raise ColabAdapterError(
                f"`new` for {session_name!r} did not report READY "
                f"(exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

    def _endpoint_for(self, session_name: str) -> str:
        """The `m-…` endpoint token from the measured `status` line. An
        unparseable endpoint refuses the launch BEFORE any upload: a
        session without keep-alive idles out mid-run and wastes the run.
        """
        result = self._run_read(
            [self._colab_executable, "status", "-s", session_name]
        )
        if self._looks_like_not_found(result):
            raise ColabAdapterError(
                f"the session {session_name!r} vanished between `new` and "
                "`status`; refusing to launch into a machine this process "
                "cannot observe"
            )
        found = self._status_line(result.stdout, session_name)
        if found is None:
            raise ColabAdapterError(
                f"colab status for {session_name!r} printed no line this "
                f"adapter can read (exit {result.returncode}): "
                f"{result.stdout.strip() or result.stderr.strip()}"
            )
        return found[1]

    def _spawn_keep_alive(self, endpoint: str, session_name: str) -> None:
        """Best-effort keep-alive, detached, output to DEVNULL (parent
        plan D9). A spawn failure is deliberately NOT a refusal: the plan
        calls this best-effort, the session is already usable, and the
        endpoint above was the load-bearing parse. The invocation shape
        is the plan's (`keep-alive <endpoint> <name>`); the live daemon
        probe measured on this CLI was the module-form of the same hidden
        command, and S5 verifies this form against the real service
        (ledger S2-J5).
        """
        argv = [self._colab_executable, "keep-alive", endpoint, session_name]
        try:
            subprocess.Popen(
                argv,
                env=self._env_for(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            return

    def _upload(self, local: Path, remote: str, session_name: str) -> None:
        if not local.is_file():
            raise ColabAdapterError(
                f"cannot upload {local}: not a readable regular file"
            )
        result = self._run(
            [
                self._colab_executable,
                "upload",
                "-s",
                session_name,
                str(local),
                remote,
            ],
            timeout=self._transfer_timeout,
        )
        if result.returncode != 0:
            raise ColabAdapterError(
                f"upload of {local.name!r} refused (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

    def _ensure_dependencies(self, probe: Path, session_name: str) -> None:
        """D10: probe, install only what is missing, re-probe once, and
        refuse a still-broken runtime — after a stop, never before one.
        """
        payload = self._parse_json_line(
            self._exec_result(probe, session_name), f"dependency probe for {session_name!r}"
        )
        missing = [package for package in PROBE_PACKAGES if payload.get(package) is None]
        if not missing:
            return
        install = self._run(
            [self._colab_executable, "install", "-s", session_name, *missing],
            timeout=self._install_timeout,
        )
        if install.returncode != 0:
            raise ColabAdapterError(
                f"installing {missing!r} on {session_name!r} refused "
                f"(exit {install.returncode}): "
                f"{install.stderr.strip() or install.stdout.strip()}"
            )
        reparsed = self._parse_json_line(
            self._exec_result(probe, session_name),
            f"dependency re-probe for {session_name!r}",
        )
        still = [package for package in PROBE_PACKAGES if reparsed.get(package) is None]
        if still:
            raise ColabAdapterError(
                f"the VM still cannot import {still!r} after `colab install`; "
                "refusing to launch a run that would die in its executor. "
                "Install them yourself (`colab install -s "
                f"{session_name} {' '.join(still)}`) and resubmit"
            )

    def _launch(self, launcher: Path, session_name: str) -> None:
        """Run the rendered launcher and require its receipt line. Never
        retried: a retry could spawn a second executor.
        """
        payload = self._parse_json_line(
            self._exec_result(launcher, session_name),
            f"launch for {session_name!r}",
        )
        if not isinstance(payload.get("launched_pid"), int):
            raise ColabAdapterError(
                f"the launcher for {session_name!r} did not report a pid: "
                f"{payload!r}"
            )

    def _stop_session(self, session_name: str) -> None:
        """`colab stop -s <session>`, output-interpreted (measured:
        unknown sessions print "not found" and exit 0 — the exit code is
        not truth, S0 obligation 3).
        """
        argv = [self._colab_executable, "stop", "-s", session_name]
        result = self._run(argv)
        if self._looks_like_not_found(result):
            return
        if result.returncode != 0:
            raise ColabAdapterError(
                f"stop for {session_name!r} refused (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

    def _stop_session_quietly(self, session_name: str) -> str:
        """Best-effort cleanup for a failure path: attempt the stop and
        return a note describing a FAILED cleanup, or `""` when the stop
        succeeded or the session was already gone. Never raises — the
        caller is already unwinding a primary failure.
        """
        try:
            self._stop_session(session_name)
        except ColabAdapterError as exc:
            return f"session cleanup also failed: {exc}"
        return ""

    # -- the seam's six operations ----------------------------------------

    def workers(self) -> list["ADAPTER.Worker"]:
        """This backend's one worker, stated rather than discovered.

        No subprocess, no network, no credential read: this backend's
        unit of capacity is the operator's single account, its sessions
        are serialized by this adapter, and a `workers()` that dialed the
        service would make `packer`'s own capacity path depend on the
        network for a figure no call could change.
        """
        return [ADAPTER.Worker(id=WORKER_ID, capacity=COLAB_WORKER_CAPACITY)]

    def submit(self, job: "ADAPTER.Job") -> "ADAPTER.Submission":
        """The full session lifecycle, in the parent plan's own order:
        job-folder checks → `new` → endpoint → keep-alive → remote mkdir →
        uploads (plus the credential material, when one is configured —
        after the three payload uploads, before the probe) → dependency
        probe (install only what is missing) → the detached launch → the
        submission receipt.

        The credential bytes are read ONCE, before any network call at
        all (S3/D6): a bad path refuses before a session is even checked
        for, let alone uploaded to. The bytes are then written into the
        same per-call temp dir the rendered helpers use — never into the
        job folder, never into `run-config.json` — and both files die
        with the call after being uploaded.

        Everything after the `new` INVOCATION sits inside one cleanup
        boundary: any failure attempts a stop, and a cleanup that itself
        fails is appended to the refusal rather than swallowing it (the
        parent plan's D9 says "any failure after `colab new`", which
        includes `new`'s own timeouts and its missing-READY case — the
        ledger's S2-J2). The stop is a measured no-op when no session
        exists, so the boundary can start at the invocation without
        inventing a session that was never created.
        """
        entrypoint = Path(job.entrypoint)
        run_config_path = entrypoint.parent / RUN_CONFIG_FILENAME
        if not run_config_path.is_file():
            raise ColabAdapterError(
                f"{entrypoint} has no {RUN_CONFIG_FILENAME} sibling: this "
                "backend admits only the generated job-folder shape, and a "
                "bare notebook has no session protocol to run. Generate one "
                "with `generate-job --service colab` and submit its "
                f"{RUNNER_FILENAME}"
            )
        try:
            run_config_text = run_config_path.read_text(encoding="utf-8")
            parsed_run_config = json.loads(run_config_text)
        except (OSError, json.JSONDecodeError) as exc:
            raise ColabAdapterError(
                f"cannot read {run_config_path}: {exc}"
            ) from exc
        if not isinstance(parsed_run_config, dict):
            raise ColabAdapterError(
                f"{run_config_path} is not a JSON object; refusing to guess "
                "at a run configuration"
            )
        commit = parsed_run_config.get("commit")
        if not isinstance(commit, str) or not commit:
            raise ColabAdapterError(
                f"{run_config_path} carries no usable 'commit' string; the "
                "submission digest is built from it and a guessed pin would "
                "name the wrong session"
            )
        # D13/S4: the declared accelerator decides which machine arrives,
        # and the decision is made BEFORE any CLI call at all — an
        # unmappable declaration refuses here, while refusing is free.
        accelerator_variant = self._accelerator_variant(
            parsed_run_config.get("accelerator")
        )
        try:
            entrypoint_bytes = entrypoint.read_bytes()
        except OSError as exc:
            raise ColabAdapterError(f"cannot read {entrypoint}: {exc}") from exc

        mode = _mode_token(job.run_config)
        digest = _digest8(entrypoint_bytes, commit, mode)
        session_name = f"{SESSION_NAME_PREFIX}{_slugify(entrypoint.parent.name)}-{digest}"

        # S3/D6: the credential bytes are read once, here — before the
        # session pre-check and before any upload — so a bad path refuses
        # while refusing still costs nothing, and the stripped value is
        # carried in this local until it is written into the temp dir.
        credential_token = (
            self._read_repo_credential()
            if self._repo_credential_path is not None
            else None
        )

        self._refuse_existing_session(session_name)

        if job.run_config:
            merged = dict(parsed_run_config)
            merged.update(dict(job.run_config))
            staged_run_config_text = json.dumps(merged)
        else:
            staged_run_config_text = run_config_text

        with tempfile.TemporaryDirectory(prefix="psmith-colab-session-") as raw_tmp:
            tmp = Path(raw_tmp)
            # Both rendered templates are materialized here (parent plan
            # §4's submit step 5); `poll()`/`fetch()` render their own
            # read_state copies at their own call sites, each inside a
            # temp dir that dies with the call.
            launcher = self._render_asset(LAUNCH_ASSET, session_name, tmp / LAUNCH_ASSET)
            self._render_asset(READ_STATE_ASSET, session_name, tmp / READ_STATE_ASSET)
            mkdir_helper = self._write_helper(_MKDIR_SOURCE, tmp / "remote-mkdir.py", session_name)
            probe_helper = self._write_helper(
                _PROBE_SOURCE, tmp / "dependency-probe.py", session_name
            )
            staged_run_config = tmp / RUN_CONFIG_FILENAME
            staged_run_config.write_text(staged_run_config_text, encoding="utf-8")

            try:
                self._new_session(session_name, accelerator_variant=accelerator_variant)
                endpoint = self._endpoint_for(session_name)
                self._spawn_keep_alive(endpoint, session_name)

                payload = self._parse_json_line(
                    self._exec_result(mkdir_helper, session_name),
                    f"remote mkdir for {session_name!r}",
                )
                if payload.get("exists") is not True:
                    raise ColabAdapterError(
                        f"the remote mkdir helper did not confirm the session "
                        f"directory: {payload!r}"
                    )

                self._upload(self._assets_dir / EXECUTOR_ASSET, f"{self._session_dir(session_name)}/{EXECUTOR_ASSET}", session_name)
                self._upload(staged_run_config, f"{self._session_dir(session_name)}/{RUN_CONFIG_FILENAME}", session_name)
                self._upload(entrypoint, f"{self._session_dir(session_name)}/{entrypoint.name}", session_name)

                # S3/D6 staging: the askpass script (verbatim) and the
                # token file (stripped bytes, 0o600, no trailing newline)
                # go up AFTER the payload and BEFORE the probe. The local
                # copies live in `tmp` and die with this call; the job
                # folder and `run-config.json` are never written.
                if credential_token is not None:
                    askpass_local = tmp / REPO_CREDENTIAL_ASKPASS_FILENAME
                    askpass_local.write_text(
                        REPO_CREDENTIAL_ASKPASS_SOURCE, encoding="utf-8"
                    )
                    token_local = tmp / REPO_CREDENTIAL_TOKEN_FILENAME
                    token_local.write_bytes(credential_token.encode("utf-8"))
                    os.chmod(token_local, 0o600)
                    self._upload(
                        askpass_local,
                        f"{self._session_dir(session_name)}/{REPO_CREDENTIAL_ASKPASS_FILENAME}",
                        session_name,
                    )
                    self._upload(
                        token_local,
                        f"{self._session_dir(session_name)}/{REPO_CREDENTIAL_TOKEN_FILENAME}",
                        session_name,
                    )

                self._ensure_dependencies(probe_helper, session_name)
                self._launch(launcher, session_name)
            except BaseException as exc:  # noqa: BLE001 - D9's cleanup boundary
                note = self._stop_session_quietly(session_name)
                if note:
                    _append_note(exc, note)
                raise

        return ADAPTER.Submission(id=f"{job.worker}/{session_name}", worker=job.worker)

    def poll(self, submission_id: str) -> "ADAPTER.Status":
        """One honest status, translated into the seam's vocabulary, never
        the service's own text (the parent plan's D8 table, exactly).

        A session gone mid-flight is `unknown` — evidence is MISSING, not
        negative — including the case where it vanishes between the
        `status` read and the state read (ledger S2-J6). `status` and the
        state read are the two idempotent reads this adapter retries
        once; neither is ever retried into a different answer, because
        the same input is re-asked, not a new question.
        """
        session_name = self._session_name_from(submission_id)
        status_result = self._run_read(
            [self._colab_executable, "status", "-s", session_name]
        )
        if self._looks_like_not_found(status_result):
            return ADAPTER.Status(state="unknown", detail="session not found")
        found = self._status_line(status_result.stdout, session_name)
        if found is None:
            raise ColabAdapterError(
                f"colab status for {submission_id!r} printed no line this "
                f"adapter can read (exit {status_result.returncode}): "
                f"{status_result.stdout.strip() or status_result.stderr.strip()}"
            )
        line = found[0]

        with tempfile.TemporaryDirectory(prefix="psmith-colab-read-") as raw_tmp:
            reader = self._render_asset(
                READ_STATE_ASSET, session_name, Path(raw_tmp) / READ_STATE_ASSET
            )
            read_result = self._exec_result(reader, session_name, retry_read=True)
        if self._looks_like_not_found(self._service_prose_only(read_result)):
            return ADAPTER.Status(state="unknown", detail="session not found")
        payload = self._parse_json_line(read_result, f"state read for {submission_id!r}")

        status = payload.get("status")
        if status is not None:
            if not isinstance(status, dict):
                raise ColabAdapterError(
                    f"{submission_id!r}: status.json is not a JSON object: {status!r}"
                )
            exit_code = status.get("exitCode")
            if isinstance(exit_code, bool) or not isinstance(exit_code, int):
                raise ColabAdapterError(
                    f"{submission_id!r}: status.json carries no usable "
                    f"exitCode: {status!r}"
                )
            if exit_code == 0:
                return ADAPTER.Status(state="complete", detail=line)
            # The executor records WHY beside the exit code, already
            # bounded at the writer (`ERROR_MAX_CHARS`, so a runaway
            # traceback cannot turn a completion signal into megabytes).
            # Reporting the number alone left that field written and read
            # by nobody, and left the caller with a digit to go digging
            # from -- measured: a run whose notebook could not start
            # surfaced as `unit process exited 1` beside a log holding one
            # unrelated warning, with the reason sitting in `status.json`
            # the whole time. A non-string or blank `error` is simply
            # absent: this reports what the run recorded, and never
            # invents a reason it did not.
            detail = f"unit process exited {exit_code}"
            recorded = status.get("error")
            if isinstance(recorded, str) and recorded.strip():
                detail = f"{detail}: {recorded.strip()}"
            return ADAPTER.Status(state="failed", detail=detail)

        launch = payload.get("launch")
        if launch is not None:
            pid = launch.get("pid") if isinstance(launch, dict) else None
            return ADAPTER.Status(state="running", detail=f"pid {pid}")
        return ADAPTER.Status(state="queued", detail=line)

    def fetch(self, submission_id: str, into: Path) -> "ADAPTER.Fetched":
        """Materialize the run's working-directory capture under `into`,
        completely or as completely as it exists, then release the
        session when the run is terminal (the parent plan's D9/D12).

        The manifest is downloaded entry by entry (the CLI has no
        directory transfer), each entry validated as a relative,
        non-escaping path first — and refused outright when it names this
        protocol's own staged credential material at the top level
        (S3/D6). The release runs only AFTER the downloads, and only for
        a run whose `status.json` exists — whatever its exit code,
        because the run is over either way; a session gone at read time
        is a refusal naming it, and a refusal to stop fails the fetch
        only after the bytes are already local.
        """
        session_name = self._session_name_from(submission_id)
        into = Path(into)
        into.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="psmith-colab-read-") as raw_tmp:
            reader = self._render_asset(
                READ_STATE_ASSET, session_name, Path(raw_tmp) / READ_STATE_ASSET
            )
            read_result = self._exec_result(reader, session_name, retry_read=True)
        if self._looks_like_not_found(self._service_prose_only(read_result)):
            raise ColabAdapterError(
                f"the session for {submission_id!r} no longer exists; it may "
                "already have been released by a terminal fetch, or stopped "
                "outside this skill. The ledger's own fold is the completion "
                "authority — this call will not invent one."
            )
        payload = self._parse_json_line(read_result, f"state read for {submission_id!r}")

        manifest = payload.get("files")
        if manifest is None:
            entries: list[str] = []
        elif isinstance(manifest, list) and all(isinstance(entry, str) for entry in manifest):
            entries = list(manifest)
        else:
            raise ColabAdapterError(
                f"{submission_id!r}: files.json is not a list of strings: "
                f"{manifest!r}"
            )
        for entry in entries:
            candidate = PurePosixPath(entry)
            if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
                raise ColabAdapterError(
                    f"{submission_id!r}: manifest entry {entry!r} is not a "
                    "safe relative path; refusing before any download"
                )
            # S3/D6, defense in depth: the executor deletes the staged
            # askpass material after the run and excludes both names from
            # its manifest at the top level, so a manifest naming either
            # one is a shape this protocol never produces — refusing here
            # keeps a credential file from being downloaded even if a
            # future executor regressed. The same basename under a
            # subdirectory is a product of the run, not protocol material,
            # and does NOT refuse.
            if candidate.parts[0] in CREDENTIAL_MATERIAL_FILENAMES:
                raise ColabAdapterError(
                    f"{submission_id!r}: manifest entry {entry!r} names this "
                    "protocol's own credential material; the executor deletes "
                    "both staged names after the run and never lists them, so "
                    "refusing before any download"
                )

        materialized: list[str] = []
        for entry in sorted(entries):
            local = into / entry
            local.parent.mkdir(parents=True, exist_ok=True)
            remote = f"{self._session_dir(session_name)}/{entry}"
            result = self._run(
                [
                    self._colab_executable,
                    "download",
                    "-s",
                    session_name,
                    remote,
                    str(local),
                ],
                timeout=self._transfer_timeout,
            )
            if result.returncode != 0:
                raise ColabAdapterError(
                    f"download of {entry!r} for {submission_id!r} refused "
                    f"(exit {result.returncode}): "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
            materialized.append(entry)

        status = payload.get("status")
        complete = False
        terminal = status is not None
        if terminal:
            if not isinstance(status, dict):
                raise ColabAdapterError(
                    f"{submission_id!r}: status.json is not a JSON object: {status!r}"
                )
            exit_code = status.get("exitCode")
            if isinstance(exit_code, bool) or not isinstance(exit_code, int):
                raise ColabAdapterError(
                    f"{submission_id!r}: status.json carries no usable "
                    f"exitCode: {status!r}"
                )
            complete = exit_code == 0

        if terminal:
            self._stop_session(session_name)

        return ADAPTER.Fetched(path=into, complete=complete, files=tuple(sorted(materialized)))

    def cancel(self, submission_id: str) -> None:
        """`colab stop -s <session>`, addressed by the session name the
        submission id carries. No caller in the nine-command roster
        invokes this operation on its own initiative (`reconcile` reports
        orphans, never cancels them); it exists for an explicit caller
        and for tests.
        """
        session_name = self._session_name_from(submission_id)
        self._stop_session(session_name)

    def list_active(self, worker: str) -> list[str]:
        """Submission ids this adapter issued whose sessions still exist,
        from `colab sessions` (measured shape in this module's docstring).

        Only names carrying this adapter's own prefix are claimed — the
        CLI lists the ACCOUNT's sessions, so a session some other tooling
        created is not this adapter's to report. A `[?]` machine is
        skipped deliberately: the CLI can no longer resolve a name for
        it, and fabricating one would make `reconcile` claim a session
        this skill can neither stop nor fetch.
        """
        result = self._run([self._colab_executable, "sessions"])
        if result.returncode != 0:
            raise ColabAdapterError(
                f"colab sessions refused (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        active: list[str] = []
        for line in result.stdout.splitlines():
            match = _SESSION_LINE_RE.match(line.strip())
            if match is None:
                continue
            name = match.group("name")
            if name == "?" or not name.startswith(SESSION_NAME_PREFIX):
                continue
            active.append(f"{worker}/{name}")
        return active


def _declared_capacity() -> tuple[int, int]:
    """The engine's declared-capacity channel (`adapter.py`'s fourth
    registry): the same static fact `workers()` already declares — one
    operator account, capacity one — answered from constants, per that
    registry's own contract (no network, nothing guessed). A subprocess
    here would be a lie about a figure that is constant by construction."""
    return (1, COLAB_WORKER_CAPACITY)


ADAPTER.register("colab", ColabAdapter)
ADAPTER.register_declared_capacity("colab", _declared_capacity)
