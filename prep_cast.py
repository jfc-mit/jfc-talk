#!/usr/bin/env python3
"""Cut a multi-day asciinema recording down to talk length.

Reads a v2 .cast (e.g. ../rbrun3.cast — a ~54 h wall JFC run, 280x69 tmux,
of which the analysis proper ends at ~42.9 h), and writes:

  assets/workflow.cast   retimed + bucket-merged talk cut (payload preserved)
  assets/cast_meta.js    window.CAST_META = { orig_dur, new_dur, events,
                          anchors: [[newT, origT], ...],       # run-clock map
                          rests:   [[newT, holdSec], ...] }    # story beats

Pacing
------
Uniform time-compression turns a 43 h recording into a 1,700x strobe. Instead,
if a screen-change analysis cache exists (see --analyze), the cut is
REST-POINT PACED: moments where the screen actually holds still for
>= REST_GAP s of original time become explicit holds of HOLD_MIN..HOLD_MAX s
(these are almost always "an agent finished something and paused" — the story
beats), and the motion in between is compressed uniformly to fill the rest of
the TARGET budget. Without the cache it falls back to density pacing (gaps
capped at GAP_CAP, uniformly scaled).

The analysis (python3 prep_cast.py --analyze, needs pyte; run via
`uv run --with pyte python3 prep_cast.py --analyze`) replays the cast through
a terminal emulator and logs every event that substantively changes the screen
— i.e. changes >= MIN_ROWS rows, which filters the tmux/Claude-Code clock,
token-counter and spinner repaints that repaint 1-2 rows every ~0.3 s and
would otherwise make byte counts lie. Cached to cast_analysis.json (slow pass,
run once per recording).

--fast-analyze is a stdlib micro-emulator (strips SGR/OSC, tracks only cursor
motion + row writes, approximate scrolling): ~50x faster than pyte and accurate
enough for rest detection; the pyte pass remains the ground truth.

Usage:
  uv run --with pyte python3 prep_cast.py --analyze [input.cast]
  python3 prep_cast.py --fast-analyze [input.cast]
  python3 prep_cast.py [input.cast] [target_seconds] [end_orig_seconds]
"""
import json, sys, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
ANALYZE = '--analyze' in sys.argv[1:]
FAST = '--fast-analyze' in sys.argv[1:]

SRC = ARGS[0] if len(ARGS) > 0 else os.path.join(HERE, '..', 'rbrun3.cast')
TARGET = float(ARGS[1]) if len(ARGS) > 1 else 800.0    # seconds of playback
END = float(ARGS[2]) if len(ARGS) > 2 else 154600.0    # original seconds to keep
                                                       # (analysis completes ~42.88 h)
GAP_CAP = 0.35    # s: cap on original inter-event gaps (density pacing)
BUCKET = 0.03     # s: merge output events within this window of new time
ANCHOR_EVERY = 2.0
REST_GAP = 60     # s of original time with no substantive change => rest point
                  # (>=60 s of >=MIN_ROWS-row stillness gives the same 43 story
                  #  beats the in-recording pyte analysis found at its 1.2 s
                  #  full-diff threshold — streaming keeps 1-2-row changes alive)
MIN_ROWS = 3      # rows that must change for an event to count as substantive
HOLD_MIN, HOLD_MAX = 2.0, 5.0
# Story beats the narration leans on (original run seconds): the D2 truth-flavour
# decision (T+01:12), the phase-5 arbiter/adversarial-verification exchange
# (T+39:41) and the honest bottom line (T+42:53). The rest interval containing
# (or nearest within KEY_NEAR s of) each beat is held KEY_HOLD s so the audience
# can actually read the screen the speaker is quoting.
KEY_BEATS = [4320.0, 142860.0, 154380.0]
KEY_HOLD, KEY_NEAR = 7.0, 300.0

OUT = os.path.join(HERE, 'assets', 'workflow.cast')
META = os.path.join(HERE, 'assets', 'cast_meta.js')
CACHE = os.path.join(HERE, 'cast_analysis.json')

