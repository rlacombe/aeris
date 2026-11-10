# Result

Status: exposure reconstruction in progress.

Completed inputs:

- Official Ministry of Health archive: 29,971,992 line-list records scanned.
- Study-window confirmed records: 1,517,303.
- Outcome departments: 550 before geography matching.
- Department boundaries joined by official Georef centroids: 508.

The unmatched records are retained in
`data/derived/department_boundary_join_audit.csv`. They include CABA commune
codes and unspecified residence codes that do not have a one-to-one ADM2
polygon in the joined sources.

Strict AERIS pilot, La Matanza (department `06427`): no PM2.5 monitor lies
inside the boundary for 1 March through 31 December 2020. The documented
25 km representative-point sensitivity also found no usable PM2.5 series.

No effect estimate is reported yet. The full strict pass must establish the
number of departments with valid AERIS PM2.5 records before the ecological
correlation can be fitted.
