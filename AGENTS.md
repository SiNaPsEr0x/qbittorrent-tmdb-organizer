# Repository instructions

- Keep tracked scripts and documentation generic and suitable for public use.
- Never commit or push personal API tokens, passwords, credentials, host ports,
  absolute media paths, or other machine-specific configuration.
- Keep `tmdb_prepare.local.py` local and ignored. Preserve its personal values
  when refreshing it from the public script.
- Before every commit and push, inspect tracked files and the staged diff for
  secrets and personal configuration. Confirm the local script is ignored and
  absent from the index.
- Public examples must use placeholders or clearly fictional values.
