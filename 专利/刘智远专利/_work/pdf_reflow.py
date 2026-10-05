# -*- coding: utf-8 -*-
"""IEEE two-column PDF -> logical paragraphs (char-level re-lining).

Why char level: LaTeX PDFs split stacked sub/superscripts (e.g. FP^c_v) and tight justified
lines into separate PyMuPDF lines/blocks, which breaks words and paragraphs. Here every glyph is
re-assigned to a visual baseline, small glyphs become sub/superscripts of the host line, and word
spaces are recovered from glyph gaps.
"""
import re
from collections import Counter

import pymupdf

LIG = str.maketrans({"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl"})
TERMINAL = tuple(".:?!")
SKIP_PREFIX = ("This article has been accepted", "Authorized licensed use", "1941-0050",
               "for more information", "Personal use is permitted")
KEEP_HYPHEN_TAILS = {"foot", "based", "driven", "wise", "level", "first", "specific", "borne",
                     "joining", "triangular", "category"}


def is_math(font: str) -> bool:
    return font.startswith(("CM", "MSBM", "MT2"))


def column_of(bbox):
    return 0 if (bbox[0] + bbox[2]) / 2 < 297 else 1


def runs_text(runs):
    return "".join(t for t, _ in runs)


def _style(font, vert):
    bold = "Bold" in font or font.startswith("CMBX")
    italic = "Oblique" in font or "Italic" in font or font.startswith("CMMI")
    return (bold, italic, vert)


# ----------------------------------------------------------------------------- glyphs -> lines
def _group_by_baseline(chars, tol=1.6):
    lines = []
    for c in sorted(chars, key=lambda c: c["oy"]):
        if lines and abs(c["oy"] - lines[-1]["base"]) <= tol:
            lines[-1]["chars"].append(c)
        else:
            lines.append({"base": c["oy"], "chars": [c]})
    return lines


def _line_to_runs(ln, sz):
    order = {"sup": 0, None: 1, "sub": 2}
    chs = sorted(ln["chars"], key=lambda c: (round(c["x0"], 1), order[c.get("vert")]))
    runs, maxx1, need_space, hat, prev_vert = [], None, False, False, None

    def put(text, style):
        if runs and runs[-1][1] == style:
            runs[-1] = (runs[-1][0] + text, style)
        else:
            runs.append((text, style))

    for c in chs:
        ch = c["c"]
        if ch == " ":
            need_space = maxx1 is not None
            continue
        if ch == "\u02c6":          # math hat accent -> combine with the next letter
            hat = True
            continue
        # sub/superscripts (and punctuation right after them) sit a little right of the advance
        # width because of italic correction -> use a looser threshold there
        loose = c.get("vert") or (prev_vert and ch in ",.;:)]|")
        thr = (0.25 if loose else 0.08) * sz
        if maxx1 is not None and not need_space and c["x0"] - maxx1 > thr:
            need_space = True
        style = _style(c["font"], c.get("vert"))
        text = ch.translate(LIG)
        if hat and ch.isalpha():
            text += "\u0302"
            hat = False
        if need_space:
            put(" ", (style[0], style[1], None))
            need_space = False
        put(text, style)
        maxx1 = c["x1"] if maxx1 is None else max(maxx1, c["x1"])
        prev_vert = c.get("vert")
    return runs


