# ML Classifier

Layer 2 of PromptGuard's detection chain. Scores outbound prompts for prompt
injection and returns a number. **It never decides anything** — the API gateway
owns the thresholds, because a threshold is organisational policy and changing
one should not require redeploying a model.

It scores prompts only. Replies from the LLM are not sent here; response-side
protection is the gateway's rule engine (Layer 1).

If you are here to deliver a trained model, read [Delivering a real
model](#delivering-a-real-model) and [Evaluation](#evaluation).

## API

### `POST /classify`

```json
{ "text": "ignore all previous instructions" }
```

```json
{ "label": "injection", "score": 0.94, "model_version": "stub-tfidf-0.1.0" }
```

`score` is P(injection), within `[0,1]`. `label` is the argmax class
(`clean` or `injection`) and exists for audit readability, not as a verdict.

Returns `422` for empty text or text longer than `CLASSIFIER_MAX_TEXT_CHARS`
(default `32000`, matching the gateway's own prompt ceiling).

### `GET /health`

Reports `status`, `model_version` and `stub`. The service refuses to start
without a loadable, valid artifact, so a running process always has a model.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `MODEL_PATH` | `models/stub-tfidf-0.1.0.joblib` | artifact to serve, relative to the working directory (`/app`) |
| `CLASSIFIER_MAX_TEXT_CHARS` | `32000` | request size limit |

The gateway-side settings (`CLASSIFIER_URL`, `CLASSIFIER_TIMEOUT_SECONDS`,
`CLASSIFIER_BLOCK_THRESHOLD`, `CLASSIFIER_REVIEW_THRESHOLD`) live in the root
`.env`, not here.

## The shipped model is a stub

`models/stub-tfidf-0.1.0.joblib` is a placeholder fitted on forty hand-written
examples. It exists so the HTTP contract and the gateway integration could be
built and tested before a real model was delivered. **Its verdicts are not a
security control.** The service logs a warning at startup when serving it, and
because `model_version` is written to every audit row, the database permanently
records which verdicts came from it.

Regenerate it (from the `ml-classifier/` directory) with:

```bash
python -m scripts.train_stub
```

Note that the script hardcodes `trained_at` in the card, so a regenerated
artifact reports the original date.

## Delivering a real model

Add the artifact and its card to `models/`, point `MODEL_PATH` at it, and make
`requirements.txt` match the versions the card declares. Every requirement below
exists because its absence produces a specific failure.

1. **All preprocessing inside an `sklearn.pipeline.Pipeline`.** This service
   calls `predict_proba` on raw text and nothing else. Normalisation left
   outside the pipeline has to be reimplemented here, and that copy is what
   drifts. The loaded object must expose `predict_proba()` and `classes_`.
2. **One class must be named `injection`.** The class index is read from
   `classes_`, never assumed. A model without it is rejected at startup —
   which is how an inverted score (clean prompts reading 0.95) is made
   impossible rather than merely unlikely. The other class should be `clean`.
3. **A card named `<artifact stem>.card.json` in the same directory.** For
   `models/foo.joblib` that is `models/foo.card.json`. Example:

   ```json
   {
     "model_version": "baseline-tfidf-0.1.0",
     "stub": false,
     "trained_at": "2026-09-20",
     "dataset": "deepset/prompt-injections@<commit> + jackhhao/jailbreak-classification@<commit>",
     "classes": ["clean", "injection"],
     "metrics": { "precision": 0.94, "recall": 0.88, "roc_auc": 0.97, "eval_set": "held-out 20%" },
     "environment": { "python": "3.14.0", "scikit-learn": "1.7.2", "numpy": "2.5.3" }
   }
   ```

   What the service **enforces**: `model_version` (non-empty string; it is
   written to every audit row, up to 64 characters fit there) and
   `environment.scikit-learn`. `stub` is optional and defaults to `false`.
   Everything else is provenance for humans and is not validated, but fill it in
   honestly — the card is the only record of what the model was trained on.
   Set `"stub": true` only for placeholders; it triggers the startup warning.
4. **`environment.scikit-learn` must exactly match the version installed
   here** (currently `1.7.2`, pinned in `requirements.txt`). The service
   refuses to start on a mismatch. scikit-learn does not support loading
   pickles across versions, and without this check a mismatch shows up as
   quietly shifted scores rather than as an exception. If you trained on a
   different version, either retrain on the pinned one or change the pin in
   `requirements.txt` in the same pull request. Also record `numpy` — it is not
   checked, but a pickle is sensitive to it.
5. **Artifacts arrive by pull request, never by file transfer.**
   `joblib.load` executes arbitrary code from the file. A review and a commit
   give the artifact provenance. For a transformer, prefer `safetensors` over
   pickle and Git LFS for the weights — a 250 MB binary enters git history
   permanently.

Check your delivery before opening the pull request: start the service with
`MODEL_PATH` pointing at it (`uvicorn app.main:app --port 7000`) and call
`GET /health`. A bad artifact fails at startup with a message naming the
problem; a good one reports your `model_version` and `"stub": false`.

The `prod` image bakes in everything under `models/`, so a delivery is
shipped by the same pull request that adds the artifact.

## Evaluation

Model quality is never asserted in CI: metrics depend on an artifact that
changes, so a pinned assertion either breaks constantly or proves nothing.
Measure it here instead. Run from the `ml-classifier/` directory (the scripts
import `app` and `scripts`, so `python scripts/evaluate.py` will not work):

```bash
python -m scripts.evaluate models/<artifact>.joblib path/to/eval.csv
python -m scripts.evaluate models/<artifact>.joblib path/to/eval.csv --adversarial
```

The first prints precision, recall and false-positive rate across a threshold
grid (0.1 to 0.9 in steps of 0.1, then 0.95) — this is where the gateway's
`CLASSIFIER_BLOCK_THRESHOLD` and `CLASSIFIER_REVIEW_THRESHOLD` values should
come from. The values currently configured, `0.90` and `0.60`, are
**uncalibrated placeholders**. The second re-scores the injection rows after
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
paraphrase, translation, typo or payload-splitting variants. These are tracked
as follow-ups.
