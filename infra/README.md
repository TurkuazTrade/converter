# Infra

Reserved home for deployment and operations configuration.

The current development entrypoint is still the root `docker-compose.yml`. Add files here only when the project needs environment-specific infrastructure, for example:

- production or staging compose profiles
- reverse proxy configuration
- deployment scripts
- environment templates
- backup/restore notes
- TLS, domain, and routing documentation

Keep local-only setup in the root README unless it is specific to deployment.