# Transient wide-terminal windows: the tmux session was occasionally reattached
# at ~280 cols (incl. the very start), which makes the fit-to-width dock shrink
# to unreadable and then snap back. Drop those windows from the cut entirely —
# events AND the resize pair — so the dock geometry never jumps. A final wide
# stretch with no return before END is kept: that's the end-of-run screen the
# finale shows full-stage.
WIDE_COLS = 100

def wide_windows(path, end):
    wins, open_t = [], None
    with open(path) as f:
        hdr = json.loads(f.readline())
        if hdr.get('width', 80) > WIDE_COLS:
            open_t = 0.0
        for line in f:
            try:
                t, typ, d = json.loads(line)
            except Exception:
                continue
            if t > end:
                break
            if typ != 'r':
                continue
            try:
                w = int(d.split('x')[0])
            except Exception:
                continue
            if w > WIDE_COLS and open_t is None:
                open_t = t
            elif w <= WIDE_COLS and open_t is not None:
                wins.append((open_t, t))     # incl. the closing resize event
                open_t = None
    return wins

WINS = wide_windows(SRC, END)
in_win = lambda t: any(a <= t <= b for a, b in WINS)

def post_window_dims():
    """Terminal dims right after the leading wide window closes — the cut's true
    geometry. The header must declare these: the player sizes its font from the
    header, and a stale 280-col header renders everything at ~1/3 scale."""
    if not (WINS and WINS[0][0] == 0.0):
        return None
    b = WINS[0][1]
    dims = None
    with open(SRC) as f:
        f.readline()
        for line in f:
            try:
                t, typ, d = json.loads(line)
            except Exception:
                continue
            if t > b:
                break
            if typ == 'r':
                try:
                    w, h = map(int, d.split('x'))
                    if w <= WIDE_COLS:
                        dims = (w, h)
                except Exception:
                    pass
    return dims


def events(path, end=None):
    with open(path) as f:
        f.readline()
        for line in f:
            try:
                t, typ, data = json.loads(line)
            except Exception:
                continue
            if end is not None and t > end:
                break
            yield t, typ, data


# ------------------------------------------------------- fast analysis pass
if FAST:
    OSC = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\\\)?')
    SGR = re.compile(r'\x1b\[[0-9;:]*m')
    CSI = re.compile(r'\x1b\[([0-9;?]*)([A-Za-z@])')
    ESC1 = re.compile(r'\x1b[=>@-Z\\^_]')   # bare ESC sequences (RIS, DECSC...)
    rows_n, cols_n = 69, 280
    rows = [''] * rows_n
    cy = cx = 0
    chg, n = [], 0

    def putline(y, x, txt, touched, old):
        if y < 0 or y >= rows_n or not txt:
            return
        if y not in old:
            old[y] = rows[y]
        r = rows[y]
        if len(r) < x:
            r = r + ' ' * (x - len(r))
        rows[y] = r[:x] + txt + r[x + len(txt):]
        touched.add(y)

    for t, typ, data in events(SRC):
        n += 1
        if typ == 'r':
            try:
                w, h = map(int, data.split('x'))
                cols_n, rows_n = w, h
            except Exception:
                pass
            rows = [''] * rows_n
            cy = cx = 0
            chg.append(round(t, 2))
            continue
        if typ != 'o':
            continue
        data = OSC.sub('', data)
        data = SGR.sub('', data)
        data = ESC1.sub('', data)
        touched, old = set(), {}
        pos = 0
        for m in CSI.finditer(data):
            # literal text between control sequences
            for piece in re.split(r'([\r\n\x08])', data[pos:m.start()]):
                if piece == '\r':
                    cx = 0
                elif piece == '\n':
                    cy += 1
                    if cy >= rows_n:            # approximate scroll
                        rows.pop(0)
                        rows.append('')
                        old.clear()
                        touched.clear()
                        cy = rows_n - 1
                elif piece == '\x08':
                    cx = max(0, cx - 1)
                elif piece:
                    piece = piece.replace('\x0f', '').replace('\x0e', '')
                    putline(cy, cx, piece, touched, old)
                    cx += len(piece)
            pos = m.end()
            p, c = m.group(1), m.group(2)
            args = [int(a) if a.isdigit() else 0 for a in p.split(';')] if p and not p.startswith('?') else []
            if c in 'Hf':
                cy = (args[0] - 1) if args else 0
                cx = (args[1] - 1) if len(args) > 1 else 0
            elif c == 'A': cy = max(0, cy - (args[0] if args else 1))
            elif c == 'B': cy = min(rows_n - 1, cy + (args[0] if args else 1))
            elif c == 'C': cx += (args[0] if args else 1)
            elif c == 'D': cx = max(0, cx - (args[0] if args else 1))
            elif c == 'G': cx = (args[0] - 1) if args else 0
            elif c == 'd': cy = (args[0] - 1) if args else 0
            elif c == 'K':
                if cy not in old:
                    old[cy] = rows[cy] if cy < rows_n else ''
                if 0 <= cy < rows_n:
                    mode = args[0] if args else 0
                    rows[cy] = ('' if mode == 2 else ' ' * cx + '' if mode == 1 else rows[cy][:cx])
                    touched.add(cy)
            elif c == 'J':
                rows = [''] * rows_n
                old.clear(); touched.clear()
        # trailing text after the last control sequence
        for piece in re.split(r'([\r\n\x08])', data[pos:]):
            if piece == '\r': cx = 0
            elif piece == '\n':
                cy += 1
                if cy >= rows_n:
                    rows.pop(0); rows.append(''); old.clear(); touched.clear(); cy = rows_n - 1
            elif piece == '\x08': cx = max(0, cx - 1)
            elif piece:
                piece = piece.replace('\x0f', '').replace('\x0e', '')
                putline(cy, cx, piece, touched, old)
                cx += len(piece)
        changed = sum(1 for y in touched if y in old and rows[y] != old[y])
        if changed >= MIN_ROWS:
            chg.append(round(t, 2))
        if n % 50000 == 0:
            print(f"  … {n} events, {t/3600:.1f} h, {len(chg)} substantive changes", flush=True)
    json.dump({'min_rows': MIN_ROWS, 'method': 'fast', 'changes': chg}, open(CACHE, 'w'))
    print(f"wrote {CACHE}: {len(chg)} substantive changes over {n} events (fast mode)")
    sys.exit(0)

