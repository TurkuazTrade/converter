# Converter Worker

Reserved boundary for future asynchronous Excel/file processing.

The converter currently belongs in `apps/api` because it shares clients, products, orders, mappings, storage, and export history with the main CRM workflow.

Move work here only when conversion/import/export jobs become too heavy for request-response API handling.

Good triggers:

- large files block normal API requests
- uploads need queueing
- retries or resumable jobs are required
- conversion progress must be tracked independently
- failures should not affect the main API process

Until then, keep converter configs and tests in `apps/api`.
