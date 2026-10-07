# Copilot instructions

Use the repository-wide [`AGENTS.md`](../AGENTS.md) for architecture, safe-edit boundaries, and verified run/test commands.

- Check the applicable design/plan in `docs/superpowers/` before architectural changes.
- Preserve behavior across FastAPI (`server/`), Electron (`desktop-app/`), and Android (`android/`) where a feature crosses clients.
- Keep generated artifacts, local config, databases, and stored user files out of commits; see `.gitignore`.
- Verify changes with the narrowest relevant test first. Do not claim checks passed unless run.
