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
so this is the model, not the integration. With the gateway's placeholder block
threshold of 0.90 such prompts would be blocked. Calibrate the thresholds with
`scripts.evaluate` before relying on them, and report false positives to the
model owner.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `MODEL_DIR` | `models/xlm-roberta-pi` | directory with the weights and tokenizer, relative to the working directory (`/app`) |
| `MODEL_CARD_PATH` | `models/xlm-roberta-pi.card.json` | provenance card with the pinned revision and sha256 values |
| `CLASSIFIER_MAX_TEXT_CHARS` | `32000` | request size limit |
| `CLASSIFIER_MAX_WINDOWS` | `3` | windows scored per request (see [Long prompts](#long-prompts)) |
| `CLASSIFIER_MAX_CONCURRENCY` | `1` | inferences allowed at once |
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
Compose keeps them in the `ml_weights` volume.

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
(`CLASSIFIER_MAX_CONCURRENCY=1`). Concurrent requests queue, and requests that
wait past the gateway's budget fail open and are audited as `ml_unavailable`.

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

No evaluation set is committed (there is no `ml-classifier/data/`); you supply
`eval.csv` yourself. The S-Labs test split is held out from training and suits
calibration.

```bash
python -m scripts.evaluate models/xlm-roberta-pi.card.json path/to/eval.csv [--adversarial] [--model-dir DIR]
```

Without `--adversarial` the script prints precision, recall and false-positive rate across a threshold
grid (0.1 to 0.9 in steps of 0.1, then 0.95) — this is where the gateway's
`CLASSIFIER_BLOCK_THRESHOLD` and `CLASSIFIER_REVIEW_THRESHOLD` values should
come from. The values currently configured, `0.90` and `0.60`, are
**uncalibrated placeholders**. With `--adversarial` it re-scores the injection rows after
obfuscation (leetspeak, spacing, zero-width characters, base64, upper-snake)
and reports each variant's recall, which is the MITRE ATLAS AML.T0015
measurement. Compare it with the baseline recall to get the drop.

The evaluation CSV has two columns, `text,label`, with `label` in
`{injection, clean}` (case-insensitive), UTF-8. **It must not contain training
examples**, or the adversarial number measures memorisation rather than
robustness. The script cannot check this; you must guarantee it.

Know the limits of the adversarial experiment before quoting it: it applies
every transform to all injection rows rather than only those the model detects
at baseline (misses dilute the drop); its tables contain no clean rows, so their
precision and FPR columns are trivially 1 and 0; and it has no homoglyph,
paraphrase, translation, typo or payload-splitting variants; and
the threshold grid is coarse (no counts, and it jumps from 0.90 to 0.95), so
for a stringent false-positive target compute the threshold yourself from the
raw scores.
