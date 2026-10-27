# Final presentation files

- [Editable PowerPoint deck](Warden-CCD-Project-Presentation-FINAL.pptx)
- [Matching PDF](Warden-CCD-Project-Presentation-FINAL.pdf)
- [10-minute presenter and demo guide](Presenter-Guide.md)

The deck retains the 17-slide structure and research references. The guide includes a four-presenter script, a safe
read-only live demo, offline evidence fallback, plain-language definitions and likely questions.

Azure Flexible Server provisioning, a basic SQL smoke query and teardown passed on 27 October 2026. Full E4 remains
partial: the service-level migration and connection test, repeat timing and cost measurements are still open. Live
image verification remains in Audit. The project keeps the current Kyverno version pinned.

The editable deck source is `scripts/build_presentation.cjs`. From `scripts/`, use `npm ci` once and `npm run build`
to generate `.presentation-build/candidate.pptx`. Validate the candidate, publish it as the final PowerPoint, export a
matching PDF and inspect all pages before replacing the submitted files.
