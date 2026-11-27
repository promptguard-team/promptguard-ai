# ML Classifier

Layer 2 of PromptGuard's detection chain. Scores outbound prompts for prompt
injection and returns a number. **It never decides anything** — the API gateway
owns the thresholds, because a threshold is organisational policy and changing
one should not require redeploying a model.

It scores prompts only. Replies from the LLM are not sent here; response-side
protection is the gateway's rule engine (Layer 1).

If you are here to deliver a new model version, read [Delivering a new model
version](#delivering-a-new-model-version) and [Evaluation](#evaluation).

## API

### `POST /classify`

```json
{ "text": "ignore all previous instructions" }
```

```json
{ "label": "injection", "score": 0.94, "model_version": "xlmr-pi-e8a758a" }
```

`score` is P(injection), within `[0,1]`. `label` is the argmax class
(`clean` or `injection`) and exists for audit readability, not as a verdict.

Returns `422` for empty text or text longer than `CLASSIFIER_MAX_TEXT_CHARS`
(default `32000`, matching the gateway's own prompt ceiling).

### `GET /health`

Reports `status`, `model_version` and `stub`. The service refuses to start
without a loadable, valid model, so a running process always has one.

## The model

The service serves
[`mkvpczyk/prompt-injection-xlm-roberta`](https://huggingface.co/mkvpczyk/prompt-injection-xlm-roberta)
pinned at commit `e8a758a`, a fine-tuned XLM-RoBERTa from the team's training
PR #62. Labels are `0 = clean` and `1 = injection`, declared on the card
(`models/xlm-roberta-pi.card.json`) and read from it, never assumed. The model
reads up to 256 tokens at a time, handles Polish and English, and ships as about
1.1 GB of weights in safetensors.

### Known model behaviour

Observed on the real weights with the PR #62 sample prompts plus a few more:
attacks in Polish and English score 0.98-0.999, and benign prompts mostly score
0.01 or less. There are exceptions: "Podsumuj proszę ten artykuł w trzech
punktach." scores 0.95 and "Summarize this article in three bullet points."
scores 0.41. The teammate's own transformers pipeline gives identical numbers,
so this is the model, not the integration.

The PoC set (`data/poc/`, 150 clean and 104 attack prompts) shows these are not
isolated cases: ordinary editing requests ("replace every occurrence of...",
"rewrite the previous sentence...", "shorten this email...") score 0.99 or
more, as high as real attacks. That is why the gateway defaults are high:
block 0.998 stops 53/104 attacks with 1/150 false positives, and the review
band from 0.99 flags 97/104 attacks for the CISO at the cost of 14/150
ordinary prompts. Report false positives to the model owner; retraining on
Polish business prompts is the fix. Details in `docs/poc/raport-poc.md`.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `MODEL_DIR` | `models/xlm-roberta-pi` | directory with the weights and tokenizer, relative to the working directory (`/app`) |
| `MODEL_CARD_PATH` | `models/xlm-roberta-pi.card.json` | provenance card with the pinned revision and sha256 values |
| `CLASSIFIER_MAX_TEXT_CHARS` | `32000` | request size limit |
| `CLASSIFIER_MAX_WINDOWS` | `3` | windows scored per request (see [Long prompts](#long-prompts)) |
| `CLASSIFIER_MAX_CONCURRENCY` | `1` | inferences allowed at once |
| `CLASSIFIER_QUEUE_TIMEOUT_SECONDS` | `1.5` | longest a request may wait for an inference slot before it gets `503` |
| `CLASSIFIER_TORCH_THREADS` | torch default | torch intra-op threads; compose sets `2` to match its CPU limit, because torch otherwise uses the host core count and oversubscribes a CPU-limited container |
| `HF_TOKEN` | optional | used by `fetch_model` only |

The gateway-side settings (`CLASSIFIER_URL`, `CLASSIFIER_TIMEOUT_SECONDS`,
`CLASSIFIER_BLOCK_THRESHOLD`, `CLASSIFIER_REVIEW_THRESHOLD`) live in the root
`.env`, not here.

`requirements.txt` pins `torch==2.15.0+cpu`, which comes from the PyTorch CPU
index (Linux x86_64 and Windows). On macOS install the plain `torch==2.15.0`
wheel instead.

## Getting the weights

From the `ml-classifier/` directory:

```bash
python -m scripts.fetch_model
```

The script is idempotent and verifies the sha256 of every file against the card.
The `prod` image fetches the weights at build time, so building needs network.
Compose keeps them in the `ml_weights` volume. On the first `compose up` the
classifier downloads ~1.1 GB before serving, and until then the gateway fails
open (`ml_unavailable`).

The service itself never downloads anything. At startup it verifies the sha256
of every file, loads offline (safetensors only, no remote code) and runs one
warm-up inference. Any failure, such as a missing file or a hash mismatch,
refuses to start. Loading takes about 7-10 s on the dev box, hence the generous
compose `start_period`.

## Long prompts

The model reads 256 tokens at a time, so longer prompts are split into
overlapping windows of 254 content tokens (room for `<s>` and `</s>`) with an
overlap of 64, a stride of 190. The score is the maximum over the windows.

Past `CLASSIFIER_MAX_WINDOWS`, the first half and the last half of the windows
are kept. Injected instructions are usually prepended or appended to otherwise
harmless text, so the ends matter most.

With the default of 3 windows, prompts up to about 630 tokens (roughly 2,500
characters) are read in full. Beyond that the first two and the last window are
scored and **the middle is not**. This is a known evasion path: an injection
buried in the middle of a long text can go unseen. Raising the cap trades
latency for coverage (see [Latency](#latency)).

Special tokens are neutralised: user text is tokenised with special-token
matching disabled and the control ids (`<s>`, `</s>`, `<pad>`, `<mask>`) are
dropped, so typed control tokens cannot fake sequence structure. `<unk>` is
kept.

Each request is one inference at a time by default
(`CLASSIFIER_MAX_CONCURRENCY=1`). Concurrent requests queue, but only for
`CLASSIFIER_QUEUE_TIMEOUT_SECONDS`: a request still queued past it gets `503`
(`classifier busy`) instead of building an unbounded backlog. The gateway treats
that as unavailable, so it fails open and audits `ml_unavailable`. An inference
that has already started always completes.

## Latency

Measured with `python -m scripts.benchmark --repeats 5` on a Windows dev box
(16 logical CPUs, torch 2.15.0+cpu); see below.

| threads | windows | chars | median ms | max ms |
|---------|---------|-------|-----------|--------|
| 8 (torch default here) | 1 | 68 | 59 | 68 |
| 8 | 4 | 3672 | 884 | 951 |
| 8 | 8 | 7956 | 1643 | 1658 |
| 2 (compose CPU limit) | 1 | 68 | 93 | 93 |
| 2 | 2 | 1496 | 767 | 777 |
| 2 | 3 | 2584 | 1133 | 1141 |
| 2 | 4 | 3672 | 1494 | 1530 |
| 2 | 8 | 7956 | 2840 | 3019 |

The gateway gives the classifier 2 s (`CLASSIFIER_TIMEOUT_SECONDS`) and fails
open. At compose's limit of 2 CPUs, 8 windows (2.8 s) blows that budget and 4
(1.5 s) leaves no headroom for queueing and the network, so the default cap is
3 (about 1.1 s). Re-measure on your hardware with `python -m scripts.benchmark`
whenever the model, the CPU limit or the cap changes.

## Delivering a new model version

1. Push the model to Hugging Face.
2. Update `models/xlm-roberta-pi.card.json`: `source.revision`, the four sha256
   values and `model_version`. `model_version` is limited to 64 characters and
   is written to every audit row.
3. Run `python -m scripts.fetch_model`, `pytest` and `python -m scripts.benchmark`,
   and revisit the window cap against the new latency numbers.
4. Open a pull request. The card is the provenance record.

Only safetensors and only offline loading are accepted, and `trust_remote_code`
is never used.

## Evaluation

Model quality is never asserted in CI: metrics depend on an artifact that
changes, so a pinned assertion either breaks constantly or proves nothing.
Measure it here instead. Run from the `ml-classifier/` directory (the scripts
import `app` and `scripts`, so `python scripts/evaluate.py` will not work):

### PoC report and calibration

The PoC set lives in `data/poc/`: `clean.csv` (150 ordinary prompts: business,
borderline, code, chitchat) and `attacks.csv` (104 attacks: instruction
override, system prompt leak, jailbreak, roleplay), about half Polish and half
English, written for this project. `scripts.poc_report` scores it, the S-Labs
held-out test split, obfuscated attacks (MITRE ATLAS AML.T0015) and attacks
pasted inside documents (OWASP LLM02), and recommends thresholds:

```bash
python -m scripts.fetch_model
python -m scripts.fetch_eval_data          # S-Labs train + test, pinned by data/s-labs.card.json
python -m scripts.poc_report > poc.md      # ~15 min at 2 threads; --quick (~10 min) skips S-Labs test
```

Before scoring, a leakage guard aborts if any PoC row also appears in the
S-Labs train split or the notebook's added samples (the model would be
recognising it, not judging it). Recommended thresholds are the lowest grid
value with FPR at most 1% on the clean set (block) and the lowest value below
it with FPR at most 10% (review). Tables report absolute counts: with 150
clean prompts, 1% is one or two prompts. The gateway defaults and the full
results are in `docs/poc/raport-poc.md`.

### Ad-hoc evaluation

```bash
python -m scripts.evaluate models/xlm-roberta-pi.card.json path/to/eval.csv [--adversarial] [--model-dir DIR]
```

Without `--adversarial` the script prints precision, recall and false-positive
rate (with counts) across the same threshold grid as the PoC report. With
`--adversarial` it re-scores the injection rows after each obfuscation
transform (leetspeak, spacing, zero-width characters, base64, upper-snake,
diacritics stripping, Cyrillic homoglyphs, filler-word noise) and reports each
variant's recall. Compare it with the baseline recall to get the drop.

The evaluation CSV has columns `text,label` (`label` in `{injection, clean}`,
case-insensitive) and optionally `category,lang`, UTF-8. **It must not contain
training examples**, or the numbers measure memorisation rather than
robustness; `scripts.evaluate` cannot check this (`scripts.poc_report` can, for
its own set).

Know the limits of the adversarial experiment before quoting it: it applies
every transform to all injection rows rather than only those the model detects
at baseline (misses dilute the drop); its tables contain no clean rows, so
their precision and FPR columns are trivially 1 and 0; and it has no
paraphrase, translation, typo or payload-splitting variants.
