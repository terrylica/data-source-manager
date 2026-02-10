# How-To Guides

Quick reference guides for common tasks in the codebase.

## Guides

- [Cache Control](ckvd_cache_control.md) - Enable/disable caching, environment variable control
- [Logging Control](ckvd_logging_control.md) - Log level configuration, CKVD_LOG_LEVEL env var

## Testing

Run tests using mise tasks:

```bash
# Run unit tests
mise run test

# Run all tests
mise run test:all

# Run with coverage
mise run test:cov
```

## AWS CLI Commands

Always use the `--no-cli-pager` flag with AWS CLI commands:

```bash
# Good
aws s3 ls --no-cli-pager

# Bad
aws s3 ls
```

## Git Operations

Move or rename files using git:

```bash
# Move a file (preserves history)
git mv old_path/file.py new_path/file.py

# Rename a file
git mv old_name.py new_name.py

# Move a directory
git mv old_dir/ new_dir/
```
