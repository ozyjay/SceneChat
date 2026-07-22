# Privacy and safety

## Defaults

- Visitor images, video, and audio are not stored. Configuration rejects frame/video storage.
- Frames remain in bounded process memory only and responses use `Cache-Control: no-store`.
- Logs may record start-up, mode, duration, error category, fallback, and reset events; they must never contain frames, faces, identifying information, or full visitor text.
- Visitors choose version-controlled curated questions. Arbitrary public prompts are out of scope.

## Prohibited inference

Do not identify people or infer names, age, ethnicity, religion, health, disability, sexuality, emotion, criminality, political views, or other sensitive personal attributes. Do not add face recognition, face matching, attendance tracking, persistent visitor tracking, licence-plate recognition, or audio recording.

## Public signage

> SceneChat combines fast object detection with a multimodal language model that generates a likely description of the scene. The detector and the language model can both miss details or make mistakes. This camera feed is processed live and is not stored by default.

## Reset and privacy screen

**Hide camera now** sets the privacy flag immediately. The public visual is replaced, `/api/frame` stops returning an image, new analysis is blocked, and the generation counter invalidates an analysis already in flight. **Reset session** clears generated text and learned detector objects, restores the operator-selected detector baseline, clears learning counters, clears staff errors and latency, restores the default curated question, and increments the same counter so an older success or failure cannot change state afterwards. Reset does not silently disable an active privacy screen.

## Prompt safeguards

`prompts/scene_analysis_system.txt` requires visible evidence, cautious observation/inference wording, uncertainty, generic references to people, prohibited sensitive inference, concise structured JSON, and no private-reasoning claim. Output is untrusted: only the model-generated schema is accepted, extra operational fields and overlong text are rejected, and high-confidence identification or sensitive-trait claims are blocked before trusted provider metadata is added.

ModelDeck errors are also untrusted. SceneChat exposes only bounded categories and sanitised operator guidance; it never displays raw gateway bodies, Worker identifiers, prompts, images or model output in logs.

Session prompt learning accepts only short lowercase object-style labels from structured `objects`. Both the label and description are checked against version-controlled conservative rules for human description and identity, sensitive traits, medical and assistive items, religious and political objects, intimate items, weapons, drugs, alcohol, tobacco and vaping. Any model `safety_notes` block all candidates from that analysis. Rejected raw labels are removed before API or state exposure and are never logged; exact rejected labels and the sensitive terms that caused rejection are locally replaced with `[withheld]` if repeated in otherwise-safe scene text. Other summary, relationship and uncertainty content remains available. Operators see counts and safe reason categories only. The exact generic `person` label remains available when its description contains no sensitive wording.
