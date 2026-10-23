# Review lenses

Select checks relevant to the change; checklist coverage is not proof of a bug.

## Correctness and regression

- Trace inputs through changed branches to outputs and side effects. Check empty/null values,
  numeric boundaries, error paths, retries, cancellation, and backward compatibility.
- Compare intended behavior with actual callers, tests, public contracts, and previous behavior.
  A test asserting the same mistake is not an independent oracle.
- For bug fixes, check whether the root cause and other reachable instances remain.
- For docs/config changes, check factual claims, routing, defaults, and compatibility against
  their authoritative source. Do not fabricate runtime concerns for prose-only edits.

## Security and reliability

- Trace untrusted data to SQL, shell, HTML, file paths, network requests, and deserialization.
  Identify a reachable attack path and the actual trust boundary before reporting a vulnerability.
- Check authentication versus authorization, tenant isolation, secret exposure, and permissions.
- Check concurrency, check-then-act races, transaction boundaries, idempotency, partial failures,
  resource cleanup, and migration/rollback compatibility.
- Check unbounded work, N+1 queries, memory growth, and hot-path regressions against real usage.
  Explain both exploitability or triggering conditions and impact.

## Architecture and maintainability

- Use SOLID as questions about concrete contracts: mixed responsibilities, substitutability,
  interface obligations, extension points, and dependency direction. Apply only where useful
  for the language and design; do not force object-oriented patterns onto unrelated code.
- Explain how a design choice breaks a contract or impedes a stated requirement before treating
  it as a defect. Drop stylistic preferences and preference-based refactors unless the user
  asks for suggestions.
- Before recommending deletion, check callers, dynamic registration, public APIs, and supported
  feature flags. No search matches alone does not prove code is unused.
- Use scoped project conventions and comments as evidence; distinguish a binding requirement
  from advice. Cite the actual rule, not an inferred preference.
