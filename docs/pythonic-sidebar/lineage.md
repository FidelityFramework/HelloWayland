# Lineage: why Clef reads like Python

A Python programmer reading `src/Gfx3D/Fixed.clef` for the first time
usually gets through it without stopping. That is a designed outcome,
not a coincidence, and the design decisions are older than both
languages.

## Landin's offside rule (1966)

Peter Landin, describing ISWIM, proposed that a program's block
structure could be carried by indentation instead of punctuation — the
"offside rule". ISWIM was never implemented as a production language,
but it seeded two lines of descent.

One line runs through ML (Milner, 1973) into Standard ML, OCaml, Haskell
and eventually F#. The other reaches Python: Guido van Rossum's ABC
teaching language took indentation-as-structure directly from this
tradition, and Python inherited it from ABC. When people say "Python
looks like pseudocode," they are describing an idea that arrived in both
families from the same source.

So the first similarity is **shared ancestry, not imitation**:
significant whitespace, expression-oriented evaluation, first-class
functions, list/sequence comprehensions, and garbage-collected reference
semantics all appear in Python because the ML family got there first and
the ideas were good.

## Don Syme's lightweight syntax (2003→)

The second similarity *is* deliberate. F# began as OCaml on .NET, and
OCaml's syntax is punctuated: `let ... in`, `;;` terminators, explicit
`begin`/`end`. Don Syme made "lightweight syntax" — indentation-aware,
`in`-free, terminator-free — the default mode, with the older "verbose"
syntax kept only for compatibility.

The practical effect: writing

```fsharp
let f x =
    let y = x * 2
    y + 1
```

instead of OCaml's

```ocaml
let f x =
  let y = x * 2 in
  y + 1
```

That single change removes most of the visual distance between an
ML-family function body and a Python one. Syme was explicit that
approachability was a goal — a language can be principled *and* look
familiar to the working programmer.

Clef inherits this posture wholesale. It is an F#-derived language, so
it arrives with lightweight syntax already in place, plus a native
compilation story (Composer → MLIR → machine code) rather than a runtime.

## What actually transfers

Reading the two columns in [side-by-side.md](side-by-side.md), the
following carry across with no structural change:

| Concept | Python | Clef |
|---|---|---|
| Binding | `x = expr` | `let x = expr` |
| Rebindable local | `x = 0` … `x += 1` | `let mutable x = 0` … `x <- x + 1` |
| Block structure | indentation | indentation |
| Loop | `while cond:` | `while cond do` |
| Conditional expression | `a if c else b` | `if c then a else b` |
| Function definition | `def f(a, b):` | `let f (a: int) (b: int) : int =` |
| Early guard | `if bad: return 1` | `if bad then 1 else` … |
| Integer division | `//` | `/` on ints |
| Comment | `#` | `//` |

The differences that remain are the ones that carry real meaning:
Clef's types are mandatory at function boundaries and checked; `mutable`
is opt-in rather than the default; and the compiler's output is a native
binary, not bytecode for an interpreter.

## Why we are pointing at it

This project's rendering math was written twice — once in Python to find
the shape of the solution, once in Clef to ship it — and the second
writing was mostly transcription. That is a good advertisement for both
languages: Python is a fine medium for thinking, and an ML-family
language with lightweight syntax is close enough that the thinking
survives the crossing intact, while gaining static types, no runtime,
and a compilation path all the way down to the metal.

The invitation to Python programmers is therefore small and concrete:
you already know most of the syntax. What you gain by crossing over is
the type checker and the compiler.
