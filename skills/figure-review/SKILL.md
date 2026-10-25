---
name: figure-review
description: "Trigger: after `render` has already written a compiled figure to `paper/Figures/<id>.pdf`, and a reader needs to know whether the picture itself reads — not the prose that describes it. Turns an already-compiled PDF into pixels and computes the geometric facts a raster can actually support: whether ink runs off the canvas, whether ink regions collide, and how much of the canvas is occupied. Never repairs a figure, never compiles LaTeX, never judges style or legibility. Verbs: `probe` names the rasterizer this machine will use; `raster` produces the PNG and its provenance."
---

# Figure Review

`render` compiles a diagram source to a PDF and stops there. `figure audit`
then checks that PDF's declared manifest against the prose that describes it.
Between the two, nothing ever looks at the picture — every visual dimension is
reported `unmeasured`, honestly, because nobody ever rasterized it.

This skill closes that gap, and only that gap. It consumes a PDF `render`
already produced; it never compiles anything, and it never touches the
per-figure repair budget that guards `render`'s own compile attempts. Its job
ends at pixels and the facts a raster can actually support — it never repairs
a figure and it never decides what "too much whitespace" or "illegible text"
means, because those are judgements about a reader, not properties a
rasterizer can settle.

## What this skill answers, and what it refuses to

**Answerable from pixels alone, with a computed verdict:**

- Whether non-background ink sits inside the outermost pixel row or column of
  the raster — ink running off the canvas.
- Whether two ink regions' bounding boxes collide — reported by coordinates
  only, never by a component's name, because a raster carries no names.

**A number worth reporting, with no verdict attached:**

- How much of the canvas each band occupies. A canvas that is a third blank
  is a fact, not a failing condition; deciding whether that is "too much" is a
  composition judgement this skill does not make.

**Never answerable from pixels, and never claimed to be:** legibility, arrow
or connection correctness, style, aesthetics, legend quality, and which
declared component an overlap belongs to. Each of these stays an announced
silence — `unmeasured` with a reason naming exactly why — rather than a guess
dressed up as a measurement. A `pass` on any of these would be strictly worse
than today's honest silence.

## The front door is a command, not a session claim

Whether this skill is usable is a fact anyone can check by running it, never
an agent's unverified claim that it happens to be "available in this
session." The front door answers `--help` and reports which rasterizer this
machine will use.

```
python scripts/review_cli.py probe [--json]
python scripts/review_cli.py raster --pdf <path/to/example-figure.pdf> [--dpi 150] [--out <dir>]
```

`probe` names the first tool this skill's fallback chain finds — in order,
`pdftoppm`, `pdftocairo`, `gs`, `sips` — and exits 2 naming every one of the
four it probed, plus the exact `PATH` it searched, when none resolves. That
refusal is never reported as an `unmeasured` visual dimension: an absent tool
is an unreadable invocation, not a dimension this skill declined to judge.
Whoever consumes the refusal (an agent, another verb) quotes it as the reason
every dimension went unmeasured.

`raster` writes a PNG plus its provenance (which tool produced it, at what
DPI, and whether that DPI was requested or derived) beside the figure it
rasterized. It reads no ledger and writes no ledger: a full pass — successful
or one where every fallback link fails — leaves `render`'s repair budget
byte-identical, because rasterizing a picture that already exists is not a
compile.

## What this skill never does

- It never invokes a LaTeX toolchain and never opens a repair-budget ledger,
  under any code path, including a failed rasterization.
- It never repairs or redraws a figure. Reading the picture and deciding what
  to change about it are different jobs, kept apart on purpose.
- It never imports another skill's scripts, and no other skill imports this
  one's. The two sides meet only through a plain-data file on disk.
- It never reports a judgement — style, legibility, "does this look right" —
  as a measurement. Two boxes that merely sit close together, or an arrow that
  merely looks thin, are not findings this skill produces; only a computed
  collision or an out-of-bounds pixel is.

## Subprocess boundary

`raster.py` is the only module in this skill permitted to spawn a process —
every rasterizer link this skill can reach lives behind that one seam, pinned
by this skill's own test suite the same way `paper-writing` pins its own.
Every invocation is a list of arguments, never a composed shell string, and
the figure path is always resolved to an absolute path before it reaches
argv, so a path beginning with a dash is never mistaken for a flag.