def reline(chars):
    """chars: dicts(c,x0,x1,y0,y1,oy,size,font) -> [{'runs','bbox','size','font'}] top to bottom."""
    solid = [c for c in chars if c["c"].strip()]
    if not solid:
        return []
    sz = Counter(round(c["size"], 1) for c in solid).most_common(1)[0][0]
    # only visible body-size glyphs define baselines; spaces inherit the origin of a preceding
    # sub/superscript span, so they are attached afterwards like small glyphs
    big = [c for c in solid if c["size"] >= 0.86 * sz]
    small = [c for c in solid if c["size"] < 0.86 * sz]
    spaces = [c for c in chars if not c["c"].strip()]
    lines = _group_by_baseline(big)
    for ln in lines:
        xs = [c for c in ln["chars"] if c["c"].strip()] or ln["chars"]
        ln["x0"], ln["x1"] = min(c["x0"] for c in xs), max(c["x1"] for c in xs)

    orphans = []
    for c in small:
        best = None
        for ln in lines:
            dy = c["oy"] - ln["base"]
            if -0.75 * sz <= dy <= 0.6 * sz and ln["x0"] - 3 <= c["x0"] <= ln["x1"] + 12:
                if best is None or abs(dy) < abs(best[1]):
                    best = (ln, dy)
        if best is None:
            orphans.append(c)
            continue
        c["vert"] = "sub" if best[1] > 0.6 else ("sup" if best[1] < -0.6 else None)
        best[0]["chars"].append(c)
    lines += _group_by_baseline(orphans)
    lines.sort(key=lambda ln: ln["base"])
    for c in spaces:
        near = [ln for ln in lines if -0.75 * sz <= c["oy"] - ln["base"] <= 0.6 * sz
                and ln["chars"] and min(x["x0"] for x in ln["chars"]) - 3 <= c["x0"]
                <= max(x["x1"] for x in ln["chars"]) + 3]
        if near:
            host = min(near, key=lambda ln: abs(c["oy"] - ln["base"]))
            host["chars"].append(dict(c, vert=None))

    out = []
    for ln in lines:
        vis = [c for c in ln["chars"] if c["c"].strip()]
        if not vis:
            continue
        host = [c for c in vis if c.get("vert") is None] or vis
        bbox = pymupdf.Rect(min(c["x0"] for c in vis), min(c["y0"] for c in host),
                            max(c["x1"] for c in vis), max(c["y1"] for c in host))
        first = min(vis, key=lambda c: c["x0"])
        out.append({"runs": _line_to_runs(ln, sz), "bbox": bbox, "base": ln["base"],
                    "size": max(c["size"] for c in host), "font": first["font"],
                    "fsize": round(first["size"], 1)})
    return out


