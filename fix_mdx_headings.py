import os
import re

# Path to your MDX articles folder
ARTICLES_DIR = os.path.join("src", "content", "articles")

# 1) Unclosed heading tags, e.g. "<h2>Text" → "<h2>Text</h2>"
heading_open_pattern = re.compile(r"^(\s*)<h([1-6])>([^<\n\r]+?)(\s*)$")

# 2) Stray closing heading tags in list items, e.g. "- </h3>…"
stray_heading_close_pattern = re.compile(r"^(\s*-\s*)</h([1-6])>(.*)$")

# 3) Heading incorrectly closed with </p><p>, e.g. "<h2>Fazit</p><p>Text…"
heading_wrong_close_pattern = re.compile(
    r"^(\s*)<h([1-6])>([^<]+?)</p><p>(.*)$"
)

# 4) Unclosed inline tags on a line by themselves, e.g. "<strong>Important"
inline_tags = ["strong", "em", "u", "a", "code", "span"]
inline_open_pattern = re.compile(
    r"^(\s*)<(" + "|".join(inline_tags) + r")>([^<\n\r]+?)(\s*)$"
)

# 5) Stray closing inline tags at start of list items, e.g. "- </strong>…"
stray_inline_close_pattern = re.compile(
    r"^(\s*-\s*)</(" + "|".join(inline_tags) + r")>(.*)$"
)

# 6) Unclosed block tags on a line by themselves, e.g. "<blockquote>Quote"
block_tags = ["p", "blockquote", "ul", "ol", "li"]
block_open_pattern = re.compile(
    r"^(\s*)<(" + "|".join(block_tags) + r")>([^\n\r<]+?)(\s*)$"
)

# 7) Stray closing block tags in list items, e.g. "- </p>…"
stray_block_close_pattern = re.compile(
    r"^(\s*-\s*)</(" + "|".join(block_tags) + r")>(.*)$"
)

# 8) Lines that contain "<p>" but no "</p>" anywhere → we will append "</p>"
p_open_without_close_pattern = re.compile(r"<p>(?!.*</p>)")

def fix_file(path: str) -> None:
    """
    Read the MDX file at `path`, apply multiple regex‐based fixes:
      1) Fix missing closing <hN> tags
      2) Remove stray </hN> in lists
      3) Fix <hN>…</p><p>…  to <hN>…</hN><p>…
      4) Fix unclosed <inlineTag> lines
      5) Remove stray </inlineTag> from lists
      6) Fix unclosed <blockTag> lines
      7) Remove stray </blockTag> from lists
      8) Append </p> to any line with "<p>" but no matching "</p>"
    Write the file back only if any changes occurred.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changed = False
    new_lines = []

    for line in lines:
        # 1) Unclosed <hN> → append </hN>
        m = heading_open_pattern.match(line)
        if m:
            indent, level, text, ws = m.groups()
            fixed = f"{indent}<h{level}>{text}</h{level}>{ws}\n"
            new_lines.append(fixed)
            changed = True
            continue

        # 2) Remove stray </hN> in list items
        m = stray_heading_close_pattern.match(line)
        if m:
            list_start, level, rest = m.groups()
            fixed = f"{list_start}{rest}\n"
            new_lines.append(fixed)
            changed = True
            continue

        # 3) Fix <hN>…</p><p>… → <hN>…</hN><p>…
        m = heading_wrong_close_pattern.match(line)
        if m:
            indent, level, heading_text, rest = m.groups()
            fixed = f"{indent}<h{level}>{heading_text}</h{level}><p>{rest}\n"
            new_lines.append(fixed)
            changed = True
            continue

        # 4) Unclosed inline tag → append </tag>
        m = inline_open_pattern.match(line)
        if m:
            indent, tag, text, ws = m.groups()
            fixed = f"{indent}<{tag}>{text}</{tag}>{ws}\n"
            new_lines.append(fixed)
            changed = True
            continue

        # 5) Remove stray closing inline tag in list items
        m = stray_inline_close_pattern.match(line)
        if m:
            list_start, tag, rest = m.groups()
            fixed = f"{list_start}{rest}\n"
            new_lines.append(fixed)
            changed = True
            continue

        # 6) Unclosed block tag → append </tag>
        m = block_open_pattern.match(line)
        if m:
            indent, tag, text, ws = m.groups()
            fixed = f"{indent}<{tag}>{text}</{tag}>{ws}\n"
            new_lines.append(fixed)
            changed = True
            continue

        # 7) Remove stray closing block tag in list items
        m = stray_block_close_pattern.match(line)
        if m:
            list_start, tag, rest = m.groups()
            fixed = f"{list_start}{rest}\n"
            new_lines.append(fixed)
            changed = True
            continue

        # 8) Append </p> if line contains "<p>" but no "</p>"
        if p_open_without_close_pattern.search(line):
            # Avoid double-appending if line already ends with </p>
            if "</p>" not in line:
                new_lines.append(line.rstrip("\n") + "</p>\n")
                changed = True
                continue

        # If no pattern matched, keep line unchanged
        new_lines.append(line)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Fixed MDX in: {path}")

def main():
    if not os.path.isdir(ARTICLES_DIR):
        print(f"ERROR: Directory not found: '{ARTICLES_DIR}'")
        print("Run this script from your project root (where 'src/content/articles' exists).")
        return

    for root, dirs, files in os.walk(ARTICLES_DIR):
        for filename in files:
            if filename.lower().endswith(".mdx"):
                fix_file(os.path.join(root, filename))

if __name__ == "__main__":
    main()