# ---------------------------------------------------------------- analysis pass
if ANALYZE:
    import pyte
    screen = pyte.Screen(280, 69)
    stream = pyte.Stream(screen)
    prev, chg, n = {}, [], 0
    for t, typ, data in events(SRC):          # full file: cache is END-agnostic
        n += 1
        if typ == 'r':
            try:
                w, h = map(int, data.split('x'))
                screen.resize(lines=h, columns=w)
            except Exception:
                pass
            prev.clear()
            screen.dirty.clear()
            chg.append(round(t, 2))
            continue
        if typ != 'o':
            continue
        try:
            stream.feed(data)
        except Exception:
            continue
        changed = 0
        for y in screen.dirty:
            try:
                row = screen.display[y]
            except IndexError:
                continue
            if prev.get(y) != row:
                prev[y] = row
                changed += 1
        screen.dirty.clear()
        if changed >= MIN_ROWS:
            chg.append(round(t, 2))
        if n % 20000 == 0:
            print(f"  … {n} events, {t/3600:.1f} h, {len(chg)} substantive changes", flush=True)
    json.dump({'min_rows': MIN_ROWS, 'changes': chg}, open(CACHE, 'w'))
    print(f"wrote {CACHE}: {len(chg)} substantive changes over {n} events")
    sys.exit(0)

# ---------------------------------------------------------------- rest points
rests = []                                   # [(t_start, t_end, hold_s), ...]
if os.path.exists(CACHE):
    chg = [c for c in json.load(open(CACHE))['changes'] if c <= END]
    for a, b in zip(chg, chg[1:] + [END]):
        if b - a >= REST_GAP:
            hold = min(HOLD_MAX, max(HOLD_MIN, 0.8 + (b - a) / 1200))
            rests.append((a, b, hold))
    for kb in KEY_BEATS:                     # boost the narrated story beats
        best, dist = -1, KEY_NEAR
        for i, (a, b, _) in enumerate(rests):
            d = 0.0 if a <= kb <= b else min(abs(kb - a), abs(kb - b))
            if d < dist:
                best, dist = i, d
        if best >= 0:
            a, b, h = rests[best]
            rests[best] = (a, b, max(h, KEY_HOLD))
    print(f"{len(rests)} rest points (screen still >= {REST_GAP}s), "
          f"total hold {sum(r[2] for r in rests):.0f}s "
          f"({sum(1 for r in rests if r[2] >= KEY_HOLD)} key beats boosted)")
