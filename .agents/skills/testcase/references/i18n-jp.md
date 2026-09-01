# Character Set / i18n — Japanese Systems

Read this when the system or the requirement is Japanese, or when any text input accepts
multi-byte characters.

These defects are common, cheap to test, and almost always missed by first-pass test
design — the developer tested with ASCII and the QA tested with ASCII.

---

## For every text input

| Dimension | Test with |
| --------- | --------- |
| 全角 vs 半角 | Numbers `１２３` / `123`, alphabet `ＡＢＣ` / `ABC`, katakana `ｱｲｳ` / `アイウ` |
| Mixed width | One value containing both, e.g. `A１b２` |
| Script mix | ひらがな / カタカナ / 漢字 / romaji in one field |
| Surrogate pairs | 絵文字 `😀`, rare kanji `𠮷`, `𩸽` |
| Full-width space | `　` as leading, trailing, and as the entire value |
| Unicode normalization | Composed vs decomposed: `が` (U+304C) vs `か`+`゛` (U+304B U+309B) |
| Excel paste | Tabs, line breaks, and invisible characters copied from a spreadsheet cell |

## Numbers and dates

* Japanese date format: `2026/08/15`, `2026年8月15日`
* Japanese era: 令和8年8月15日 — accepted, rejected, or converted?
* Comma separators: `1,000` vs `1000`
* Full-width digits in a numeric field: `１０００`

## Charset rules

When the system defines a charset rule for a field — e.g. *code fields are half-width
alphanumeric only* — test **both**:

1. The full allowed set (each allowed character class)
2. Each violation of the rule, separately (全角 digit, kana, kanji, symbol, space)

A single "invalid characters rejected" case is not enough; validation is usually
implemented per character class and fails unevenly.

## Length limits with multi-byte characters

A `VARCHAR(10)` limit means different things per layer. Test the boundary in **characters**
and in **bytes**:

```text
10 half-width characters   (10 bytes UTF-8)
10 full-width characters   (30 bytes UTF-8)
10 surrogate-pair emoji    (40 bytes UTF-8)
```

Frontend counts characters, database counts bytes — the mismatch is where truncation and
save failures live.

## Display, not just storage

* Does the stored value round-trip unchanged after reload?
* Does the value display correctly in lists, PDF/Excel exports, and email?
* Does sorting behave sensibly for kana/kanji?
* Does search find the record when the query uses the other width (`ｱｲｳ` finding `アイウ`)?

Export and search are separate code paths from the input form. A value that saves fine can
still break the CSV export.
