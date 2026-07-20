# AI Tools Suite

## Overview

Three AI-powered mobile-style web apps built with Flask, SQLite, and Groq AI. Each runs as an independent Blueprint. The UI mimics a native smartphone app (430 px phone shell, dark theme, per-app accent colours).

## User Preferences

Preferred communication style: Simple, everyday language.

## Routes

| Route | Tool | Accent |
|-------|------|--------|
| `/` | Home — app launcher | Purple `#7c3aed` |
| `/coursegen` | Course Generator | Indigo `#6366f1` |
| `/emailnewsgen` | Email Newsletter Generator | Emerald `#10b981` |
| `/actgen` | Activity Book Generator | Amber `#f59e0b` |
| `/admin` | Admin Panel | Red `#e11d48` |

## Architecture

- **Framework**: Flask + Blueprint-based modular structure
- **Database**: SQLite via Flask-SQLAlchemy (`data.db`)
- **AI**: Groq API (`llama-3.1-8b-instant`) — key stored in `settings` table
- **UI**: Custom mobile-first CSS — 430 px phone shell, status bar, dark theme, per-app `--accent` CSS variable
- **Downloads**: Server-side only (no Blob/createObjectURL)
- **Notifications**: Inline `showMsg()` (no floating toasts); errors never auto-dismiss

## App Structure

```
apps/
  coursegen/    Course Generator blueprint
  emailnewsgen/ Newsletter Generator blueprint
  actgen/       Activity Book Generator blueprint
templates/
  base.html     Shared phone-shell layout
  index.html    Home screen (app grid)
  coursegen/    index.html + view.html
  emailnewsgen/ index.html
  actgen/       index.html + view.html
static/css/
  mobile.css    Full design system (cards, buttons, forms, grids, quiz, etc.)
models.py       All SQLAlchemy models
app.py          App factory + from_json template filter
main.py         Dev entry point (python main.py)
wsgi.py         PythonAnywhere WSGI entry
requirements.txt
```

## Key Implementation Notes

- **Groq key**: Stored in `Setting(key="GROQ_API_KEY")` — set via the Admin Panel at `/admin/` (Settings & API Keys tab).
- **Course Generator**: Groq returns structured JSON → saved as Course → CourseModule → CourseQuiz + CourseAssignment rows. Quiz is interactive (select → check → score bar).
- **Newsletter Generator**: Groq returns `{subject, content_html}` → iframe srcdoc preview → server-side HTML download.
- **Activity Book**: 4 activities generated per book:
  - Word search — Groq picks themed words, grid built algorithmically (8-direction placement)
  - Sudoku — fully algorithmic backtracking generator, no AI
  - Crossword — Groq gives word-clue pairs, layout placed with intersection algorithm
  - Trivia quiz — Groq generates Q&A with 4 options
- **Running workflow**: `flask_website` (`python main.py`) on port 5000. The `Start application` (gunicorn) workflow is unused.
