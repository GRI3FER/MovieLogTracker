from flask import Flask, jsonify, request, render_template
import sqlite3, os, requests as req
from dotenv import load_dotenv
load_dotenv()

app  = Flask(__name__)
DB   = os.path.join(os.path.dirname(__file__), "movie_log.db")
TMDB = os.environ.get("TMDB_API_KEY", "")

GENRES       = ["Action","Comedy","Drama","Horror","Romance","Sci-Fi","Thriller","Documentary","Animation","Fantasy"]
PLATFORMS    = ["Netflix","Hulu","Disney+","HBO Max","Apple TV+","Amazon Prime","YouTube","Theaters","Other"]
MEDIA_TYPES  = ["Movie","TV Show","Anime","Cartoon"]

TMDB_GENRE_MAP = {
    28:"Action", 10759:"Action", 35:"Comedy", 18:"Drama", 27:"Horror",
    10749:"Romance", 878:"Sci-Fi", 10765:"Sci-Fi", 53:"Thriller",
    80:"Thriller", 9648:"Thriller", 99:"Documentary", 16:"Animation", 14:"Fantasy",
}

def get_con():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with get_con() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                platform     TEXT,
                genre        TEXT,
                rating       INTEGER CHECK(rating BETWEEN 1 AND 5),
                date_watched TEXT,
                notes        TEXT,
                status       TEXT NOT NULL DEFAULT 'watched',
                rank         INTEGER,
                poster_path  TEXT,
                media_type   TEXT
            )""")
        cols = {r[1] for r in con.execute("PRAGMA table_info(movies)")}
        for col, defn in [("status","TEXT NOT NULL DEFAULT 'watched'"),
                          ("rank","INTEGER"), ("poster_path","TEXT"), ("media_type","TEXT")]:
            if col not in cols:
                con.execute(f"ALTER TABLE movies ADD COLUMN {col} {defn}")

# ── Options ──────────────────────────────────────────────────
@app.get("/api/options")
def options():
    return jsonify({"genres": GENRES, "platforms": PLATFORMS, "media_types": MEDIA_TYPES})

# ── TMDB lookup ───────────────────────────────────────────────
@app.get("/api/lookup")
def lookup():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    if not TMDB: return jsonify({"error": "TMDB_API_KEY not set"}), 503
    r = req.get("https://api.themoviedb.org/3/search/multi",
                params={"api_key": TMDB, "query": q, "page": 1}, timeout=5)
    r.raise_for_status()
    out = []
    for item in r.json().get("results", [])[:6]:
        media = item.get("media_type")
        if media not in ("movie", "tv"): continue
        genre_ids = item.get("genre_ids", [])
        out.append({
            "title":       item.get("title") or item.get("name", ""),
            "year":        (item.get("release_date") or item.get("first_air_date") or "")[:4],
            "genre":       next((TMDB_GENRE_MAP[g] for g in genre_ids if g in TMDB_GENRE_MAP), None),
            "media_type":  "Movie" if media == "movie" else "TV Show",
            "poster_path": item.get("poster_path"),
        })
    return jsonify(out)

# ── List ──────────────────────────────────────────────────────
@app.get("/api/movies")
def list_movies():
    status     = request.args.get("status", "watched")
    genre      = request.args.get("genre")
    media_type = request.args.get("media_type")
    min_rating = request.args.get("min_rating", type=int)
    search     = request.args.get("search")
    sort       = request.args.get("sort", "rating_desc")
    ORDER = {
        "date_watched_desc": "date_watched DESC",
        "date_watched_asc":  "date_watched ASC",
        "rating_desc":       "rating DESC, date_watched DESC",
        "rating_asc":        "rating ASC",
        "title_asc":         "title ASC",
        "genre_asc":         "COALESCE(genre,'zzz') ASC, title ASC",
        "rank_asc":          "COALESCE(rank,9999) ASC, id ASC",
    }
    clauses, params = ["status = ?"], [status]
    if genre:      clauses.append("genre = ?");      params.append(genre)
    if media_type: clauses.append("media_type = ?"); params.append(media_type)
    if min_rating: clauses.append("rating >= ?");    params.append(min_rating)
    if search:     clauses.append("title LIKE ?");   params.append(f"%{search}%")
    with get_con() as con:
        rows = con.execute(
            f"SELECT * FROM movies WHERE {' AND '.join(clauses)} ORDER BY {ORDER.get(sort,'date_watched DESC')}",
            params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/api/movies/all_unwatched_ids")
def all_unwatched_ids():
    status = request.args.get("status", "unwatched")
    with get_con() as con:
        rows = con.execute(
            "SELECT id FROM movies WHERE status=? ORDER BY COALESCE(rank,9999) ASC, id ASC", (status,)
        ).fetchall()
    return jsonify([r["id"] for r in rows])

# ── Create ────────────────────────────────────────────────────
@app.post("/api/movies")
def create_movie():
    d = request.json
    if not d.get("title"):                                       return jsonify({"error":"Title is required"}), 400
    if d.get("platform")   and d["platform"]   not in PLATFORMS:  return jsonify({"error":"Invalid platform"}), 400
    if d.get("genre")      and d["genre"]      not in GENRES:      return jsonify({"error":"Invalid genre"}), 400
    if d.get("media_type") and d["media_type"] not in MEDIA_TYPES: return jsonify({"error":"Invalid media type"}), 400
    status = d.get("status", "watched")
    if status not in ("watched","unwatched","watching"): return jsonify({"error":"Invalid status"}), 400
    with get_con() as con:
        rank = None
        if status in ("unwatched", "watching"):
            row = con.execute("SELECT MAX(rank) FROM movies WHERE status=?", (status,)).fetchone()
            rank = (row[0] or 0) + 1
        cur = con.execute(
            "INSERT INTO movies (title,platform,genre,rating,date_watched,notes,status,rank,poster_path,media_type) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (d["title"], d.get("platform"), d.get("genre"), d.get("rating"),
             d.get("date_watched"), d.get("notes"), status, rank,
             d.get("poster_path"), d.get("media_type")))
    return jsonify({"id": cur.lastrowid}), 201

# ── Read one ──────────────────────────────────────────────────
@app.get("/api/movies/<int:mid>")
def get_movie(mid):
    with get_con() as con:
        row = con.execute("SELECT * FROM movies WHERE id=?", (mid,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error":"Not found"}), 404)

# ── Update ────────────────────────────────────────────────────
@app.put("/api/movies/<int:mid>")
def update_movie(mid):
    d = request.json
    if d.get("platform")   and d["platform"]   not in PLATFORMS:  return jsonify({"error":"Invalid platform"}), 400
    if d.get("genre")      and d["genre"]      not in GENRES:      return jsonify({"error":"Invalid genre"}), 400
    if d.get("media_type") and d["media_type"] not in MEDIA_TYPES: return jsonify({"error":"Invalid media type"}), 400
    with get_con() as con:
        con.execute(
            "UPDATE movies SET title=?,platform=?,genre=?,rating=?,date_watched=?,notes=?,status=?,poster_path=?,media_type=? WHERE id=?",
            (d["title"], d.get("platform"), d.get("genre"), d.get("rating"),
             d.get("date_watched"), d.get("notes"), d.get("status","watched"),
             d.get("poster_path"), d.get("media_type"), mid))
    return jsonify({"ok": True})

# ── Delete ────────────────────────────────────────────────────
@app.delete("/api/movies/<int:mid>")
def delete_movie(mid):
    with get_con() as con:
        con.execute("DELETE FROM movies WHERE id=?", (mid,))
    return jsonify({"ok": True})

# ── Bulk reorder ──────────────────────────────────────────────
@app.put("/api/movies/reorder")
def reorder_movies():
    ids = request.json.get("ids", [])
    with get_con() as con:
        for i, mid in enumerate(ids, 1):
            con.execute("UPDATE movies SET rank=? WHERE id=?", (i, mid))
    return jsonify({"ok": True})

@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    init_db()
    print("\n  Movie Log running at http://localhost:5000\n")
    app.run(debug=True)