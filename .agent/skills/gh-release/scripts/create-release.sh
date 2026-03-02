#!/bin/bash
set -e

VERSION=$1
if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version>"
  exit 1
fi

if ! command -v gh &> /dev/null; then
    echo "gh command could not be found, please install it first"
    exit 1
fi

PYPROJECT="pyproject.toml"

if [ ! -f "$PYPROJECT" ]; then
    echo "Error: No pyproject.toml found in the current directory."
    exit 1
fi

# Using python to update the toml file safely
python -c "
import re
from pathlib import Path

content = Path('$PYPROJECT').read_text()
content = re.sub(
    r'^version\s*=\s*\"[^\"]*\"',
    'version = \"$VERSION\"',
    content,
    count=1,
    flags=re.MULTILINE,
)
Path('$PYPROJECT').write_text(content)
print(f'Updated $PYPROJECT to version $VERSION')
"

git add "$PYPROJECT"
git commit -m "chore(release): $VERSION"
gh release create "$VERSION" --generate-notes
