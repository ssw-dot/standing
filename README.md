# Standing

**Can I apply to this?** Point it at a call for proposals and it answers — with
the exact sentence from the document that decides it.

Built for the **DevNetwork [API + Cloud + AI] Hackathon 2026**.

```bash
python -m standing call.pdf --perfil profile.json --salida report.pdf
```

```
[1/5] reading call.pdf...
[2/5] locating requirements...
      3 requirements with verified quotes
[3/5] comparing against your profile...

  ELIGIBLE

  [yes] tipo_de_entidad: 'nonprofit' matches ['nonprofit organisations']
  [yes] pais: 'MX' (MX) is on the list
  [yes] antiguedad: 4 years against at least 2 years

[5/5] generating report.pdf...
```

---

## The error nobody ever finds out about

Every AI document tool answers. That is the problem.

There are two ways to be wrong about eligibility and **they do not cost the
same**:

| | What happens |
|---|---|
| **False "you qualify"** | You apply. You get rejected. You lost an afternoon. |
| **False "you don't qualify"** | You don't apply. There is no rejection letter. Nothing to review. **The money is gone and no trace is left that it was ever there.** |

The second error is invisible, and it is the one a model eager to be helpful
makes. So Standing has a third verdict:

> ### ELIGIBLE · NOT ELIGIBLE · **CANNOT BE DETERMINED**

When the document does not say whether a requirement applies to you, the
correct answer is not a guess. It is to point at the ambiguous sentence and
hand the decision back to a person.

This is not hypothetical. An earlier version of this screening logic told a
public library not to apply to a fund whose text read *"open to nonprofit
organisations"* — because the profile said `nonprofit` and string equality said
no. We told a library to skip a grant written for libraries.

## The architecture, and why it is shaped that way

```
  call.pdf
     │
     ├─▶ Nutrient DWS ──────────  PDF → text (OCR if scanned)
     │
     ├─▶ Gemini ────────────────  text → requirements, each with a verbatim quote
     │                            ↓
     │                        every quote is checked against the source text;
     │                        if it isn't there, the requirement is dropped
     │                            ↓
     ├─▶ deterministic code ────  requirements + profile → VERDICT   ← no model here
     │
     ├─▶ SerpApi ───────────────  cited context for what stayed unresolved
     │
     └─▶ Foxit PDF Services ────  report → PDF
```

**The model never decides.** Its job is smaller and far more reliable: find the
requirements and copy the sentence that states them. Comparing those
requirements against a profile is arithmetic, and arithmetic does not
hallucinate.

That split buys a property worth more than accuracy: asking a model *"is this
person eligible?"* requests a conclusion, and it will produce one even when the
document does not support one. Asking it *"copy me the sentence that says so"*
has a useful failure mode — **when the sentence does not exist, there is
nothing to copy**, and that is detectable.

So every extracted quote is verified character-for-character against the source
text. A requirement whose quote is not found in the document was invented, and
it is dropped and reported — not silently used.

## A document that points elsewhere is not a document without rules

Run against a real 21-page Horizon Europe work programme, Standing returned NOT
ELIGIBLE — with a quote, a comparison and a reason. All of it correct except
one thing: the same document says, in its own words,

> *"the **General Annexes** to this work programme set out the general
> conditions applying to the calls of the work programme such as **eligibility
> rules**"*

**The authoritative rules were in a file nobody had read.** The verdict was
drawn from a parenthetical listing who had to file a gender equality plan — not
from a list of who may apply.

This is the worst version of the failure this project exists to prevent,
because it looks well-founded. So:

> **A document that defers its eligibility rules cannot exclude anyone.**

When deferral is detected, NOT ELIGIBLE is downgraded to CANNOT BE DETERMINED,
the unmet requirement stays visible, and the report names the annex you have to
go read. ELIGIBLE is left alone — *"you meet what this document asks"* stays
true, and anyone wrong about that finds out by applying.

Detection requires both a deferral phrase **and** eligibility language in the
same sentence. Without that second filter, *"the TRL definition is available in
the General Annexes"* triggered it too — and if everything defers, nothing
does.

## The same document, three different verdicts

Run four times over one call for proposals, Standing answered ELIGIBLE once,
NOT ELIGIBLE twice, and CANNOT BE DETERMINED once. For a tool whose whole pitch
is *defensible and auditable*, answering differently on the second run is worse
than answering wrong on the first.

**It was not the verdict logic.** The model returns `["at least two years"]` on
one read and `["2 years"]` on the next. Strip the threshold words and the
condition passes for an enumeration, text comparison runs, and `4 years` does
not equal `2 years` — the four-years bug back through a different door. The
first fix detected thresholds by their words, so it broke the moment the words
were dropped.

Two changes, and the second closes the class rather than the instance:

**The threshold is read from the quote when the values do not carry it.** The
quote is verified character-for-character against the document, so it is real
text rather than the model's paraphrase. If the document says *at least two
years*, it still says it.

**Text comparison may never exclude when both sides are quantities.** `4 years`
and `2 years` are not the same string and one still clears the other by double.
Excluding there is precisely the invisible error this project exists to
prevent, so that path now returns a doubt.

And the extraction itself now reads each chunk three times and keeps only what
appears in at least two. A requirement present in one read of three is sampling
noise, not something the document states. Grouping is by normalised quote, not
by key: the model invents the key and renames it between reads, while the quote
is copied text.

> Temperature 0 reduces Gemini's variance. It does not remove it. A screening
> tool that answers differently on two runs cannot be defended to anyone, which
> is the only thing it sells.

## Four failures found by running it, not by imagining it