# ----------------------------------------------------------------------------- pages -> items
def parse_pages(doc, eq_windows, img_dir, dpi=300):
    """eq_windows: [(page, col, y0, y1)] display-equation clip windows (1-based page)."""
    items, fig_no = [], 0
    eq_done = set()
    for pno, page in enumerate(doc):
        blocks = page.get_text("rawdict")["blocks"]
        lefts, rights = {0: [], 1: []}, {0: [], 1: []}
        for b in blocks:
            if b["type"] == 0 and b["lines"] and b["lines"][0]["spans"]:
                sp = b["lines"][0]["spans"][0]
                if sp["font"] == "Times-Roman" and abs(sp["size"] - 10) < 0.2:
                    lefts[column_of(b["bbox"])].append(b["bbox"][0])
                    rights[column_of(b["bbox"])].append(b["bbox"][2])
        col_left = {c: (min(v) if v else (38 if c == 0 else 301)) for c, v in lefts.items()}
        col_right = {c: (max(v) if v else (289 if c == 0 else 552)) for c, v in rights.items()}
        fig_boxes = [pymupdf.Rect(b["bbox"]) + (-3, -3, 3, 3) for b in blocks
                     if b["type"] == 1 and (b["bbox"][2] - b["bbox"][0]) > 80]
        wins = [(k, w) for k, w in enumerate(eq_windows) if w[0] == pno + 1]

        def eq_hit(col, cy):
            for k, (_, c, ya, yb) in wins:
                if c == col and ya <= cy <= yb:
                    return k
            return None

        def emit_eq(k):
            if k in eq_done:
                return
            eq_done.add(k)
            _, c, ya, yb = eq_windows[k]
            clip = pymupdf.Rect(col_left[c] - 1.5, ya, col_right[c] + 1.5, yb)
            path = img_dir / f"eq_{k + 1:02d}_p{pno + 1}.png"
            page.get_pixmap(clip=clip, dpi=dpi).save(path)
            items.append({"type": "equation", "path": path, "w_pt": clip.width})

        def emit_lines(lines, col):
            if not lines:
                return
            bb = pymupdf.Rect(lines[0]["bbox"])
            for l in lines[1:]:
                bb |= l["bbox"]
            items.append({"type": "block", "page": pno + 1, "col": col, "bbox": bb,
                          "font": lines[0]["font"], "size": lines[0]["fsize"],
                          "col_left": col_left[col], "lines": lines})

        cluster = []

        def flush():
            if not cluster:
                return
            col = column_of(cluster[0]["bbox"])
            chars, hits = [], set()
            for b in cluster:
                for l in b["lines"]:
                    for s in l["spans"]:
                        for ch in s["chars"]:
                            x0, y0, x1, y1 = ch["bbox"]
                            k = eq_hit(col, (y0 + y1) / 2)
                            if k is not None:
                                hits.add(k)
                                continue
                            chars.append({"c": ch["c"], "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                                          "oy": ch["origin"][1], "size": s["size"], "font": s["font"]})
            lines = reline(chars)
            solid = [c for c in chars if c["c"].strip()]
            if solid and sum(is_math(c["font"]) for c in solid) / len(solid) > 0.5 and not hits:
                print(f"  [warn] p{pno + 1} math-like text kept as prose: {runs_text(lines[0]['runs'])[:60]}")
            for k in sorted(hits, key=lambda k: eq_windows[k][2]):
                ya = eq_windows[k][2]
                above = [l for l in lines if l["base"] < ya]
                lines = [l for l in lines if l["base"] >= ya]
                emit_lines(above, col)
                emit_eq(k)
            emit_lines(lines, col)
            cluster.clear()

        def cluster_ok(b):
            if not cluster:
                return False
            f_new = b["lines"][0]["spans"][0]["font"]
            f_old = cluster[0]["lines"][0]["spans"][0]["font"]
            if f_new in ("Helvetica",) or f_old in ("Helvetica",) or "Bold" in f_new:
                return False
            cb = pymupdf.Rect(cluster[0]["bbox"])
            for x in cluster[1:]:
                cb |= pymupdf.Rect(x["bbox"])
            bb = pymupdf.Rect(b["bbox"])
            return column_of(bb) == column_of(cb) and min(cb.y1, bb.y1) - max(cb.y0, bb.y0) > 1.0

        for b in blocks:
            bb = pymupdf.Rect(b["bbox"])
            if bb.y1 < 46 or bb.y0 > 756:
                continue
            if b["type"] == 1:
                if bb.width <= 80:
                    continue  # journal logo
                flush()
                fig_no += 1
                path = img_dir / f"fig_{fig_no:02d}_p{pno + 1}.png"
                page.get_pixmap(clip=bb + (-2, -2, 2, 2), dpi=dpi).save(path)
                items.append({"type": "figure", "path": path, "w_pt": bb.width})
                continue
            if not b["lines"] or any(fb.contains(bb) for fb in fig_boxes):
                continue
            head = "".join(ch["c"] for s in b["lines"][0]["spans"] for ch in s["chars"]).strip()
            if head.startswith(SKIP_PREFIX):
                continue
            if not cluster_ok(b):
                flush()
            cluster.append(b)
        flush()
    missing = set(range(len(eq_windows))) - eq_done
    if missing:
        print("  [warn] equation windows never hit:", sorted(missing))
    return items


# ----------------------------------------------------------------------------- de-hyphenation
def build_vocab(items):
    vocab = Counter()
    for it in items:
        if it["type"] != "block":
            continue
        prev_hyph = False
        for l in it["lines"]:
            words = re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*-?", runs_text(l["runs"]))
            if prev_hyph and words:
                words = words[1:]          # line-initial fragment of a hyphenated word
            for w in words:
                if not w.endswith("-"):
                    vocab[w.lower()] += 1
            prev_hyph = runs_text(l["runs"]).rstrip().endswith("-")
    return vocab


def join_runs(dst, src, vocab):
    """Append line runs `src` to paragraph runs `dst` with hyphen/space handling."""
    if not src:
        return
    if not dst:
        dst.extend(src)
        return
    last_text, last_style = dst[-1]
    first_text = src[0][0]
    m = re.search(r"([A-Za-z]+)-$", last_text)
    if m and first_text[:1].islower():
        head = m.group(1)
        tail_m = re.match(r"[A-Za-z]+", first_text)
        tail = tail_m.group(0) if tail_m else ""
        joined, hyph = (head + tail).lower(), f"{head}-{tail}".lower()
        if vocab.get(joined):
            keep = False
        elif vocab.get(hyph) or tail.lower() in KEEP_HYPHEN_TAILS:
            keep = True
        else:
            keep = (len(head) >= 3 and len(tail) >= 3
                    and vocab.get(head.lower()) and vocab.get(tail.lower()))
        dst[-1] = (last_text if keep else last_text[:-1], last_style)
    elif not last_text.endswith((" ", "/", "\u2014")):
        dst[-1] = (last_text + " ", last_style)
    for t, st in src:
        if dst and dst[-1][1] == st:
            dst[-1] = (dst[-1][0] + t, st)
        else:
            dst.append((t, st))


# ----------------------------------------------------------------------------- blocks -> paragraphs
def classify(block):
    f, s = block["font"], block["size"]
    text = " ".join(runs_text(l["runs"]) for l in block["lines"]).strip()
    if s > 20 and len(text) > 3:
        return "title"
    if block["page"] == 1 and f == "Helvetica" and abs(s - 11) < 0.3:
        return "authors"
    if f.startswith("Helvetica-BoldOblique"):
        return "abstract"
    if f == "Helvetica" and abs(s - 10) < 0.3:
        return "h1"
    if f.startswith("Helvetica-Oblique") and re.match(r"^[A-H]\. ", text):
        if all(style[1] for l in block["lines"] for _, style in l["runs"] if _.strip()):
            return "h2"
    if f == "Helvetica" and abs(s - 8) < 0.3:
        return "caption" if text.startswith(("Fig.", "TABLE")) else "footnote"
    if f.startswith("Times") and abs(s - 8) < 0.3:
        return "small"
    return "body"


def to_paragraphs(items):
    vocab = build_vocab(items)
    out, front_notes = [], []
    in_refs, dropcap = False, ""

    def last_para_index():
        for i in range(len(out) - 1, -1, -1):
            if out[i]["type"] in ("figure", "caption"):
                continue
            return i if out[i]["type"] == "body" else None
        return None

    for it in items:
        if it["type"] != "block":
            out.append(it)
            continue
        kind = classify(it)
        lines = []
        for l in it["lines"]:
            t = runs_text(l["runs"]).strip()
            if l["size"] > 20 and len(t) == 1:
                dropcap = t                      # "E" of ELECTRICAL
            else:
                lines.append(l)
        if not lines:
            continue

        if kind in ("title", "authors", "h1", "h2", "caption", "abstract"):
            runs = []
            for l in lines:
                join_runs(runs, l["runs"], vocab)
            text = runs_text(runs).strip()
            if kind == "h1" and text == "REFERENCES":
                in_refs = True
            if kind == "title" and out and out[-1]["type"] == "title":
                join_runs(out[-1]["runs"], runs, vocab)
                continue
            out.append({"type": kind, "runs": runs})
            continue

        if kind == "footnote" and it["page"] > 1 and out and out[-1]["type"] == "caption":
            for l in lines:                      # 2nd/3rd line blocks of TABLE titles
                join_runs(out[-1]["runs"], l["runs"], vocab)
            continue
        if kind == "footnote" and it["page"] == 1:
            runs = []
            for l in lines:
                join_runs(runs, l["runs"], vocab)
            front_notes.append({"type": "footnote", "runs": runs})
            continue
        if in_refs and kind == "small":
            for l in lines:
                t = runs_text(l["runs"]).strip()
                if re.match(r"^\[\d+\]", t) or not out or out[-1]["type"] != "ref":
                    out.append({"type": "ref", "runs": list(l["runs"])})
                else:
                    join_runs(out[-1]["runs"], l["runs"], vocab)
            continue

        ptype = "body" if kind == "body" else "footnote"
        cur, prev_line, prev_is_item = None, None, False
        for l in lines:
            t = runs_text(l["runs"]).strip()
            if not t:
                continue
            is_item = bool(re.match(r"^(\d+|[a-z])\) ", t))
            if cur is None:
                indented = l["bbox"].x0 > it["col_left"] + 5
                prev_idx = last_para_index() if ptype == "body" else None
                prev_text = runs_text(out[prev_idx]["runs"]).rstrip() if prev_idx is not None else ""
                continuation = (prev_idx is not None and not is_item
                                and (not prev_text.endswith(TERMINAL) or prev_text.endswith("-"))
                                and (not indented or t[:1].islower()))
                if continuation:
                    cur = out[prev_idx]
                    join_runs(cur["runs"], l["runs"], vocab)
                else:
                    runs = list(l["runs"])
                    if dropcap:
                        runs.insert(0, (dropcap, runs[0][1]))
                        dropcap = ""
                    cur = {"type": ptype, "runs": runs}
                    out.append(cur)
            else:
                prev_t = runs_text(cur["runs"]).rstrip()
                rel_indent = l["bbox"].x0 > prev_line["bbox"].x0 + 5 and not prev_is_item
                if prev_t.endswith(TERMINAL) and (rel_indent or is_item):
                    cur = {"type": ptype, "runs": list(l["runs"])}
                    out.append(cur)
                else:
                    join_runs(cur["runs"], l["runs"], vocab)
            prev_line, prev_is_item = l, is_item

    for i, p in enumerate(out):
        if p["type"] == "authors":
            out[i + 1:i + 1] = front_notes
            break
    return out
