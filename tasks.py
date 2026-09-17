from invoke import task


@task
def format(ctx):
    """Format all markdown files."""
    ctx.run("uv run rumdl fmt .", pty=True)


@task
def lint(ctx):
    """Run all linters (markdown + YAML + CLI invocations + docs sidebar)."""
    ctx.run("uv run rumdl check .", pty=True)
    ctx.run("uv run yamllint -c .yamllint.yml .", pty=True)
    ctx.run("uv run python scripts/check-cli-invocations.py", pty=True)
    ctx.run("uv run python scripts/check-docs-sidebar.py", pty=True)


@task
def test(ctx):
    """Run the test suite (grader libraries and bundled skill scripts)."""
    ctx.run("uv run --group test pytest", pty=True)


@task
def freshness(ctx):
    """Check the installed plugin against this working tree."""
    ctx.run("uv run python scripts/check-plugin-freshness.py", pty=True, warn=True)
