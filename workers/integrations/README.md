# Integrations Worker

Reserved boundary for external system integrations.

Use this worker when integrations become slow, retry-heavy, scheduled, or unreliable enough that they should not run inside normal API requests.

Typical responsibilities:

- external API synchronization
- webhook processing
- retry queues
- scheduled imports/exports
- integration audit logs

Keep integration contracts explicit: the API should enqueue or record work, while the worker owns retries and external communication.
