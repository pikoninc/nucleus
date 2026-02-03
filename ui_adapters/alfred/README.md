# Alfred UI Adapter (CLI bridge)

This repository's Alfred adapter is implemented as a **CLI bridge**:

- Alfred passes its `{query}` string to `nuc alfred --query ...`
- The command prints a **contract-shaped `Intent` JSON** to stdout
- Execution is still performed by running the Intent through the kernel (plan-first)

## Output behavior
Alfred itself is the UI, but this bridge is intentionally minimal:
- **stdout**: emitted `Intent` JSON (for piping/interop)
- **default renderer**: terminal stdout/stderr when the next layer executes the intent/plan

## Query grammar (minimal)

- `tidy configure`
  - emits `desktop.tidy.configure`
- `tidy preview <config_path>`
  - emits `desktop.tidy.preview`
- `tidy run <config_path>`
  - emits `desktop.tidy.run`
- `tidy restore <config_path>`
  - emits `desktop.tidy.restore`
- `tidy <config_path>`
  - shorthand for preview (`desktop.tidy.preview`)
- `tidy legacy [target_dir]`
  - emits legacy `desktop.tidy` (defaults to `~/Desktop`)

## Examples

```bash
# Preview from config
nuc alfred --query "tidy preview ~/DesktopRules.yml"

# Execute tidy from config (kernel run happens elsewhere)
nuc alfred --query "tidy run ~/DesktopRules.yml"

# Legacy tidy defaults into <target_dir>/_Sorted
nuc alfred --query "tidy legacy ~/Desktop"
```

