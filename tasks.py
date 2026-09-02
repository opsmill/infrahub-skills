from invoke import task


@task
def format(ctx):
    """Format all markdown files."""
    ctx.run("uv run rumdl fmt .", pty=True)


@task
def lint(ctx):
    """Run all linters (markdown + YAML + CLI invocations)."""
    ctx.run("uv run rumdl check .", pty=True)
    ctx.run("uv run yamllint -c .yamllint.yml .", pty=True)
    ctx.run("uv run python scripts/check-cli-invocations.py", pty=True)
