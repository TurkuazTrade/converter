# Shared Package

Reserved home for shared contracts and small reusable helpers.

Do not move code here just to make it look reusable. Add shared code only when at least two runtime boundaries need the same thing, such as:

- API response/request types used by web and workers
- generated client contracts
- shared enum definitions
- small normalization helpers with stable behavior

Keep domain logic in `apps/api` until another app or worker truly needs it.
