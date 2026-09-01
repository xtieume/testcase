# Japanese Documents — Extra Audit Checks

Read this when the spec or the documents are Japanese, or when either mixes scripts.

Add these to the checklist built in `dimensions.md`:

* Term consistency across 漢字 / かな / カタカナ / 英字 spellings of the same term — search all
  variants before writing `Missing`
* 全角/半角 differences in field values, IDs, and numbers
* 敬体/常体 mixing where the doc set has a style rule
* Whether translated documents match the source revision (`Stale` if not)

## Before writing `Missing`

Search every spelling variant of the term first. A requirement documented as `工種コード`
will not be found by grepping `工種コード` alone if the document writes `工種 コード`,
`コウシュコード`, or `work type code`. List the variants you searched in the Note column —
that list is what makes a `Missing` verdict checkable.

## Quotes

Quote Japanese text verbatim, including 全角 punctuation and spacing. Normalizing a quote
while copying it destroys the evidence for 全角/半角 findings.
