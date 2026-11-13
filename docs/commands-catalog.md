# Commands catalog

Machine-readable catalog: [`data/commands.yaml`](../data/commands.yaml)
(schema: [`schema/commands.schema.json`](../schema/commands.schema.json)).

## Sections

| Key | Purpose |
|-----|---------|
| `cmd_internal_commands` | True cmd.exe internals (verbs not resolved as separate PATH executables) |
| `stock_windows_utilities` | Stock Windows PATH/`System32` utilities commonly used from batch |
| `builtin_commands` | Union of the two lists above for "is this a Windows/cmd command?" detection |
| `command_aliases` | Alias verb → canonical name (`chdir`→`cd`, `erase`→`del`, …) |
| `common_external_tools` | Third-party / language / package-manager CLIs commonly recognized by tooling |
| `deprecated_commands` | Still present or optionally available, but deprecated for new use |
| `removed_commands` | Historical commands no longer part of modern Windows cmd |
| `older_windows_commands` | DOS-era / legacy names retained for detection |
| `common_command_typos` | Frequent misspellings mapped to intended commands |
| `builtin_overlap_deprecated_notes` | Notes when a name is both detected and flagged deprecated |

## Guidance

- Prefer `cmd_internal_commands` when the distinction matters: true internals are never overridden by a same-named file in the current directory. Prefer `stock_windows_utilities` for PATH/`System32` tools that **can** be shadowed by a CWD `.bat`/`.cmd`/`.exe` according to PATHEXT (see `command_resolution.cwd_shadows_externals` in [`data/expansion.yaml`](../data/expansion.yaml)).
- Prefer `builtin_commands` for broad "is this a Windows/cmd command?" checks (it is the union of internals and stock utilities).
- Use `command_aliases` to canonicalize alias peers (`chdir`/`mkdir`/`erase`/`rename`/`rmdir`) to their primary names; both spellings remain in the detection lists.
- Use `common_external_tools` for optional recognition of developer tooling without implying Windows stock commands.
- Stock utilities such as `curl`, `tar`, `telnet`, and `wmic` remain in `stock_windows_utilities` / `builtin_commands` for detection, but may be absent on older or Feature-on-Demand-stripped hosts (`builtin_overlap_deprecated_notes`).
- For the machine name in scripts prefer `%COMPUTERNAME%`; `hostname` is the external `hostname.exe` printer, not a cmd internal.
- `removed_commands` lists commands that shipped with DOS or Windows and are absent on modern cmd. `graftabl` is still listed by HELP, and `edlin` was a 16-bit tool on 32-bit Windows only. Resource Kit and Sysinternals tools are not part of this catalog. Some `deprecated_commands` remain as cmd internals with no useful effect (for example `keys`).
- Captured help under [`audit/cmd-help/`](../audit/cmd-help/) is a language-relevant subset (internals and high-impact stock tools such as `find` / `findstr` / `robocopy` / `fc` / `comp` / `attrib` / `tree` / `reg` / `replace` / `dpath` / `keys` / `mode` / `label` / `print` / `hostname` / `whoami` / `tasklist` / `taskkill` / `icacls` / `certutil` / `clip` / `waitfor` / `msg` / `ipconfig` / `ping` / `net` / `sc` / `schtasks` / `systeminfo` / `takeown` / `fsutil` / `compact` / `cipher` / `arp` / `route` / `netstat`), not a full dump of every detection name. Alias pairs share one help file (`cd`/`chdir`, `md`/`mkdir`, `rd`/`rmdir`, `del`/`erase`, `ren`/`rename`). The HELP utility itself does not list `dpath` / `keys` — use `dpath /?` / `keys /?` (and the captured help files) instead.
