#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Galaxynet - WHOIS Nameserver Batch Lookup
=========================================
Paste a batch of domains (all together, any separator: newline / space / comma).
The tool does a WHOIS lookup on each domain (port 43, following the IANA referral
chain), extracts the nameservers, and falls back to a direct DNS NS query when the
registry has no public port-43 WHOIS (common for .gr and several ccTLDs).

Output:
  * Per-domain nameservers
  * One consolidated, de-duplicated list of all nameservers in ASCENDING order
    (natural sort: ns1, ns2, ns10 ...).

No third-party libraries. Pure Python standard library only.

Run modes
---------
GUI (default, just double-run it):
    python3 whois_nameservers.py

CLI:
    python3 whois_nameservers.py domains.txt            # read domains from a file
    python3 whois_nameservers.py example.com galaxynet.gr
    cat domains.txt | python3 whois_nameservers.py -    # read from STDIN
    add --dns   to force DNS-only (fastest, most reliable for nameservers)
    add --whois to force WHOIS-only (no DNS fallback)
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

WHOIS_PORT = 43
IANA_WHOIS = "whois.iana.org"
DNS_SERVERS = ("1.1.1.1", "8.8.8.8", "9.9.9.9")

_tld_cache = {}
_tld_lock = threading.Lock()


# --------------------------------------------------------------------------- #
#  WHOIS
# --------------------------------------------------------------------------- #
def _whois_raw(query, server, timeout=20):
    """Send a raw query to <server>:43 and return the decoded text response."""
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
    """Ask IANA which WHOIS server is authoritative for this TLD (cached)."""
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
    """Full WHOIS text for a domain. Follows the registrar referral once."""
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


# Hostname validator (labels, dots, at least one dot, ends in a letter group)
_HOST_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$", re.I)

# Field labels that introduce nameservers in the many WHOIS formats out there
_NS_FIELD_RE = re.compile(
    r"^\s*(?:name\s*server[s]?|nserver[s]?|"
    r"domain\s*servers(?:\s*in\s*listed\s*order)?)\s*[:.]?\s*(.*)$", re.I)


def extract_nameservers(text):
    """Pull nameserver hostnames out of raw WHOIS text (inline or block form)."""
    hosts, seen = [], set()

    def add(token):
        h = token.strip()
        h = h.split()[0] if h.split() else ""   # 'ns1.x 1.2.3.4' -> 'ns1.x'
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
            if rest:                         # inline:  "Name Server: ns1.x"
                add(rest)
            else:                            # block:   "Domain servers in listed order:"
                j = i + 1                    #              ns1.x  (indented lines follow)
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
#  DNS (NS records) - pure stdlib fallback
# --------------------------------------------------------------------------- #
def _read_name(data, offset):
    """Decode a (possibly compressed) DNS name. Returns (name, next_offset)."""
    labels = []
    jumped = False
    next_off = offset
    safety = 0
    while True:
        safety += 1
        if safety > 128 or offset >= len(data):
            break
        length = data[offset]
        if (length & 0xC0) == 0xC0:                  # compression pointer
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
    """Extract NS hostnames from a raw DNS response packet."""
    if len(data) < 12:
        return []
    _, flags, qd, an, nscount, ar = struct.unpack(">HHHHHH", data[:12])
    off = 12
    for _ in range(qd):                              # skip question section
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
        if rtype == 2:                               # NS record
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
    header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)   # RD=1
    qname = b"".join(struct.pack("B", len(p)) + p.encode("ascii", "replace")
                     for p in ascii_domain.split(".") if p) + b"\x00"
    packet = header + qname + struct.pack(">HH", 2, 1)         # QTYPE=NS, QCLASS=IN
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
#  Orchestration
# --------------------------------------------------------------------------- #
def _natkey(s):
    """Natural sort key so ns2 comes before ns10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s.lower())]


def sort_ns(items):
    uniq = dict.fromkeys(i.strip().lower() for i in items if i.strip())
    return sorted(uniq, key=_natkey)


def get_nameservers(domain, method="auto", whois_timeout=20, dns_timeout=5):
    """method: 'auto' | 'whois' | 'dns'.  Returns (sorted_ns_list, source)."""
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
    """Split a blob of text into clean domains (handles pasted URLs too)."""
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
    """Run lookups across a small thread pool. Returns {domain: (ns_list, src)}."""
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
#  CLI
# --------------------------------------------------------------------------- #
def run_cli(domains, method="auto"):
    if not domains:
        print("No valid domains given.")
        return
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
#  GUI (tkinter)
# --------------------------------------------------------------------------- #
def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Galaxynet — WHOIS Nameserver Batch Lookup")
    root.geometry("940x720")
    root.minsize(760, 560)

    mono = ("Consolas", 10) if sys.platform.startswith("win") else ("Monospace", 10)

    main = ttk.Frame(root, padding=10)
    main.pack(fill="both", expand=True)

    ttk.Label(main, text="Domains (paste a batch — newline / space / comma):").pack(anchor="w")
    input_txt = tk.Text(main, height=8, font=mono, wrap="word", undo=True)
    input_txt.pack(fill="x", pady=(2, 8))
    input_txt.insert("1.0", "example.com\ngalaxynet.gr\n")

    # ----- options row -----
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

    # ----- output panes -----
    panes = ttk.Panedwindow(main, orient="horizontal")
    panes.pack(fill="both", expand=True)

    left = ttk.Frame(panes)
    ttk.Label(left, text="Per domain").pack(anchor="w")
    per_txt = tk.Text(left, font=mono, wrap="none", state="disabled")
    per_scroll = ttk.Scrollbar(left, command=per_txt.yview)
    per_txt.configure(yscrollcommand=per_scroll.set)
    per_scroll.pack(side="right", fill="y")
    per_txt.pack(side="left", fill="both", expand=True)
    panes.add(left, weight=3)

    right = ttk.Frame(panes)
    ttk.Label(right, text="All nameservers (ascending)").pack(anchor="w")
    sorted_txt = tk.Text(right, font=mono, wrap="none", width=34, state="disabled")
    sorted_scroll = ttk.Scrollbar(right, command=sorted_txt.yview)
    sorted_txt.configure(yscrollcommand=sorted_scroll.set)
    sorted_scroll.pack(side="right", fill="y")
    sorted_txt.pack(side="left", fill="both", expand=True)
    panes.add(right, weight=2)

    # ----- bottom bar -----
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
        _set(per_txt, "")
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
                    block = d + "\n"
                    if ns:
                        for n in ns:
                            block += "    %s\n" % n
                    else:
                        block += "    (no nameservers — %s)\n" % src
                    _append(per_txt, block + "\n")
                elif item[0] == "done":
                    finish(item[1])
                    return
        except queue.Empty:
            pass
        if state["running"]:
            root.after(100, poll)

    def finish(res):
        state.update(running=False, results=res)
        run_btn.config(state="normal")
        stop_btn.config(state="disabled")
        allns = []
        for d, (ns, src) in res.items():
            allns.extend(ns)
        master = sort_ns(allns)
        _set(sorted_txt, "\n".join(master) if master else "(no nameservers found)")
        status_var.set("Done. %d domain(s), %d unique nameserver(s)."
                       % (len(res), len(master)))

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

    root.mainloop()


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    args = sys.argv[1:]
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
