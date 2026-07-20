from flask import Blueprint, render_template, request, jsonify, Response
from models import db, Setting, ActivityBook, Activity
import json, random, string

actgen_bp = Blueprint("actgen", __name__, url_prefix="/actgen")


def get_groq_key():
    s = Setting.query.filter_by(key="GROQ_API_KEY").first()
    return s.value.strip() if s else ""


def groq_json(key, system_msg, user_msg, max_tokens=800):
    from groq import Groq
    client = Groq(api_key=key)
    r = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=max_tokens,
    )
    raw = r.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── Word Search ────────────────────────────────────────────────────────────────

DIRS = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]

def make_word_search(words, size=15):
    grid = [[""] * size for _ in range(size)]
    placed = []
    for word in words:
        word = word.upper()
        ok = False
        for _ in range(200):
            dr, dc = random.choice(DIRS)
            rs = max(0, -dr*(len(word)-1)); re = min(size-1, size-1-dr*(len(word)-1))
            cs = max(0, -dc*(len(word)-1)); ce = min(size-1, size-1-dc*(len(word)-1))
            if rs > re or cs > ce:
                continue
            r, c = random.randint(rs, re), random.randint(cs, ce)
            fits = all(grid[r+dr*i][c+dc*i] in ("", word[i]) for i in range(len(word)))
            if fits:
                for i, ch in enumerate(word):
                    grid[r+dr*i][c+dc*i] = ch
                placed.append(word)
                ok = True
                break
    # fill blanks
    for r in range(size):
        for c in range(size):
            if not grid[r][c]:
                grid[r][c] = random.choice(string.ascii_uppercase)
    return grid, placed


# ── Sudoku ─────────────────────────────────────────────────────────────────────

def _valid(board, row, col, num):
    if num in board[row]:
        return False
    if any(board[r][col] == num for r in range(9)):
        return False
    br, bc = (row//3)*3, (col//3)*3
    return all(board[br+dr][bc+dc] != num for dr in range(3) for dc in range(3))


def _solve(board):
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0:
                nums = list(range(1, 10))
                random.shuffle(nums)
                for n in nums:
                    if _valid(board, r, c, n):
                        board[r][c] = n
                        if _solve(board):
                            return True
                        board[r][c] = 0
                return False
    return True


def generate_sudoku(difficulty):
    board = [[0]*9 for _ in range(9)]
    _solve(board)
    solution = [row[:] for row in board]
    givens = {"Easy": 40, "Medium": 32, "Hard": 26}.get(difficulty, 35)
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)
    puzzle = [row[:] for row in board]
    for r, c in cells[givens:]:
        puzzle[r][c] = 0
    return puzzle, solution


# ── Crossword ──────────────────────────────────────────────────────────────────

def make_crossword(pairs, size=15):
    grid = [[" "]*size for _ in range(size)]
    placed = []
    num = 1

    def can_place_h(word, r, c):
        if c + len(word) > size:
            return False
        for i, ch in enumerate(word):
            if grid[r][c+i] not in (" ", ch):
                return False
            if grid[r][c+i] == " ":
                if r > 0 and grid[r-1][c+i] != " ":
                    return False
                if r < size-1 and grid[r+1][c+i] != " ":
                    return False
        if c > 0 and grid[r][c-1] != " ":
            return False
        if c+len(word) < size and grid[r][c+len(word)] != " ":
            return False
        return True

    def can_place_v(word, r, c):
        if r + len(word) > size:
            return False
        for i, ch in enumerate(word):
            if grid[r+i][c] not in (" ", ch):
                return False
            if grid[r+i][c] == " ":
                if c > 0 and grid[r+i][c-1] != " ":
                    return False
                if c < size-1 and grid[r+i][c+1] != " ":
                    return False
        if r > 0 and grid[r-1][c] != " ":
            return False
        if r+len(word) < size and grid[r+len(word)][c] != " ":
            return False
        return True

    if not pairs:
        return [["#"]*size for _ in range(size)], [], []

    # Place first word horizontally at centre
    w0 = pairs[0]["answer"].upper()
    r0, c0 = size//2, (size-len(w0))//2
    for i, ch in enumerate(w0):
        grid[r0][c0+i] = ch
    placed.append({"word": w0, "clue": pairs[0]["clue"], "row": r0, "col": c0, "dir": "across", "num": num})
    num += 1

    for pair in pairs[1:]:
        word = pair["answer"].upper()
        placed_flag = False

        for existing in placed:
            ew = existing["word"]
            if existing["dir"] == "across":
                for ji, jch in enumerate(ew):
                    for ii, ich in enumerate(word):
                        if ich == jch:
                            nr = existing["row"] - ii
                            nc = existing["col"] + ji
                            if 0 <= nr and nr+len(word) <= size and 0 <= nc < size:
                                if can_place_v(word, nr, nc):
                                    for i, ch in enumerate(word):
                                        grid[nr+i][nc] = ch
                                    placed.append({"word": word, "clue": pair["clue"], "row": nr, "col": nc, "dir": "down", "num": num})
                                    num += 1
                                    placed_flag = True
                                    break
                        if placed_flag:
                            break
                    if placed_flag:
                        break
            else:  # down
                for ji, jch in enumerate(ew):
                    for ii, ich in enumerate(word):
                        if ich == jch:
                            nr = existing["row"] + ji
                            nc = existing["col"] - ii
                            if 0 <= nr < size and 0 <= nc and nc+len(word) <= size:
                                if can_place_h(word, nr, nc):
                                    for i, ch in enumerate(word):
                                        grid[nr][nc+i] = ch
                                    placed.append({"word": word, "clue": pair["clue"], "row": nr, "col": nc, "dir": "across", "num": num})
                                    num += 1
                                    placed_flag = True
                                    break
                        if placed_flag:
                            break
                    if placed_flag:
                        break
            if placed_flag:
                break

        if not placed_flag:
            # fallback: place horizontally in a spare row
            for attempt in range(30):
                r = random.randint(1, size-2)
                c = random.randint(1, size-len(word)-1)
                if can_place_h(word, r, c):
                    for i, ch in enumerate(word):
                        grid[r][c+i] = ch
                    placed.append({"word": word, "clue": pair["clue"], "row": r, "col": c, "dir": "across", "num": num})
                    num += 1
                    break

    final = [["#" if cell == " " else cell for cell in row] for row in grid]
    across = sorted([p for p in placed if p["dir"] == "across"], key=lambda x: x["num"])
    down   = sorted([p for p in placed if p["dir"] == "down"],   key=lambda x: x["num"])
    return final, across, down


