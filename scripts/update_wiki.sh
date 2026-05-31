#!/bin/bash

# Exit on error
set -e

# Configuration
REPO_URL="https://github.com/Naxeron/gwolves-battery-indicator.wiki.git"
WIKI_DIR="/tmp/gwolves_wiki_update"
DOCS_DIR="$(dirname "$0")/../docs"

echo "Updating GitHub Wiki from docs..."

# Clean up previous temporary directory if it exists
rm -rf "$WIKI_DIR"

# Clone the wiki repository
git clone "$REPO_URL" "$WIKI_DIR"

# Copy all markdown files from docs to the wiki repository
cp -a "$DOCS_DIR"/*.md "$WIKI_DIR/"

# Navigate to the wiki directory
cd "$WIKI_DIR"

# Check if there are any changes
if [[ -z $(git status -s) ]]; then
    echo "No changes to commit. Wiki is up to date."
    rm -rf "$WIKI_DIR"
    exit 0
fi

# Add, commit, and push changes
git add .
git commit -m "docs: sync wiki from docs/ directory"
git push origin master

# Clean up
rm -rf "$WIKI_DIR"

echo "Wiki updated successfully!"
