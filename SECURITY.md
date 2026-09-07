# Security Policy

## Reporting a vulnerability

If you find a security issue in SlopScan -- an SSRF bypass, a ZIP-extraction
escape, a way to trigger code execution from a scanned target, or anything
similar -- please **do not** open a public GitHub issue. Instead, email the
maintainers (see the repository's contact info) with:

- A description of the issue and its impact
- Steps to reproduce, or a minimal proof of concept
- Which version/commit you tested against

We'll acknowledge reports within a few days and aim to ship a fix before
any public disclosure.

## Threat model

SlopScan's job is to analyze content it does not control -- arbitrary
websites, arbitrary GitHub repositories, arbitrary ZIP archives someone
hands it. That means every target type is treated as untrusted input.
The sections below describe what SlopScan actively defends against, and
what it deliberately never does.

### Live website scanning (SSRF)

`slopscan analyze <url>` fetches the requested page (and a small, bounded
number of same-origin linked stylesheets) over HTTP. Before any request is
made, `slopscan.utils.security.validate_url`:

- Rejects non-`http(s)` schemes outright (no `file://`, `ftp://`,
  `gopher://`, etc.)
- Resolves the hostname via DNS and rejects it if it has no hostname or
  fails to resolve
- Rejects the request if **any** resolved IP address is loopback, private
  (RFC 1918), link-local (including the `169.254.169.254` cloud metadata
  address), reserved, multicast, or unspecified
- Rejects `localhost` and `*.local` hostnames explicitly

This check runs again on **every redirect hop** -- SlopScan follows
redirects manually rather than letting the HTTP client follow them
transparently, specifically so a redirect to an internal address can't
slip past the initial check. Requests also have a connection/read timeout
and a response-size cap, and stylesheet fetching is limited to a small,
same-origin set of URLs (no arbitrary crawling by default).

This defends against SSRF and naive DNS-rebinding, but it is not a
substitute for network-level egress controls if you're running SlopScan in
a sensitive environment (e.g. inside a cloud VPC) -- for defense in depth,
also restrict outbound network access at the infrastructure level if you
can.

### ZIP archive scanning

`slopscan analyze <file>.zip` extracts to a temporary directory before
scanning. Before extracting anything, `slopscan.targets.archive`:

- Rejects entries with absolute paths or `..` path-traversal components
- Rejects entries whose resolved final path would land outside the
  extraction directory
- Skips symlink entries entirely (never follows them)
- Rejects the whole archive if it has more than ~20,000 entries
- Rejects individual entries whose compression ratio exceeds ~200x
  (a classic zip-bomb signature), before any size-based skip logic runs
- Enforces a total-uncompressed-size ceiling (200MB by default) and skips
  individual entries larger than the configured per-file limit
- Always cleans up the temporary extraction directory afterward, even on
  error

Nothing extracted from a ZIP is ever executed, and no package manager or
build tool is ever invoked against it.

### GitHub repository scanning

SlopScan never clones a repository or runs `git`. It uses the public
GitHub REST API to list a repository's file tree and fetch individual file
contents as raw text, for a bounded number of recognized source-file
extensions. Nothing from the repository is executed. Unauthenticated
access works for public repositories; an optional `GITHUB_TOKEN` /
`SLOPSCAN_GITHUB_TOKEN` only raises the API rate limit and is never
required.

### Local directory / general execution policy

SlopScan performs **static analysis only**. Regardless of target type, it
never:

- Runs `npm install`, `pip install`, `cargo build`, `docker build`,
  `make`, or any other build/install command against scanned content
- Executes scanned source code, scripts, or binaries in any language
- Runs package.json scripts, Makefiles, or CI configuration it finds

If a future sandboxed-execution feature is ever added, it will be
explicitly opt-in and clearly documented as a change to this policy.

### AI-enhanced mode

The optional `--ai` mode sends only aggregated, structured evidence
(rule ids, categories, severities, occurrence counts, short evidence
strings) to the configured provider -- never raw source files, full page
HTML, or your API key in any logged/reported output. See
[docs/ai-mode.md](docs/ai-mode.md) for the exact payload shape. API keys
are read from the `SLOPSCAN_AI_API_KEY` environment variable (or an
equivalent session-only mechanism) and are never written to disk, logs, or
reports by SlopScan itself.

### What SlopScan does not defend against

- **Malicious content designed to fool the pattern rules themselves**
  (e.g. text engineered to break a regex) is a correctness/robustness
  concern, not a security one -- rules are written defensively (bounded
  loops, size limits before regex matching) but this isn't a hardened
  parser.
- SlopScan does not sandbox its own process. If you're scanning a target
  you don't trust at all and want extra isolation, run SlopScan itself
  inside a container or VM as an additional layer.

## Dependencies

SlopScan's dependency list is intentionally small (`typer`, `rich`,
`httpx`, `beautifulsoup4`, `lxml`, `pydantic`, `tomli-w`). Optional extras
(`playwright` for future browser rendering, dev tools) are never installed
by default. We don't currently run automated dependency-vulnerability
scanning in CI, but keeping the dependency surface small is a deliberate
mitigation in itself; contributions to add `pip-audit` or similar to CI are
welcome.