# ── Download HTML builder ──────────────────────────────────────────────────────

def build_html(book, activities):
    ws = activities.get("wordsearch", {})
    su = activities.get("sudoku", {})
    cw = activities.get("crossword", {})
    tr = activities.get("trivia", {})

    ws_grid_html = ""
    if ws.get("grid"):
        rows = "".join(
            "<tr>" + "".join(f"<td>{ch}</td>" for ch in row) + "</tr>"
            for row in ws["grid"]
        )
        ws_grid_html = f'<table style="border-collapse:collapse;font-family:monospace;font-size:13px;">{rows}</table>'
    ws_words_html = " &nbsp;|&nbsp; ".join(ws.get("words", []))

    su_html = ""
    if su.get("puzzle"):
        rows = ""
        for ri, row in enumerate(su["puzzle"]):
            cells = ""
            for ci, val in enumerate(row):
                br = "border-right:2px solid #555;" if ci in (2, 5) else ""
                bb = "border-bottom:2px solid #555;" if ri in (2, 5) else ""
                cells += f'<td style="width:28px;height:28px;text-align:center;border:1px solid #bbb;font-weight:bold;{br}{bb}">{val if val else ""}</td>'
            rows += f"<tr>{cells}</tr>"
        su_html = f'<table style="border-collapse:collapse;">{rows}</table>'

    cw_html = ""
    if cw.get("grid"):
        rows = "".join(
            "<tr>" + "".join(
                '<td style="width:22px;height:22px;background:#000;"></td>' if ch == "#"
                else f'<td style="width:22px;height:22px;text-align:center;border:1px solid #999;font-size:11px;font-weight:bold;">{ch}</td>'
                for ch in row
            ) + "</tr>"
            for row in cw["grid"]
        )
        cw_html = f'<table style="border-collapse:collapse;">{rows}</table>'
    across_html = "".join(f'<li><b>{c["num"]}.</b> {c["clue"]}</li>' for c in cw.get("across", []))
    down_html   = "".join(f'<li><b>{c["num"]}.</b> {c["clue"]}</li>' for c in cw.get("down", []))

    trivia_html = ""
    for i, q in enumerate(tr.get("questions", []), 1):
        opts = "".join(
            f'<div style="padding:5px 8px;border:1px solid #ddd;border-radius:4px;margin:3px 0;">{chr(64+j)}. {o}</div>'
            for j, o in enumerate(q.get("options", []), 1)
        )
        trivia_html += f'<div style="margin-bottom:20px;"><p><b>{i}. {q.get("q","")}</b></p>{opts}</div>'

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>{book.theme} Activity Book</title>
<style>
body{{font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:24px;}}
h1{{text-align:center;}} h2{{border-bottom:2px solid #333;padding-bottom:6px;margin-top:36px;}}
.pb{{page-break-after:always;}} @media print{{.pb{{page-break-after:always;}}}}
td{{font-size:13px;}}
</style></head><body>
<h1>{book.theme} Activity Book</h1>
<p style="text-align:center;color:#666;">{book.difficulty} · {book.age_group}</p>

<div class="pb">
<h2>Word Search</h2>
<p>Find the words: <b>{ws_words_html}</b></p>
{ws_grid_html}
</div>

<div class="pb">
<h2>Sudoku</h2>
<p>Fill every row, column and 3×3 box with digits 1–9.</p>
{su_html}
</div>

<div class="pb">
<h2>Crossword</h2>
{cw_html}
<div style="display:flex;gap:40px;margin-top:16px;">
  <div><h3>Across</h3><ul style="list-style:none;padding:0;">{across_html}</ul></div>
  <div><h3>Down</h3><ul style="list-style:none;padding:0;">{down_html}</ul></div>
</div>
</div>

<div><h2>Trivia Quiz</h2>{trivia_html}</div>
</body></html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@actgen_bp.route("/")
def index():
    books = ActivityBook.query.order_by(ActivityBook.created_at.desc()).limit(20).all()
    return render_template("actgen/index.html", books=books)


@actgen_bp.route("/generate", methods=["POST"])
def generate():
    data   = request.get_json()
    theme  = data.get("theme", "").strip()
    diff   = data.get("difficulty", "Medium")
    age    = data.get("age_group", "Kids 9-12")

    if not theme:
        return jsonify({"error": "Theme is required."}), 400

    key = get_groq_key()
    if not key:
        return jsonify({"error": "Groq API key not configured. Ask your admin."}), 400

    try:
        sys_j = "You return only valid JSON, no other text."

        # 1. Word search
        ws_resp = groq_json(key, sys_j,
            f"Give 8 {diff}-level words related to '{theme}' for {age}. "
            "Words: uppercase, 3-10 letters, no spaces, no hyphens. "
            'Return ONLY JSON: {"words":["WORD1","WORD2","WORD3","WORD4","WORD5","WORD6","WORD7","WORD8"]}',
            max_tokens=150)
        ws_words = [w.upper().replace(" ","")[:10] for w in ws_resp.get("words",[]) if w][:8]
        ws_grid, ws_placed = make_word_search(ws_words)

        # 2. Sudoku (algorithmic)
        puzzle, solution = generate_sudoku(diff)

        # 3. Crossword
        cw_resp = groq_json(key, sys_j,
            f"Give 7 crossword word-clue pairs for theme '{theme}', {diff} difficulty, {age}. "
            "Answers: uppercase, 3-9 letters, no spaces. "
            'Return ONLY JSON: {"pairs":[{"answer":"WORD","clue":"Short clue"}]}',
            max_tokens=500)
        cw_pairs = cw_resp.get("pairs", [])[:7]
        cw_grid, cw_across, cw_down = make_crossword(cw_pairs)

        # 4. Trivia
        tr_resp = groq_json(key, sys_j,
            f"Create 6 trivia questions about '{theme}' for {age}, {diff} level. "
            'Return ONLY JSON: {"questions":[{"q":"?","options":["A","B","C","D"],"answer":0}]}',
            max_tokens=900)
        trivia_qs = tr_resp.get("questions", [])[:6]

        book = ActivityBook(theme=theme, difficulty=diff, age_group=age)
        db.session.add(book)
        db.session.flush()

        for atype, atitle, adata in [
            ("wordsearch", "Word Search",     {"grid": ws_grid, "words": ws_placed}),
            ("sudoku",     "Sudoku Puzzle",   {"puzzle": puzzle, "solution": solution}),
            ("crossword",  "Crossword",       {"grid": cw_grid, "across": cw_across, "down": cw_down}),
            ("trivia",     "Trivia Quiz",     {"questions": trivia_qs}),
        ]:
            db.session.add(Activity(book_id=book.id, activity_type=atype,
                                    title=atitle, data=json.dumps(adata)))

        db.session.commit()
        return jsonify({"success": True, "id": book.id})

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned an invalid response. Please try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@actgen_bp.route("/<int:book_id>")
def view(book_id):
    book = ActivityBook.query.get_or_404(book_id)
    activities = {a.activity_type: json.loads(a.data) for a in book.activities}
    return render_template("actgen/view.html", book=book, activities=activities)


@actgen_bp.route("/<int:book_id>/download")
def download(book_id):
    book = ActivityBook.query.get_or_404(book_id)
    activities = {a.activity_type: json.loads(a.data) for a in book.activities}
    html = build_html(book, activities)
    fname = f"ActivityBook_{book.theme.replace(' ','_')}_{book.id}.html"
    return Response(html, mimetype="text/html",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@actgen_bp.route("/<int:book_id>/delete", methods=["POST"])
def delete(book_id):
    book = ActivityBook.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    return jsonify({"success": True})
