# 🌙 Dream Dairy

A small, mysterious sanctuary for recording dreams. Keep them sealed and
private, or set them free into the shared archive — where other dreamers
can gather in "the circle" (a live chat thread) to talk about what they
might mean.

## Features

- **Accounts** — simple username + passphrase sign-up and login (passwords
  are hashed, never stored in plain text).
- **Record dreams** — title, freeform description, a mood tag (Lucid,
  Nightmare, Peaceful, Surreal, Prophetic, Recurring, Fading), and a choice
  to keep it **sealed** (private, only you) or **shared** (public archive).
- **The Shared Archive** — a public feed of every dream people have chosen
  to share, filterable by mood.
- **My Dreams** — your own private journal of everything you've recorded.
- **The Circle** — a chat/comment thread on every accessible dream, so
  people can discuss it together. Updates automatically every few seconds
  (no page refresh needed) and works without any extra services — just
  Flask and SQLite.
- **Mystery-vibe design** — a drifting starfield, aurora haze, torn
  journal-page cards, and a wax-seal motif for private entries, built with
  Cormorant and EB Garamond serif type.

## Requirements

- Python 3.9+
- Flask (see `requirements.txt`)

No database server, no build step, no JavaScript framework — everything
runs from `app.py` using Python's built-in `sqlite3`.

## Setup

```bash
cd DreamDairy

# (optional but recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# run the app (creates DreamDairy.db automatically on first run)
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Project structure

```
DreamDairy/
├── app.py                  # Flask app: routes, auth, chat API, db helpers
├── requirements.txt
├── DreamDairy.db     # created automatically on first run
├── static/
│   ├── css/style.css       # the mystery-vibe theme
│   └── js/main.js          # starfield animation + chat polling
└── templates/
    ├── base.html
    ├── feed.html            # public "Shared Archive"
    ├── my_dreams.html       # private journal
    ├── new_dream.html       # record a dream form
    ├── dream_detail.html    # full dream + chat/"circle"
    ├── login.html
    └── register.html
```

## Notes on the chat

The Circle is implemented with lightweight polling (an AJAX request every
3 seconds) rather than WebSockets, so it needs no extra dependencies or
services to run — just plain Flask. It's not literally instantaneous, but
new messages typically appear within a few seconds, which is enough for a
relaxed discussion thread under each dream.

## Extending it

Some natural next steps if you want to take this further:
- Add reactions/emoji on individual dreams.
- Let users edit dreams after posting.
- Add a "dream dictionary" glossary page for common symbols.
- Swap the polling chat for Flask-SocketIO if you want true real-time push.
- Add email/password reset flows if you deploy this for real users.