**0 · Eighty-eight thousand characters, zero requirements.**
Handed the whole Horizon Europe document at once, the model returned an empty
array — from a text that contained at least two real criteria, one of them
geographic. It skims. The text is now split into overlapping 18k chunks and the
results merged and deduplicated by quote. The overlap is not decoration: a
requirement straddling a cut would vanish from both sides, and that is the kind
of failure that raises no error.

**1 · "4 years" failed "at least two years".**
The first full end-to-end run returned NOT ELIGIBLE to an applicant who
qualified. `at least two years` is not a list of accepted values — it is a
threshold, and text comparison cannot evaluate one. Thresholds are now parsed
and compared numerically, and anything unparseable becomes a doubt, never an
exclusion. ([`cantidades.py`](standing/cantidades.py))

**2 · "un mínimo de tres empleados" parsed as 1.**
The Spanish article *un* was read as the numeral one, before *tres*. A minimum
of three silently became a minimum of one. Ambiguous articles are now read
last. Found by a test, not by a user.

**3 · "United States" resolved to nothing.**
The normaliser strips plurals — which fixes `organisations`/`organisation` and
destroys `United States` → `united state`. The same normalisation cannot serve
both proper nouns and common ones. ([`lugares.py`](standing/lugares.py))

## Doubt never excludes

The rule that governs every comparison. Unresolvable inputs go to CANNOT BE
DETERMINED, never to NOT ELIGIBLE:

| Situation | Verdict |
|---|---|
| Document accepts "Europe", profile says "MX" | cannot determine — a region is not a country |
| Document accepts "Quebec" | cannot determine — Quebec is not a country, and guessing "CA" would be an opinion wearing the costume of a fact |
| Document asks for years, profile gives employees | cannot determine — not comparable |
| Requirement stated but no values given | cannot determine — the document raises it without defining it |
| No requirements could be extracted | cannot determine — **an unreadable document is not an authorisation** |

## The pile that does not exist anywhere else

Standing's whole argument is that a false *"not eligible"* is invisible. But
**why** is it invisible?

Because nobody keeps a record of what they did not apply to. Applications that
were sent leave a trail — a file, an acknowledgement, a rejection letter. The
ones that were never sent leave nothing. There is no folder called *calls we
ruled out*, so there is no way to go back over them.

The PDF fixes that for one screening. The history fixes it for an organisation:

    Which calls did we screen this quarter?
    Which ones did we rule ourselves out of, and on which sentence?
    How many were left undecided that nobody ever went back to?

That last question cannot be asked anywhere today. `--historial` answers it, and
counts the pile out loud.

Only two endpoints exist, and the missing ones are the point: there is no
`DELETE` and no `PUT`. An audit trail whose rows can be edited or removed is not
an audit trail, and the whole reason this table exists is to hold the decisions
nobody else writes down.

Two rules: **saving never blocks a verdict** — if Xano is down the screening
already happened and the report is still valid — and **the evidence is stored,
not just the verdict**, because a row saying `NOT ELIGIBLE` and nothing else
would force you to re-run the screening to learn why, which is the thing the
history existed to avoid.

## Sponsor integrations

| Sponsor | What it does here | Why it is not decorative |
|---|---|---|
| **Nutrient DWS** | PDF → text, with OCR | A local library returns an empty string for a scanned PDF *without saying so* — which this system would read as "no requirements found". OCR keeps "says nothing" and "could not be read" from becoming the same thing. |
| **SerpApi** | Cited context for open doubts | When the document defers to an external fact, the model will invent a plausible one. Search returns real links, or returns nothing — and nothing is an answer a model never gives. |
| **Foxit PDF Services** | The report | If someone decides not to apply, the reason has to outlive the session. A PDF with the quotes can be shown to a director or filed. A chat message cannot. |
| **Xano** | The screening history (`POST` + `GET /cribados`) | One report outlives one session. The history outlives the *decision* — it is the only place the calls you ruled yourself out of are written down, which is the precondition for ever noticing a wrong exclusion. |

Search results never decide a verdict. They add cited context for a human. The
document decides.

## Running it

```bash
cp .env.example .env        # fill in your four keys
python -m unittest discover -s tests -p "test_*.py"     # 89 tests, no network
python -m standing ejemplos/convocatoria.pdf --perfil ejemplos/perfil.json
```

Exit codes: `0` eligible · `1` not eligible · `2` cannot be determined · `3`
bad input. The distinction matters in a pipeline: `2` is not a failure, it is a
request for a person.

Flags: `--sin-ocr` saves credits on text-layer PDFs · `--sin-contexto` skips
search · `--texto` console only, no PDF.

**Model fallback.** Measured 21 Aug 2026 on a fresh key with one identical
request: `gemini-flash-latest` hung for 25 s with no response;
`gemini-2.5-flash` returned 404 *"no longer available to new users"*;
`gemini-flash-lite-latest` answered in 0.9 s. Pinning one model means that if
it is down when a judge runs this, the project looks broken. A floating alias
is not enough either — **the one that hung was the floating alias.** So there
is a chain, and failures are reported together rather than as "could not
contact the model".

**Foxit sits behind Cloudflare** and returns `403 error code: 1010` to any
request without a browser User-Agent. Measured: same request, with and without,
gives 200 and 403. Not in the docs.

## Tests

89 tests, no network, no credentials. Most of them assert the same thing from
different angles: **that a doubt does not turn into an exclusion.**

A forecasting bug announces itself. This one does not — it returns a confident
verdict and nobody learns it was wrong, because the person it was wrong about
simply never applied.

## Licence

MIT.
