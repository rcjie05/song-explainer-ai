import streamlit as st
import requests
from groq import Groq
from st_copy_to_clipboard import st_copy_to_clipboard
import sqlite3
import hashlib
from datetime import datetime

# ====================== DATABASE SETUP ======================
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 username TEXT PRIMARY KEY,
                 password_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT,
                 song_title TEXT,
                 artist TEXT,
                 explanation TEXT,
                 timestamp TEXT,
                 FOREIGN KEY(username) REFERENCES users(username))''')
    conn.commit()
    conn.close()

init_db()  # Create DB and tables if not exist

# ====================== AUTH FUNCTIONS ======================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register():
    st.title("Register")
    new_user = st.text_input("Choose Username")
    new_pass = st.text_input("Choose Password", type="password")
    if st.button("Register"):
        if new_user and new_pass:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                          (new_user, hash_password(new_pass)))
                conn.commit()
                st.success("Registered successfully! Go to Login.")
            except sqlite3.IntegrityError:
                st.error("Username already exists.")
            conn.close()
        else:
            st.warning("Please fill both fields.")

def login():
    st.title("Login to Song Explainer AI")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        conn.close()
        if result and result[0] == hash_password(password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Invalid username or password")

def logout():
    if st.button("Logout"):
        for key in ['logged_in', 'username']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def save_history(username, title, artist, explanation):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO history (username, song_title, artist, explanation, timestamp) VALUES (?, ?, ?, ?, ?)",
              (username, title, artist, explanation, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def get_history(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT song_title, artist, explanation, timestamp FROM history WHERE username = ? ORDER BY timestamp DESC", (username,))
    rows = c.fetchall()
    conn.close()
    return rows

# ====================== AUTH FLOW ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        login()
    with tab2:
        register()
else:
    # Sidebar: User info + History + Logout
    with st.sidebar:
        st.write(f"**Logged in as:** {st.session_state.username}")
        st.divider()
        st.subheader("History")
        history = get_history(st.session_state.username)
        if history:
            for i, (title, artist, explanation, ts) in enumerate(history):
                with st.expander(f"{title} – {artist} ({ts})"):
                    st.write(explanation)
        else:
            st.info("No history yet.")
        st.divider()
        logout()

    # === Main App ===
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    st.title("🎵 Song Explainer AI")
    st.write("Search or paste lyrics to get AI-powered explanations")

    option = st.radio("Input method", ["Search by Title/Artist", "Paste Lyrics"])

    explanation = ""  # To store for history

    if option == "Search by Title/Artist":
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Song Title")
        with col2:
            artist = st.text_input("Artist")

        if st.button("Explain Meaning"):
            if not title or not artist:
                st.warning("Enter both title and artist.")
            else:
                with st.spinner("Fetching lyrics & analyzing..."):
                    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
                    response = requests.get(url)
                    if response.status_code == 200 and response.json().get("lyrics"):
                        lyrics = response.json()["lyrics"]
                        st.subheader(f"{title} by {artist}")
                        st.text_area("Lyrics", lyrics, height=250, disabled=True)
                        st_copy_to_clipboard(lyrics, "📋 Copy Lyrics", "✅ Copied!", key="copy_search")

                        prompt = f"Explain the meaning of these lyrics in an engaging way. Include theme, metaphors, references, and context:\n\n{lyrics}"
                        chat_completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.1-8b-instant",
                        )
                        explanation = chat_completion.choices[0].message.content
                        st.markdown("### 🤖 AI Explanation")
                        st.markdown(explanation)

                        # Save to DB
                        save_history(st.session_state.username, title, artist, explanation)
                    else:
                        st.error("Lyrics not found. Try paste mode!")

    else:  # Paste Lyrics
        lyrics = st.text_area("Paste Lyrics Here", height=300)
        if lyrics.strip():
            if st.button("Explain Meaning"):
                with st.spinner("Analyzing..."):
                    prompt = f"Explain the meaning of these lyrics in an engaging way. Include theme, metaphors, references, and context:\n\n{lyrics}"
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama-3.1-8b-instant",
                    )
                    explanation = chat_completion.choices[0].message.content
                    st.markdown("### 🤖 AI Explanation")
                    st.markdown(explanation)

                    # Save with "Pasted Song" as title
                    save_history(st.session_state.username, "Pasted Song", "", explanation)

            st_copy_to_clipboard(lyrics, "📋 Copy Lyrics", "✅ Copied!", key="copy_paste")

    st.caption("Uses free lyrics.ovh API • Database powered by SQLite")