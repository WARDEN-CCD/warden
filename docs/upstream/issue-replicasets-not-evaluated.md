### Kyverno Version

1.19.2 (Helm chart 3.9.2)

### Kubernetes Version

1.37.0 (kind)

### Description

An `ImageValidatingPolicy` whose `matchConstraints.resourceRules` select `apps/v1` `replicasets` admits a ReplicaSet whose pod template has an unsigned image. The policy is configured to refuse:

- `images` extractor: `object.spec.template.spec.containers.map(c, c.image)`
- `validationActions: [Deny]`, `failurePolicy: Fail`, `validationConfigurations.required: true`

What I see:

- The ReplicaSet is admitted in 0.23 s, and the admission controller's log shows no verification.
- The webhook configuration does contain the rule (`replicasets`, path `/ivpol/validate/<policy>`).
- The same policy and the same ReplicaSet are refused as expected by `kyverno apply`.
- Removing `matchConditions` makes no difference.
- The autogen'd controller rules of a Pod-matching IVP behave the same way: a dry-run ReplicaSet is admitted in 0.22 s, while the equivalent Pod takes 16.7 s and is verified.

### Expected

ReplicaSets (and the other pod controllers the webhook is registered for) are verified at admission, as `kyverno apply` does.
### Notes

The investigation is written up in ADR-031 of the project that found it: https://github.com/WARDEN-CCD/warden/blob/main/DECISIONS.md (search for "ADR-031"). The failing check is attack A14 in https://github.com/WARDEN-CCD/warden/blob/main/evidence/attacks/2026-10-25T024144Z-results.json. I can share the exact manifests.
