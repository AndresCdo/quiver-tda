"""paper_full_text: fills the `full-text` role `papersmith.yaml` and
`paper_resolve.ROLES` both already declared and neither ever wired
(`the-pdf-arrives-or-the-operator-is-told`). The skill fetches a citation's
own PDF itself, keyless, over the SAME `urllib` client `paper_resolve.py`
already owns -- no second HTTP path anywhere in this module.

Reachability is measured, never assumed: this module never re-resolves an
identifier and never guesses a URL. It reads the ONE field `paper_resolve`'s
own parsers already computed and cached at `resolve` time --
`full_text_url` -- off the metadata blob `resolve` already wrote to disk.
A cached record with no `full_text_url` is reported unobtainable BY NAME
(`FULL_TEXT_URL_ABSENT` names the identifier, title and resolver), never
silently skipped.

The PDF lands as a LOOSE file directly under `guidance/<section-id>/` --
exactly the shape `paper-ingestion`'s own contract discovers as a source
root (`.claude/skills/paper-ingestion/SKILL.md`, "Exactly one level down":
a folder nested inside a source root is never scanned). `resolve_
destination` enforces this structurally: `cite_key` is guarded against any
path separator, so the destination's parent can only ever be
`guidance/<section-id>/` itself, never a subfolder of it.

Public surface:

    resolve_destination(guidance_dir, section_id, cite_key) -> Path
        (raises CITE_KEY_MALFORMED / GUIDANCE_OUTSIDE_REPOSITORY)
    write_full_text(destination, raw)         -> None (raises FULL_TEXT_FILE_PRESENT)
    fetch_full_text(paper_dir, guidance_dir, *, section_id, metadata_digest,
                     cite_key, config)         -> dict
        (raises METADATA_NOT_CACHED / FULL_TEXT_URL_ABSENT / RESOLVER_ROLE_EMPTY /
         FULL_TEXT_FILE_PRESENT / RESOLVER_UNREACHABLE / IDENTIFIER_UNRESOLVED /
         FULL_TEXT_NOT_A_PDF)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_resolve  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

#: The exact magic bytes every real PDF starts with. This is the load-
#: bearing check that makes "measured, never assumed" true even for a URL
#: that DOES resolve: an OpenAlex `oa_url` sometimes lands on a repository
#: splash page rather than the raw PDF bytes, so a 200 response alone is
#: not proof of a fetched PDF -- only these bytes are.
_PDF_MAGIC = b"%PDF"

#: `cite_key` becomes the output filename's stem (`<cite_key>.pdf`); a path
#: separator inside it would be the one way this module could ever write
#: outside `guidance/<section-id>/` directly, or nest a subfolder under it
#: -- both `paper-ingestion`'s own contract forbids.
_PATH_SEPARATORS = ("/", "\\")


def _validate_cite_key(cite_key: str) -> None:
    if not cite_key or cite_key in (".", "..") or any(sep in cite_key for sep in _PATH_SEPARATORS):
        raise Refused(
            "CITE_KEY_MALFORMED",
            f"{cite_key!r} is not a safe filename stem for a full-text PDF",
        )


def resolve_destination(guidance_dir: Path, section_id: str, cite_key: str) -> Path:
    """`guidance/<section_id>/<cite_key>.pdf` -- always a loose file
    directly inside the section's own citation folder, never a subfolder.

    `section_id` is guarded the same way `paper_guidance.resolve_
    guidance_dir` already guards `--guidance` itself: reuses
    `GUIDANCE_OUTSIDE_REPOSITORY` for the identical fact ("this path does
    not resolve as a direct child of guidance_dir") one level deeper,
    rather than inventing a second code for the same condition.
    `cite_key` is guarded separately (`CITE_KEY_MALFORMED`) since a path
    separator inside IT, not `section_id`, is what would actually create
    the forbidden subfolder or escape the section folder entirely.
    """
    _validate_cite_key(cite_key)
    resolved_guidance = guidance_dir.resolve()
    section_dir = (guidance_dir / section_id).resolve()
    try:
        relative = section_dir.relative_to(resolved_guidance)
    except ValueError:
        relative = None
    if relative is None or len(relative.parts) != 1:
        raise Refused(
            "GUIDANCE_OUTSIDE_REPOSITORY",
            f"{section_dir} does not resolve as a direct child of {resolved_guidance}",
        )
    return section_dir / f"{cite_key}.pdf"


def _require_destination_absent(destination: Path) -> None:
    """Refuses `FULL_TEXT_FILE_PRESENT` (work-state) when `destination`
    already exists -- this is the first path in this CLI that writes
    outside `paper/`, so it earns the same "never overwrite silently"
    discipline `paper_block.substitute`'s own `BLOCK_HAND_EDITED` guard
    already holds `main.tex` to, rather than a laxer rule just because the
    destination is new. Called BEFORE the network fetch in `fetch_
    full_text`, so a repeat fetch of an already-placed PDF spends no HTTP
    round-trip on a byte string it would refuse to keep anyway.
    """
    if destination.exists():
        raise Refused(
            "FULL_TEXT_FILE_PRESENT",
            f"{destination} already exists; refusing to overwrite it silently",
        )


def write_full_text(destination: Path, raw: bytes) -> None:
    """Writes `raw` to `destination`, creating its parent folder if absent.
    Re-checks `_require_destination_absent` as a last-write defense against
    a destination that appeared between `fetch_full_text`'s own early check
    and this call, rather than trusting that earlier check alone."""
    _require_destination_absent(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)


def _require_cached_metadata(paper_dir: Path, metadata_digest: str) -> dict:
    cached = paper_resolve.read_cached_metadata(paper_dir, metadata_digest)
    if cached is None:
        raise Refused(
            "METADATA_NOT_CACHED",
            f"no cached resolution carries digest {metadata_digest!r} under {paper_dir}; "
            "run `resolve` for this identifier before `full_text`",
        )
    return cached


def _require_full_text_url(metadata: dict) -> str:
    """The measured answer, read off the cache -- never re-guessed here.
    Refuses `FULL_TEXT_URL_ABSENT` (work-state), naming the identifier,
    title and resolver, when the cached record carries none: this is the
    "reported unobtainable BY NAME, never silently skipped" requirement's
    own gate, and the orchestrator's own record of which claim this
    candidate was meant to cover is what turns a sequence of these
    refusals into the operator-facing "No pude bajar" list.
    """
    url = metadata.get("full_text_url")
    if not url:
        raise Refused(
            "FULL_TEXT_URL_ABSENT",
            f"{metadata.get('identifier')!r} (title {metadata.get('title')!r}, resolved via "
            f"{metadata.get('resolver')!r}) carries no obtainable full-text URL in its cached "
            "metadata; source a replacement PDF for it yourself and place it under "
            "guidance/<section-id>/",
        )
    return url


def _require_full_text_role(config: dict, resolver: str) -> None:
    """Reuses `paper_resolve.require_role_connectors` verbatim -- an empty
    `full-text` role in `papersmith.yaml` refuses `RESOLVER_ROLE_EMPTY`
    here exactly as it already does for `resolve`'s own `resolution` role,
    which is what closes this whole fetch path the moment the role is
    emptied (`the-pdf-arrives-or-the-operator-is-told`, "Emptying the
    full-text role... must close this path entirely")."""
    connectors = paper_resolve.require_role_connectors(config, "full-text")
    if resolver not in connectors:
        raise Refused(
            "RESOLVER_ROLE_EMPTY",
            f"{resolver!r} is not a connector configured for role 'full-text' ({connectors})",
        )


def _verify_pdf_bytes(raw: bytes, *, source_url: str) -> None:
    if not raw.startswith(_PDF_MAGIC):
        raise Refused(
            "FULL_TEXT_NOT_A_PDF",
            f"{source_url} did not deliver real PDF bytes (no %PDF header); the reported "
            "full-text URL does not actually serve a fetchable PDF",
        )


def fetch_full_text(
    paper_dir: Path, guidance_dir: Path, *, section_id: str, metadata_digest: str,
    cite_key: str, config: dict,
) -> dict:
    """The one orchestration this module exists for: read a cached
    resolution's own measured `full_text_url`, fetch it over
    `paper_resolve`'s exact client, verify it is really a PDF, and place it
    loose under `guidance/<section_id>/`.

    Order matters: destination containment (`resolve_destination`) is
    checked BEFORE any network fetch, so a malformed `--cite-key`/
    `--section` never spends the one HTTP round-trip this call makes.
    """
    metadata = _require_cached_metadata(paper_dir, metadata_digest)
    resolver = metadata.get("resolver", "")
    url = _require_full_text_url(metadata)
    _require_full_text_role(config, resolver)
    destination = resolve_destination(guidance_dir, section_id, cite_key)
    _require_destination_absent(destination)
    raw = paper_resolve.fetch_bytes(url, config=config)
    _verify_pdf_bytes(raw, source_url=url)
    write_full_text(destination, raw)
    return {
        "section": section_id, "cite_key": cite_key, "identifier": metadata.get("identifier"),
        "resolver": resolver, "metadata_digest": metadata_digest, "full_text_url": url,
        "path": str(destination), "bytes": len(raw),
    }
