import os
import re

# Directory where all your MDX article files live
ARTICLES_DIR = os.path.join("src", "content", "articles")

# Regex patterns to locate frontmatter boundaries and slug/layout lines
FRONTMATTER_START = re.compile(r"^---\s*$")
FRONTMATTER_END   = re.compile(r"^---\s*$")
SLUG_LINE         = re.compile(r"^\s*slug\s*:\s*.+$", re.IGNORECASE)
LAYOUT_LINE       = re.compile(r"^\s*layout\s*:\s*.+$", re.IGNORECASE)

def clean_file(path: str) -> None:
    """
    Opens a .mdx file, removes any lines beginning with `slug:` or `layout:`
    inside the top-frontmatter section, then writes it back if changed.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    in_frontmatter = False
    changed = False

    for i, line in enumerate(lines):
        # Detect frontmatter block start/end
        if FRONTMATTER_START.match(line):
            # Toggle frontmatter on/off (first occurrence → enter; second → exit)
            in_frontmatter = not in_frontmatter
            new_lines.append(line)
            continue

        if in_frontmatter:
            # If this line is a slug: or layout: line, skip it
            if SLUG_LINE.match(line) or LAYOUT_LINE.match(line):
                changed = True
                # (Do not append this line—it is removed.)
                continue

        # Otherwise, keep the line unchanged
        new_lines.append(line)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Cleaned frontmatter in: {path}")

def main():
    if not os.path.isdir(ARTICLES_DIR):
        print(f"ERROR: '{ARTICLES_DIR}' not found. Run this from your project root.")
        return

    for root, dirs, files in os.walk(ARTICLES_DIR):
        for filename in files:
            if filename.lower().endswith(".mdx"):
                clean_file(os.path.join(root, filename))

if __name__ == "__main__":
    main()
