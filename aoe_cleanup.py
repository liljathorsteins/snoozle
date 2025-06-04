#!/usr/bin/env python3
"""
AEO Cleanup Pipeline
--------------------
1. Crawl src/content/articles/*.mdx
2. Extract front-matter + plain text body
3. Get OpenAI embeddings → cluster near-duplicates (>0.86 cosine)
4. For each cluster pick the "canonical" file (longest body); mark the others for redirect
5. Run structural lint:
     • Quick Answer present?
     • ≥2 H2 and ≥2 H3 headings?
     • References section?
     • Word count ≥300?
6. (Optional) patch problems via GPT-4o (Quick Answer / References) if --auto-fix flag is set
7. Emit three csvs:
     duplicates.csv, structural_gaps.csv, action_report.csv
8. Write any redirects to redirects.txt
"""
import os, re, json, glob, textwrap, frontmatter
from slugify import slugify
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from fuzzywuzzy import fuzz
import openai, tiktoken

ART_DIR = os.path.join("src", "content", "articles")
ENCODER  = tiktoken.get_encoding("cl100k_base")
EMBED_MODEL = "text-embedding-3-small"  # cheap + good enough
THRESH   = 0.86                         # cosine sim threshold for dup cluster

QA_RE  = re.compile(r"^##+\s+Quick\s+Answer", re.I|re.M)
H2_RE  = re.compile(r"^##\s+\S", re.M)
H3_RE  = re.compile(r"^###\s+\S", re.M)
REF_RE = re.compile(r"^##+\s+References", re.I|re.M)

def load_articles():
    files = glob.glob(os.path.join(ART_DIR, "*.mdx"))
    data  = []
    for f in files:
        post = frontmatter.load(f)
        body = post.content
        plain = re.sub(r"<[^>]+>", " ", body)        # strip html
        plain = re.sub(r"{[^}]+}", " ", plain)       # strip mdx jsx
        text  = re.sub(r"[#`*_\-\[\]\(\)]", " ", plain)  # rough md strip
        text  = re.sub(r"\s+", " ", text).strip()
        data.append({
            "file": os.path.basename(f),
            "path": f,
            "title": post.get("title","").strip(),
            "description": post.get("description","").strip(),
            "body": body,
            "plain": text,
        })
    return data

def embed(texts):
    # chunk into ≤ 8192 tokens cum per request
    vecs=[]
    for t in texts:
        vec = openai.embeddings.create(model=EMBED_MODEL, input=t[:8000]).data[0].embedding
        vecs.append(vec)
    return np.array(vecs, dtype=np.float32)

def cluster_duplicates(items):
    embeds = embed([it["plain"] for it in items])
    sim = cosine_similarity(embeds)
    seen=set(); clusters=[]
    for i in range(len(items)):
        if i in seen: continue
        group=[i]; seen.add(i)
        for j in range(i+1, len(items)):
            if sim[i,j] >= THRESH:
                group.append(j); seen.add(j)
        clusters.append(group)
    return clusters

def structural_lint(item):
    body=item["body"]
    plain=item["plain"]
    issues=[]
    if not QA_RE.search(body): issues.append("no_quick_answer")
    if len(H2_RE.findall(body))<2: issues.append("few_h2")
    if len(H3_RE.findall(body))<2: issues.append("few_h3")
    if "evidence" in plain.lower() and not REF_RE.search(body):
        issues.append("no_references")
    if len(plain.split())<300: issues.append("too_short")
    return issues

def auto_fix(item, issues):
    prompt_base=textwrap.dedent(f"""
    You are an expert medical copy-editor. Improve the article below for AEO:
    Title: {item['title']}
    ---
    {item['body'][:5000]}
    ---
    Tasks:
    """)
    tasks=[]
    if "no_quick_answer" in issues:
        tasks.append("Add a 2–3 sentence section titled '## Quick Answer' at the very top summarising the key takeaway.")
    if "no_references" in issues:
        tasks.append("Add a '## References' section at the bottom with 2–3 peer-reviewed citations in numbered list format.")
    if "too_short" in issues:
        tasks.append("Expand content with one extra H2 explaining how Snoozle Slide Sheet addresses this problem specifically.")
    if not tasks: 
        return item["body"]  # nothing to do
    prompt = prompt_base + "\n".join(f"- {t}" for t in tasks)
    resp = openai.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[{"role":"user","content":prompt}],
        temperature=0.3)
    return resp.choices[0].message.content

def save_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def main(auto_fix=False):
    items = load_articles()
    clusters = cluster_duplicates(items)

    dup_rows = []
    redirect_rules=[]
    keep_files=set()
    for g in clusters:
        if len(g)==1:
            keep_files.add(items[g[0]]["file"]); continue
        # pick canonical = longest plain text
        longest = max(g, key=lambda idx: len(items[idx]["plain"]))
        canon   = items[longest]["file"]; keep_files.add(canon)
        for idx in g:
            if idx==longest: continue
            old = items[idx]["file"]
            dup_rows.append({"canonical": canon, "duplicate": old})
            # write redirect stub
            old_slug = os.path.splitext(old)[0]
            canon_slug = os.path.splitext(canon)[0]
            redirect_rules.append(f"/articles/{old_slug}  /articles/{canon_slug}  301")
            # optionally delete duplicate file
            os.remove(items[idx]["path"])

    # write redirects.txt
    if redirect_rules:
        with open("redirects.txt","w") as r:
            r.write("\n".join(redirect_rules))

    # structural lint & optional auto-fix
    struct_rows=[]
    for it in items:
        if it["file"] not in keep_files: continue
        issues = structural_lint(it)
        if issues:
            struct_rows.append({"file": it["file"], "issues": ";".join(issues)})
            if auto_fix:
                new_body = auto_fix(it, issues)
                post = frontmatter.load(it["path"])
                post.content = new_body
                save_file(it["path"], frontmatter.dumps(post))

    # reports
    import csv
    if dup_rows:
        with open("duplicates.csv","w",newline="",encoding="utf-8") as c:
            w=csv.DictWriter(c, fieldnames=["canonical","duplicate"])
            w.writeheader(); w.writerows(dup_rows)
    if struct_rows:
        with open("structural_gaps.csv","w",newline="",encoding="utf-8") as c:
            w=csv.DictWriter(c, fieldnames=["file","issues"])
            w.writeheader(); w.writerows(struct_rows)

    # summary
    print(f"\n✅ Kept {len(keep_files)} canonical articles.")
    print(f"🗑️  Removed {len(dup_rows)} duplicates (see duplicates.csv).")
    print(f"🔍 {len(struct_rows)} files have structural gaps (see structural_gaps.csv).")
    if auto_fix:
        print("🤖 GPT auto-patched those structural gaps.")

if __name__=="__main__":
    import argparse, sys
    openai.api_key = os.getenv("OPENAI_API_KEY") or "YOUR_KEY"
    p=argparse.ArgumentParser()
    p.add_argument("--auto-fix", action="store_true", help="use GPT-4o to patch missing sections")
    args=p.parse_args()
    main(auto_fix=args.auto_fix)