else:
    print("no cast_analysis.json — uniform density pacing (run --analyze for rest-point pacing)")

def rest_at(t, _idx=[0]):
    """index of the rest interval containing t, else -1 (monotonic queries)."""
    i = _idx[0]
    while i < len(rests) and t >= rests[i][1]:
        i += 1
    _idx[0] = i
    return i if i < len(rests) and t > rests[i][0] else -1

# ------------------------------------------------------- pass 1: time budgets
print(f"{len(WINS)} transient wide-terminal windows dropped "
      f"({sum(b-a for a, b in WINS)/60:.1f} min of original time)")
motion, in_rest = 0.0, [0.0] * len(rests)
prev_t, orig_end, n = 0.0, 0.0, 0
for t, typ, data in events(SRC, END):
    if in_win(t):
        prev_t = t
        continue
    g = min(t - prev_t, GAP_CAP)
    r = rest_at(t)
    if r >= 0:
        in_rest[r] += g
    else:
        motion += g
    prev_t = t
    orig_end = t
    n += 1
holds = sum(r[2] for i, r in enumerate(rests) if in_rest[i] > 0)
scale_m = (TARGET - holds) / motion
print(f"events {n} · original {orig_end/3600:.1f} h · motion {motion/3600:.1f} h "
      f"(x{1/scale_m:.0f}) + {holds:.0f}s of holds")

# --------------------------------------------------- pass 2: retime and write
with open(SRC) as f:
    header = json.loads(f.readline())
header['title'] = 'JFC · autonomous ALEPH R_b analysis — talk cut'
header.pop('idle_time_limit', None)
dims = post_window_dims()
if dims:
    header['width'], header['height'] = dims
    print(f"header geometry: {dims[0]}x{dims[1]} (post-window)")

anchors, rest_marks = [[0.0, 0.0]], []
written = 0
rest_at.__defaults__[0][0] = 0               # reset the monotonic cursor
with open(OUT, 'w') as out:
    out.write(json.dumps(header) + '\n')
    prev_t, cur, next_anchor = 0.0, 0.0, ANCHOR_EVERY
    cur_rest = -1
    buf_t, buf_data = None, []

    def flush():
        global buf_t, buf_data, written
        if buf_t is not None:
            out.write(json.dumps([round(buf_t, 4), 'o', ''.join(buf_data)],
                                 ensure_ascii=False) + '\n')
            written += 1
            buf_t, buf_data = None, []

    for t, typ, data in events(SRC, END):
        if in_win(t):
            prev_t = t
            continue
        g = min(t - prev_t, GAP_CAP)
        r = rest_at(t)
        if r >= 0 and in_rest[r] > 0:
            if r != cur_rest:
                rest_marks.append([round(cur, 2), rests[r][2]])
            cur += g * (rests[r][2] / in_rest[r])
        else:
            cur += g * scale_m
        cur_rest = r
        prev_t = t
        if cur >= next_anchor:
            anchors.append([round(cur, 2), round(t, 1)])
            next_anchor = cur + ANCHOR_EVERY
        if typ == 'o':
            if buf_t is not None and cur - buf_t <= BUCKET:
                buf_data.append(data)
            else:
                flush()
                buf_t, buf_data = cur, [data]
        else:
            flush()
            out.write(json.dumps([round(cur, 4), typ, data], ensure_ascii=False) + '\n')
            written += 1
    flush()
anchors.append([round(cur, 2), round(orig_end, 1)])

with open(META, 'w') as m:
    m.write('window.CAST_META = ' + json.dumps({
        'orig_dur': round(orig_end, 1), 'new_dur': round(cur, 2),
        'events': written, 'anchors': anchors, 'rests': rest_marks}) + ';\n')
print(f"wrote {OUT}: {written} events, {cur:.0f} s playback ({os.path.getsize(OUT)/1e6:.1f} MB)")
print(f"wrote {META}: {len(anchors)} anchors, {len(rest_marks)} rest marks")
