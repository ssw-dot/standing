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

## Sponsor integrations

| Sponsor | What it does here | Why it is not decorative |
|---|---|---|
| **Nutrient DWS** | PDF → text, with OCR | A local library returns an empty string for a scanned PDF *without saying so* — which this system would read as "no requirements found". OCR keeps "says nothing" and "could not be read" from becoming the same thing. |
| **SerpApi** | Cited context for open doubts | When the document defers to an external fact, the model will invent a plausible one. Search returns real links, or returns nothing — and nothing is an answer a model never gives. |
| **Foxit PDF Services** | The report | If someone decides not to apply, the reason has to outlive the session. A PDF with the quotes can be shown to a director or filed. A chat message cannot. |

Search results never decide a verdict. They add cited context for a human. The
document decides.

## Running it

```bash
cp .env.example .env        # fill in your four keys
python -m unittest discover -s tests -p "test_*.py"     # 45 tests, no network
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

45 tests, no network, no credentials. Most of them assert the same thing from
different angles: **that a doubt does not turn into an exclusion.**

A forecasting bug announces itself. This one does not — it returns a confident
verdict and nobody learns it was wrong, because the person it was wrong about
simply never applied.

## Licence

MIT.
