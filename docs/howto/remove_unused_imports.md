# Removing Unused Imports

## Quick Method

```bash
# Find all unused imports
python -m pylint --disable=all --enable=unused-import --recursive=y .

# Remove all unused imports automatically
pip install autoflake
autoflake --remove-all-unused-imports --recursive --in-place .
```

## Step-by-Step Process

1. **Check for unused imports**:

   ```bash
   python -m pylint --disable=all --enable=unused-import --recursive=y .
   ```

2. **Generate detailed report** (optional):

   ```bash
   python -m pylint --disable=all --enable=unused-import --output-format=text --recursive=y . | grep "W0611" > unused_imports.txt
   ```

3. **Preview changes** before applying:

   ```bash
   autoflake --remove-all-unused-imports --recursive --verbose .
   ```

4. **Apply fixes** automatically:

   ```bash
   autoflake --remove-all-unused-imports --recursive --in-place .
   ```

5. **Verify** all issues are fixed:

   ```bash
   python -m pylint --disable=all --enable=unused-import --recursive=y .
   ```

## Automating Checks

Add to CI pipeline or pre-commit hooks:

```yaml
# In .pre-commit-config.yaml
- repo: https://github.com/pycqa/pylint
  rev: v2.17.0
  hooks:
    - id: pylint
      args: ["--disable=all", "--enable=unused-import"]
```
