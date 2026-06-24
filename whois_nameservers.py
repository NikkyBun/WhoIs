#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nikkybun - whois nameserver batch lookup
=========================================
so basically, you paste a bunch of domains, all at once, doesnt matter how you
separate them, newline or space or comma, its all the same to it. then for each
domain it does a whois on port 43, following the iana referral chain, and it
grabs the nameservers out, and if the registry has no public port 43 whois
(happens alot with .gr, and a few other cctlds), it just falls back to asking
dns straight up for the NS records instead.

what comes out the other end:
  * the nameservers, listed per domain
  * and one big combined list, no duplicates, sorted ascending the smart way,
    so ns1, ns2, ns10, and even the spelled out ones like serverone, servertwo

no third party libraries, none at all, just the plain python standard library.

how to run it
-------------
gui (thats the default, you just double click it / run it with no args):
    python3 whois_nameservers.py

cli:
    python3 whois_nameservers.py domains.txt            # domains from a file
    python3 whois_nameservers.py example.com ntua.gr
    cat domains.txt | python3 whois_nameservers.py -    # read it from stdin
    stick --dns   on it, to force dns only (fastest, and honestly most reliable)
    stick --whois on it, to force whois only, with no dns fallback at all
"""

import os
import re
import sys
import time
import queue
import random
import socket
import struct
import threading

__version__ = "2.23626"

WHOIS_PORT = 43
IANA_WHOIS = "whois.iana.org"
DNS_SERVERS = ("1.1.1.1", "8.8.8.8", "9.9.9.9")

_tld_cache = {}
_tld_lock = threading.Lock()


def _resource_path(name):
    """finds a file we ship along with the app (the icon, basically), no matter
    how its being run, as a plain script, or from some other folder, or all
    frozen up by pyinstaller, we just go check every spot it could be."""
    candidates = []
    base = getattr(sys, "_MEIPASS", None)          # the pyinstaller temp unpack dir
    if base:
        candidates.append(os.path.join(base, name))
    if getattr(sys, "frozen", False):              # right next to the real binary, when its installed
        candidates.append(
            os.path.join(os.path.dirname(os.path.abspath(sys.executable)), name))
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(here, name))
    except NameError:                              # no __file__ when its frozen, so we just skip this one
        pass
    candidates.append(name)                        # last resort, just the current folder
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


# --------------------------------------------------------------------------- #
#  whois
# --------------------------------------------------------------------------- #
def _whois_raw(query, server, timeout=20):
    """sends a raw query, to <server> on port 43, and hands you back whatever
    text it answers with, decoded."""
    with socket.create_connection((server, WHOIS_PORT), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall((query + "\r\n").encode("utf-8", "replace"))
        chunks = []
        while True:
            try:
                data = s.recv(4096)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("utf-8", "replace")


def _whois_server_for(domain):
    """asks iana, which whois server, is the one in charge of this tld, and we
    keep it after, so we dont have to keep asking the same thing."""
    tld = domain.rsplit(".", 1)[-1].lower()
    with _tld_lock:
        if tld in _tld_cache:
            return _tld_cache[tld]
    server = None
    try:
        resp = _whois_raw(tld, IANA_WHOIS)
        m = re.search(r"^whois:\s*(\S+)", resp, re.I | re.M)
        if m:
            server = m.group(1).strip()
    except OSError:
        pass
    with _tld_lock:
        _tld_cache[tld] = server
    return server


def whois_lookup(domain, timeout=20, follow=True):
    """the whole whois text, for one domain. it follows the registrar referral
    aswell, but just the once, not in circles."""
    domain = domain.strip().strip(".").lower()
    server = _whois_server_for(domain)
    if not server:
        return ""
    try:
        resp = _whois_raw(domain, server, timeout=timeout)
    except OSError:
        return ""
    if follow:
        m = re.search(r"^(?:registrar whois server|referralserver):\s*(\S+)",
                      resp, re.I | re.M)
        if m:
            ref = re.sub(r"^[a-z]*whois://", "", m.group(1).strip(), flags=re.I)
            ref = ref.split("/")[0].split(":")[0].strip()
            if ref and ref.lower() != server.lower():
                try:
                    resp += "\n\n" + _whois_raw(domain, ref, timeout=timeout)
                except OSError:
                    pass
    return resp


# just checks a hostname looks legit, labels and dots, atleast one dot, and it
# has to end on a letter group
_HOST_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$", re.I)

# the field labels, that whois servers use to list the nameservers, theres like
# a hundred different formats out there honestly, so we try to catch the common
# ones
_NS_FIELD_RE = re.compile(
    r"^\s*(?:name\s*server[s]?|nserver[s]?|"
    r"domain\s*servers(?:\s*in\s*listed\s*order)?)\s*[:.]?\s*(.*)$", re.I)


def extract_nameservers(text):
    """digs the nameserver hostnames, out of the raw whois text, and it copes
    with the inline style, and the block style, both."""
    hosts, seen = [], set()

    def add(token):
        h = token.strip()
        h = h.split()[0] if h.split() else ""   # 'ns1.x 1.2.3.4', becomes just 'ns1.x'
        h = h.strip().strip(".").lower()
        if h and "." in h and _HOST_RE.match(h) and h not in seen:
            seen.add(h)
            hosts.append(h)

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _NS_FIELD_RE.match(lines[i])
        if m:
            rest = m.group(1).strip()
            if rest:                         # the inline one, like "name server: ns1.x"
                add(rest)
            else:                            # the block one, like "domain servers in listed order:"
                j = i + 1                    #    and then the ns1.x lines, come indented under it
                while j < len(lines) and lines[j].strip():
                    tok = lines[j].strip().split()[0]
                    if _HOST_RE.match(tok.strip(".")):
                        add(tok)
                        j += 1
                    else:
                        break
                i = j
                continue
        i += 1
    return hosts


# --------------------------------------------------------------------------- #
#  dns (the NS records), all hand rolled, our little fallback, no libs
# --------------------------------------------------------------------------- #
def _read_name(data, offset):
    """reads a dns name, which can be compressed with pointers and all that mess,
    gives back (the name, and where to keep reading from)."""
    labels = []
    jumped = False
    next_off = offset
    safety = 0
    while True:
        safety += 1
        if safety > 128 or offset >= len(data):
            break
        length = data[offset]
        if (length & 0xC0) == 0xC0:                  # this ones a compression pointer
            if offset + 1 >= len(data):
                break
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                next_off = offset + 2
            offset = pointer
            jumped = True
            continue
        if length == 0:
            if not jumped:
                next_off = offset + 1
            break
        labels.append(data[offset + 1: offset + 1 + length].decode("ascii", "replace"))
        offset += 1 + length
    return ".".join(labels), next_off


def _skip_name(data, offset):
    _, off = _read_name(data, offset)
    return off


def _parse_ns_response(data):
    """pulls the NS hostnames, out of a raw dns response packet."""
    if len(data) < 12:
        return []
    _, flags, qd, an, nscount, ar = struct.unpack(">HHHHHH", data[:12])
    off = 12
    for _ in range(qd):                              # just skip over the question part
        off = _skip_name(data, off) + 4
    results, seen = [], set()
    for _ in range(an + nscount + ar):
        if off >= len(data):
            break
        _, off = _read_name(data, off)
        if off + 10 > len(data):
            break
        rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[off:off + 10])
        off += 10
        if rtype == 2:                               # this one, its an NS record
            nsname, _ = _read_name(data, off)
            nsname = nsname.strip(".").lower()
            if nsname and nsname not in seen:
                seen.add(nsname)
                results.append(nsname)
        off += rdlen
    return results


def _dns_query_ns(domain, server, timeout):
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except Exception:
        ascii_domain = domain
    tid = random.randint(0, 0xFFFF)
    header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)   # RD=1, means please recurse for me
    qname = b"".join(struct.pack("B", len(p)) + p.encode("ascii", "replace")
                     for p in ascii_domain.split(".") if p) + b"\x00"
    packet = header + qname + struct.pack(">HH", 2, 1)         # qtype is NS, qclass is IN
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(packet, (server, 53))
        data, _ = s.recvfrom(8192)
    return _parse_ns_response(data)


def dns_ns_lookup(domain, timeout=5):
    domain = domain.strip().strip(".").lower()
    for server in DNS_SERVERS:
        try:
            res = _dns_query_ns(domain, server, timeout)
            if res:
                return res
        except Exception:
            continue
    return []


# --------------------------------------------------------------------------- #
#  orchestration
# --------------------------------------------------------------------------- #
# spelled out english numbers, and we go the whole way up to 999, which is, way
# way overkill, but the whole point here was to be a bit funny, so now things
# like "serverone", or even "servertwohundredfiftysix", land in the right place
_ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
          "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
          "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
# the same maps, but flipped around, number back to word, we use these down
# below for the spelling double check
_ONES_INV = {v: k for k, v in _ONES.items()}
_TEENS_INV = {v: k for k, v in _TEENS.items()}
_TENS_INV = {v: k for k, v in _TENS.items()}
_NUMWORD_VALUE = {**_ONES, **_TEENS, **_TENS, "hundred": 100}
# longest words first, so the greedy bite grabs "sixteen" in one go, instead of
# eating "six" and then choking on the "teen" thats left
_NUMWORDS_SORTED = sorted(_NUMWORD_VALUE, key=len, reverse=True)


def _spell_int(n):
    # the one proper spelling, for a number 1..999, all glued together, or None
    # when its out of that range. we lean on this, to make sure a match is, an
    # actual number and not just some word that happens to look like one
    if n <= 0 or n > 999:
        return None
    out = []
    if n >= 100:
        out.append(_ONES_INV[n // 100])
        out.append("hundred")
        n %= 100
    if n >= 20:
        out.append(_TENS_INV[(n // 10) * 10])
        n %= 10
        if n:
            out.append(_ONES_INV[n])
    elif n >= 10:
        out.append(_TEENS_INV[n])
    elif n >= 1:
        out.append(_ONES_INV[n])
    return "".join(out)


def _eval_numwords(parts):
    # adds up a list of number words, into the number they spell out, "hundred"
    # is the odd one, it multiplies whatever came before it
    current = 0
    for w in parts:
        if w == "hundred":
            current = (current or 1) * 100
        else:
            current += _NUMWORD_VALUE[w]
    return current


def _segment_numwords(text):
    # chops a glued up string, fully into number words, biggest match each time,
    # and the moment a piece isnt a number word, we just bail and give back None
    parts, i = [], 0
    while i < len(text):
        for w in _NUMWORDS_SORTED:
            if text.startswith(w, i):
                parts.append(w)
                i += len(w)
                break
        else:
            return None
    return parts


def _trailing_number(tok):
    # hunts for the longest spelled out number, stuck on the tail end of tok,
    # and gives back (the text infront of it, the value), or None if theres no
    # number there. we only trust a match, if it spells back exactly the same,
    # that way random words like "zone" dont sneak in as a one
    for i in range(len(tok)):
        suffix = tok[i:]
        parts = _segment_numwords(suffix)
        if parts is None:
            continue
        value = _eval_numwords(parts)
        if _spell_int(value) == suffix:
            return tok[:i], value
    return None


def _natkey(s):
    """the sort key, that makes ascending, actually mean ascending.

    it lines things up by the real number, for:
      * digit runs, so 'ns2' comes before 'ns10', and not after it like text
      * spelled out numbers, one all the way up to 999, either as the whole
        label ('ns1.one'), or glued onto the end of one ('...serverone' before
        '...servertwo'), the text infront groups them, the number does the order

    each little piece becomes a 3-tuple (kind, number, text), so we never end up
    comparing an int against a string, kind 0 is plain text, kind 1 is a number.
    """
    key = []
    for tok in re.findall(r"\d+|[a-z]+", s.lower()):
        if tok.isdigit():
            key.append((1, int(tok), ""))
            continue
        hit = _trailing_number(tok)
        if hit is not None:
            prefix, value = hit
            if prefix:
                key.append((0, 0, prefix))
            key.append((1, value, ""))
        else:
            key.append((0, 0, tok))
    return key


def sort_ns(items):
    uniq = dict.fromkeys(i.strip().lower() for i in items if i.strip())
    return sorted(uniq, key=_natkey)


def get_nameservers(domain, method="auto", whois_timeout=20, dns_timeout=5):
    """method is one of 'auto', or 'whois', or 'dns'. it hands back (the sorted
    ns list, and where it ended up coming from)."""
    domain = domain.strip().strip(".").lower()
    if not domain:
        return [], "empty"
    if method in ("whois", "auto"):
        ns = extract_nameservers(whois_lookup(domain, timeout=whois_timeout))
        if ns:
            return sort_ns(ns), "whois"
        if method == "whois":
            return [], "whois"
    ns = dns_ns_lookup(domain, timeout=dns_timeout)
    return sort_ns(ns)[:1], ("dns" if ns else "none")


def parse_domains(text):
    """takes a big blob of text, and fishes the clean domains out of it, even
    when theyre pasted in as whole urls, it deals with that too."""
    out, seen = [], set()
    for d in re.split(r"[\s,;]+", text.strip()):
        d = d.strip().strip(".").lower()
        d = re.sub(r"^https?://", "", d)
        d = d.split("/")[0]
        if d and "." in d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def batch_lookup(domains, method="auto", workers=5, delay=0.3,
                 whois_timeout=20, dns_timeout=5,
                 progress_cb=None, stop_flag=None):
    """runs all the lookups, across a little pool of threads. gives back a dict,
    shaped like {domain: (ns_list, src)}."""
    q = queue.Queue()
    for d in domains:
        q.put(d)
    results, lock = {}, threading.Lock()
    total = len(domains)
    counter = {"done": 0}

    def worker():
        while True:
            if stop_flag is not None and stop_flag.is_set():
                return
            try:
                d = q.get_nowait()
            except queue.Empty:
                return
            try:
                ns, src = get_nameservers(d, method, whois_timeout, dns_timeout)
            except Exception as exc:
                ns, src = [], "error: %s" % exc
            with lock:
                results[d] = (ns, src)
                counter["done"] += 1
                done = counter["done"]
            if progress_cb:
                progress_cb(done, total, d, ns, src)
            if delay > 0:
                time.sleep(delay)

    threads = [threading.Thread(target=worker, daemon=True)
               for _ in range(max(1, workers))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


# --------------------------------------------------------------------------- #
#  cli
# --------------------------------------------------------------------------- #
def run_cli(domains, method="auto"):
    if not domains:
        print("No valid domains given.")
        return
    print("NikkyBun WHOIS Nameservers v%s" % __version__)
    print("Looking up %d domain(s) via '%s'...\n" % (len(domains), method))

    def cb(done, total, d, ns, src):
        shown = ", ".join(ns) if ns else "no NS (%s)" % src
        print("[%d/%d] %-32s %s" % (done, total, d, shown))

    res = batch_lookup(domains, method, progress_cb=cb)

    allns = []
    for d, (ns, src) in res.items():
        allns.extend(ns)
    master = sort_ns(allns)

    print("\n=== Nameservers (ascending) ===")
    for n in master:
        print(n)
    print("\nTotal: %d unique nameserver(s) across %d domain(s)."
          % (len(master), len(res)))


# --------------------------------------------------------------------------- #
#  gui (tkinter)
# --------------------------------------------------------------------------- #
def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    # this makes windows, tie this process to its own taskbar icon, instead of
    # it just grabbing the boring generic python/pythonw launcher icon. on
    # everything else its a harmless no-op. has to run before the window shows
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "nikkybun.whois.nameservers")
        except Exception:
            pass

    root = tk.Tk()
    root.title("NikkyBun — WHOIS Nameserver Batch Lookup  v%s" % __version__)
    root.geometry("940x720")
    root.minsize(760, 560)

    # the window / taskbar icon, straight from the bundled png (tk 8.6 and up,
    # reads png on its own, no pillow needed)
    icon_path = _resource_path("whois_icon.png")
    if icon_path:
        try:
            _icon_img = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, _icon_img)
            root._icon_ref = _icon_img        # hang onto a reference, so it doesnt get GC'd
        except Exception:
            pass

    mono = ("Consolas", 10) if sys.platform.startswith("win") else ("Monospace", 10)

    main = ttk.Frame(root, padding=10)
    main.pack(fill="both", expand=True)

    ttk.Label(main, text="Domains (paste a batch — newline / space / comma):").pack(anchor="w")
    input_txt = tk.Text(main, height=8, font=mono, wrap="word", undo=True)
    input_txt.pack(fill="x", pady=(2, 8))
    input_txt.insert("1.0", "example.com\nntua.gr\n")

    # ----- the options row -----
    opt = ttk.Frame(main)
    opt.pack(fill="x", pady=(0, 8))

    method_var = tk.StringVar(value="auto")
    ttk.Label(opt, text="Method:").pack(side="left")
    ttk.Combobox(opt, textvariable=method_var, width=8, state="readonly",
                 values=("auto", "whois", "dns")).pack(side="left", padx=(4, 14))

    workers_var = tk.StringVar(value="5")
    ttk.Label(opt, text="Threads:").pack(side="left")
    ttk.Spinbox(opt, from_=1, to=20, textvariable=workers_var,
                width=4).pack(side="left", padx=(4, 14))

    delay_var = tk.StringVar(value="0.3")
    ttk.Label(opt, text="Delay (s):").pack(side="left")
    ttk.Spinbox(opt, from_=0, to=5, increment=0.1, textvariable=delay_var,
                width=5).pack(side="left", padx=(4, 14))

    run_btn = ttk.Button(opt, text="Lookup nameservers")
    run_btn.pack(side="left", padx=(4, 6))
    stop_btn = ttk.Button(opt, text="Stop", state="disabled")
    stop_btn.pack(side="left")

    prog = ttk.Progressbar(main, mode="determinate")
    prog.pack(fill="x", pady=(0, 6))

    # ----- the output panes -----
    panes = ttk.Panedwindow(main, orient="horizontal")
    panes.pack(fill="both", expand=True)

    left = ttk.Frame(panes)
    ttk.Label(left, text="Per domain (tick to select):").pack(anchor="w")

    # the little action toolbar, it works on whatever domains are ticked
    per_bar = ttk.Frame(left)
    per_bar.pack(fill="x", pady=(0, 4))
    selall_var = tk.BooleanVar(value=False)
    selall_chk = ttk.Checkbutton(per_bar, text="Select all", variable=selall_var)
    selall_chk.pack(side="left")
    del_btn = ttk.Button(per_bar, text="Delete selected")
    del_btn.pack(side="right")
    copysel_btn = ttk.Button(per_bar, text="Copy selected NS")
    copysel_btn.pack(side="right", padx=(0, 6))

    # a scrollable list of the per domain rows, each one is, a checkbox plus the
    # domain plus its nameservers
    per_wrap = ttk.Frame(left)
    per_wrap.pack(fill="both", expand=True)
    per_canvas = tk.Canvas(per_wrap, highlightthickness=0)
    per_vsb = ttk.Scrollbar(per_wrap, orient="vertical", command=per_canvas.yview)
    per_canvas.configure(yscrollcommand=per_vsb.set)
    per_vsb.pack(side="right", fill="y")
    per_canvas.pack(side="left", fill="both", expand=True)
    rows_frame = tk.Frame(per_canvas)
    rows_window = per_canvas.create_window((0, 0), window=rows_frame, anchor="nw")
    rows_frame.bind(
        "<Configure>",
        lambda e: per_canvas.configure(scrollregion=per_canvas.bbox("all")))
    per_canvas.bind(
        "<Configure>",
        lambda e: per_canvas.itemconfigure(rows_window, width=e.width))
    panes.add(left, weight=3)

    right = ttk.Frame(panes)
    ttk.Label(right, text="All nameservers (ascending)").pack(anchor="w")
    sorted_txt = tk.Text(right, font=mono, wrap="none", width=34, state="disabled")
    sorted_scroll = ttk.Scrollbar(right, command=sorted_txt.yview)
    sorted_txt.configure(yscrollcommand=sorted_scroll.set)
    sorted_scroll.pack(side="right", fill="y")
    sorted_txt.pack(side="left", fill="both", expand=True)
    panes.add(right, weight=2)

    # ----- the bottom bar -----
    bottom = ttk.Frame(main)
    bottom.pack(fill="x", pady=(8, 0))
    status_var = tk.StringVar(value="Ready.")
    ttk.Label(bottom, textvariable=status_var).pack(side="left")
    copy_btn = ttk.Button(bottom, text="Copy sorted list")
    copy_btn.pack(side="right", padx=(6, 0))
    save_btn = ttk.Button(bottom, text="Save results…")
    save_btn.pack(side="right")

    ev = queue.Queue()
    state = {"running": False, "stop": None, "results": {}}
    row_vars = {}        # domain -> BooleanVar, the checkbox state, it survives the re-sorts
    row_frames = {}      # domain -> the row Frame thats on screen right now

    def _set(widget, text):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        if text:
            widget.insert("end", text)
        widget.config(state="disabled")

    def _append(widget, text):
        widget.config(state="normal")
        widget.insert("end", text)
        widget.see("end")
        widget.config(state="disabled")

    # ----- the per domain rows (that checkbox list) -----
    def _wheel(event):
        num = getattr(event, "num", 0)
        if num == 4:                              # linux, wheel going up
            per_canvas.yview_scroll(-3, "units")
        elif num == 5:                            # linux, wheel going down
            per_canvas.yview_scroll(3, "units")
        else:                                     # windows and macos do it this way
            per_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _bind_wheel(widget):
        widget.bind("<MouseWheel>", _wheel)
        widget.bind("<Button-4>", _wheel)
        widget.bind("<Button-5>", _wheel)

    _bind_wheel(per_canvas)
    _bind_wheel(rows_frame)

    def _make_row(d):
        """builds (or rebuilds) the one row widget, for a single domain, out of
        whatevers in the results right now."""
        if d in row_frames:
            row_frames[d].destroy()
        ns, src = state["results"].get(d, ([], ""))
        var = row_vars.get(d)
        if var is None:
            var = tk.BooleanVar(value=False)
            row_vars[d] = var

        row = tk.Frame(rows_frame)
        row.pack(fill="x", anchor="w", pady=1)
        ttk.Checkbutton(row, variable=var).pack(side="left", anchor="n", padx=(2, 6))
        info = tk.Frame(row)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=d, font=(mono[0], mono[1], "bold"),
                 anchor="w", justify="left").pack(anchor="w", fill="x")
        body = ("\n".join("    " + n for n in ns) if ns
                else "    (no nameservers — %s)" % src)
        tk.Label(info, text=body, font=mono, anchor="w", justify="left",
                 fg="#555").pack(anchor="w", fill="x")
        row_frames[d] = row

        # clicking on the text, ticks the box, and the wheel still scrolls the list
        def _toggle(_=None, v=var):
            v.set(not v.get())
            return "break"
        for child in (row, info, *row.winfo_children(), *info.winfo_children()):
            _bind_wheel(child)
        for child in info.winfo_children():
            child.bind("<Button-1>", _toggle)

    def add_live_row(d, ns, src):
        """drops in / refreshes a domains row, the moment its lookup finishes."""
        state["results"][d] = (ns, src)
        _make_row(d)
        per_canvas.update_idletasks()
        per_canvas.yview_moveto(1.0)

    def _row_order_key(d):
        # we order the rows by the domains nameserver, the number in it, so all
        # the "serverone" domains bunch up together, then the "servertwo" ones,
        # and so on. domain name is only the tiebreak, when two are on the same
        # server. and the domains with no nameserver at all, they go last
        ns = state["results"].get(d, ([], ""))[0]
        return (0, _natkey(ns[0]), _natkey(d)) if ns else (1, [], _natkey(d))

    def rebuild_rows():
        """redraws every row, ordered by the nameserver (numerically), not by
        the domain name, so the domains line up by which server theyre on."""
        for d in list(row_frames):
            row_frames[d].destroy()
            del row_frames[d]
        for d in list(row_vars):
            if d not in state["results"]:
                del row_vars[d]
        for d in sorted(state["results"], key=_row_order_key):
            _make_row(d)
        per_canvas.update_idletasks()
        per_canvas.yview_moveto(0.0)

    def selected_domains():
        return [d for d, v in row_vars.items()
                if v.get() and d in state["results"]]

    def toggle_all():
        val = selall_var.get()
        for v in row_vars.values():
            v.set(val)

    def refresh_master():
        """rebuilds the big combined 'all nameservers' pane, from whatevers left
        in the results."""
        allns = []
        for ns, src in state["results"].values():
            allns.extend(ns)
        master = sort_ns(allns)
        _set(sorted_txt, "\n".join(master) if master else "(no nameservers found)")
        return master

    def delete_selected():
        sel = selected_domains()
        if not sel:
            status_var.set("No domains selected to delete.")
            return
        for d in sel:
            if d in row_frames:
                row_frames[d].destroy()
                del row_frames[d]
            state["results"].pop(d, None)
            row_vars.pop(d, None)
        selall_var.set(False)
        master = refresh_master()
        status_var.set("Removed %d domain(s) — %d left, %d unique nameserver(s)."
                       % (len(sel), len(state["results"]), len(master)))

    def copy_selected():
        sel = selected_domains()
        if not sel:
            status_var.set("No domains selected to copy.")
            return
        allns = []
        for d in sel:
            ns, src = state["results"].get(d, ([], ""))
            allns.extend(ns)
        master = sort_ns(allns)
        if not master:
            status_var.set("Selected domain(s) have no nameservers.")
            return
        root.clipboard_clear()
        root.clipboard_append("\n".join(master))
        status_var.set("Copied %d nameserver(s) from %d selected domain(s)."
                       % (len(master), len(sel)))

    def start():
        if state["running"]:
            return
        domains = parse_domains(input_txt.get("1.0", "end"))
        if not domains:
            messagebox.showwarning("No domains", "Paste at least one valid domain.")
            return
        try:
            workers = int(workers_var.get())
            delay = float(delay_var.get())
        except ValueError:
            messagebox.showerror("Bad value", "Threads/Delay must be numbers.")
            return
        for d in list(row_frames):
            row_frames[d].destroy()
        row_frames.clear()
        row_vars.clear()
        selall_var.set(False)
        _set(sorted_txt, "")
        prog["maximum"] = len(domains)
        prog["value"] = 0
        status_var.set("Looking up %d domain(s)…" % len(domains))
        stop = threading.Event()
        state.update(running=True, stop=stop, results={})
        run_btn.config(state="disabled")
        stop_btn.config(state="normal")

        method = method_var.get()

        def cb(done, total, d, ns, src):
            ev.put(("progress", done, total, d, ns, src))

        def controller():
            res = batch_lookup(domains, method, workers, delay,
                               progress_cb=cb, stop_flag=stop)
            ev.put(("done", res))

        threading.Thread(target=controller, daemon=True).start()
        root.after(100, poll)

    def poll():
        try:
            while True:
                item = ev.get_nowait()
                if item[0] == "progress":
                    _, done, total, d, ns, src = item
                    prog["value"] = done
                    status_var.set("[%d/%d] %s → %s"
                                   % (done, total, d,
                                      (", ".join(ns) if ns else "no NS (%s)" % src)))
                    add_live_row(d, ns, src)
                elif item[0] == "done":
                    finish(item[1])
                    return
        except queue.Empty:
            pass
        if state["running"]:
            root.after(100, poll)

    def finish(res):
        # the results, got piled up live into state["results"] (and the user
        # might of deleted some already), so we just re-sort the rows, and add
        # everything back up, from whats actually left there
        state.update(running=False)
        run_btn.config(state="normal")
        stop_btn.config(state="disabled")
        rebuild_rows()
        master = refresh_master()
        status_var.set("Done. %d domain(s), %d unique nameserver(s)."
                       % (len(state["results"]), len(master)))

    def stop_run():
        if state.get("stop"):
            state["stop"].set()
        status_var.set("Stopping…")

    def copy_sorted():
        txt = sorted_txt.get("1.0", "end").strip()
        if not txt:
            return
        root.clipboard_clear()
        root.clipboard_append(txt)
        status_var.set("Sorted nameservers copied to clipboard.")

    def save_results():
        if not state.get("results"):
            messagebox.showinfo("Nothing to save", "Run a lookup first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile="nameservers.txt")
        if not path:
            return
        res = state["results"]
        allns = []
        for d, (ns, src) in res.items():
            allns.extend(ns)
        master = sort_ns(allns)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Per domain\n")
            for d, (ns, src) in res.items():
                f.write("%s\n" % d)
                if ns:
                    for n in ns:
                        f.write("    %s\n" % n)
                else:
                    f.write("    (no nameservers — %s)\n" % src)
                f.write("\n")
            f.write("# All nameservers (ascending)\n")
            f.write("\n".join(master) + "\n")
        status_var.set("Saved to %s" % path)

    run_btn.config(command=start)
    stop_btn.config(command=stop_run)
    copy_btn.config(command=copy_sorted)
    save_btn.config(command=save_results)
    selall_chk.config(command=toggle_all)
    del_btn.config(command=delete_selected)
    copysel_btn.config(command=copy_selected)

    root.mainloop()


# --------------------------------------------------------------------------- #
#  entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    args = sys.argv[1:]
    if "--version" in args or "-V" in args:
        print("NikkyBun WHOIS Nameservers v%s" % __version__)
        sys.exit(0)
    if args:
        method = "auto"
        if "--dns" in args:
            method = "dns"
            args.remove("--dns")
        if "--whois" in args:
            method = "whois"
            args.remove("--whois")

        blob, literals = "", []
        for a in args:
            if a == "-":
                blob += sys.stdin.read() + "\n"
            elif os.path.isfile(a):
                with open(a, encoding="utf-8", errors="replace") as fh:
                    blob += fh.read() + "\n"
            else:
                literals.append(a)
        run_cli(parse_domains(blob + "\n" + " ".join(literals)), method)
    else:
        try:
            run_gui()
        except Exception as exc:
            sys.stderr.write("GUI unavailable (%s). Reading domains from STDIN…\n" % exc)
            run_cli(parse_domains(sys.stdin.read()))
