# Reports Worker

Reserved boundary for scheduled and heavy report generation.

Keep simple report endpoints in `apps/api`. Move work here when a report is too slow for a normal HTTP request or needs planned background execution.

Good triggers:

- large Excel/PDF generation
- scheduled daily/weekly reports
- report retries
- long-running aggregations
- report delivery through email or external systems

Generated report files should be stored under the project storage layer, not committed to the repository.
