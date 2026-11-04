# calendar.csv: method notes

Compiled 2026-11-03. Window: 2026-11-03 to 2028-11-03 (24 months).

## Columns

| column | meaning |
|---|---|
| `id` | stable key, `<iso2>-<year>-<type>`; a run-off gets its own row `<id>-r2` once it is called |
| `date` | vote date (local). For `due_by` rows it is the **latest legal date**, not a forecast |
| `type` | `presidential`, `legislative`, `general` (presidential and legislative on the same day) or `referendum` |
| `rounds` | 2 when a run-off is possible; the run-off row is added only once round 1 makes it necessary |
| `status` | `scheduled`: date fixed by law or set by the election authority. `due_by`: only a legal deadline is known. Later values: `held`, `postponed` |
| `source_url` | Wikipedia permalink (exact revision) used for the date |

The tracker acts on a row (90-day poll window, 14-day pre-registration) only when its status is `scheduled`; a
`due_by` row is polled but not pre-registered until the weekly refresh finds a set date.

## Universe

Original study universe (Brazil, Mexico, South Africa, Turkey, Indonesia, Poland) **plus** every emerging-market
country that passes the spec's section 9 rules:

1. MSCI Emerging Markets constituent country.
2. Floating or free-floating under the IMF AREAER de facto classification (2023 report, as tabulated on Wikipedia's
   [List of countries by exchange rate regime](https://en.wikipedia.org/w/index.php?title=List_of_countries_by_exchange_rate_regime&oldid=1369823927)).
   Pegs, crawling/crawl-like and other managed arrangements are excluded (ARS and onshore CNY explicitly).
3. Currency in the BIS Triennial Survey top 35 (April 2025, via
   [Template:Most traded currencies](https://en.wikipedia.org/w/index.php?title=Template:Most_traded_currencies&oldid=1377199205), citing BIS rpfx25).
4. At least 36 months of daily data (all qualifying currencies pass).

Qualifying currencies: BRL, CLP, COP, CZK, HUF, IDR, INR, KRW, MXN, MYR, PEN, PHP, PLN, THB, ZAR, plus TRY through the
original study.

**Turkey is flagged.** AREAER 2023 classifies Turkey as a crawl-like arrangement, which fails rule 2. It is kept
because it is in the original study's universe, and spec section 8 already says to flag TRY. Drop the row if the
section 9 rule should override the study's universe.

Event types: national presidential and legislative elections and nationwide referendums, as requested. Run-offs are
separate events, as in the study.

## Sources and checks

- **IFES ElectionGuide** (`/elections/type/upcoming/`, `/elections/type/anticipated/` and the country pages,
  fetched 2026-11-03) lists elections only through 18 Jul 2027 and has **no entry yet** for any row in this
  calendar, including Mexico 2027. It confirms that no qualifying national vote falls between today and 6 Jun 2027.
  The weekly refresh re-checks it and logs matches in `calendar_checks.csv`.
- **Wikipedia** election pages (permalinks in `source_url`) give the dates:
  - Mexico: 6 Jun 2027 (first Sunday of June, by law). The Spanish page also gives 6 Jun 2027 (es.wikipedia oldid 176050527).
  - Poland: by 11 Nov 2027. The President sets the date: possible dates are 17, 24 and 31 Oct, 1, 7 and 11 Nov 2027.
  - Czech Republic: "by January 2028". Pavel's term ends in March 2028. The run-off would be two weeks after round 1.
  - Malaysia: automatic dissolution 19 Dec 2027, so the vote is due by 17 Feb 2028. It may come earlier at the
    Prime Minister's request.
  - South Korea: 12 Apr 2028. Fixed by law: the first Wednesday from the 50th day before the National Assembly's
    term ends. There is no dissolution.
  - Philippines: 8 May 2028 (second Monday of May, by law), presidential and congressional on the same day. Single
    round, plurality.
  - Turkey: presidential page "by 14 May 2028", parliamentary page "on or before 7 May 2028" (oldid 1377466416; the
    two pages disagree). Presidential and parliamentary votes are held together; a run-off would come two weeks
    later. Snap elections are possible.

## Considered and excluded

| Vote | Date | Reason |
|---|---|---|
| South Africa municipal elections | 4 Nov 2026 | Local, not national (and too close to pre-register) |
| Taiwan presidential and legislative | Jan 2028 (Wikipedia: "during 2028") | TWD is in the BIS top 35 and MSCI EM, but Taiwan is not an IMF member, so it has no AREAER classification (rule 2 cannot be met). A judgment call: add it if you treat TWD as managed-floating |
| Taiwan national referendum | Aug 2027, only if proposals qualify | As above |
| Mexico federal judicial election | 2028 (es.wikipedia "Elecciones federales judiciales de México de 2028"; no date) | Judicial, not presidential, legislative or referendum. The study did include Mexico's 2025 judicial vote |
| Mexico presidential recall (revocación de mandato) | Not scheduled | No request yet; it could be requested after Sep 2027. Add it if it is called |
| Nigeria general election | 16 Jan 2027 (ElectionGuide) | NGN is not in the BIS top 35 |
| Argentina general election | Oct 2027 | ARS is excluded by rule 2 |
| Kenya general election | Aug 2027 | KES is not in the BIS top 35 |
| Brazil, Chile, Colombia local elections | 2027–28 | Local |
| Romania parliamentary | Dec 2028 | Outside the window; Romania is not MSCI EM |
| Hungary (2030), Thailand (by Mar 2030), India (2029), Indonesia (2029), South Africa general (by Aug 2029), Chile (Nov 2029), Colombia (2030), Brazil (2030), Peru (2031) | | Outside the window |
