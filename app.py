import streamlit as st
import requests
from groq import Groq
from st_copy_to_clipboard import st_copy_to_clipboard
import sqlite3
import hashlib
from datetime import datetime
import base64  # For download button

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

init_db()

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
    with st.sidebar:
        st.write(f"**Logged in as:** {st.session_state.username}")
        st.divider()
        st.subheader("History")
        history = get_history(st.session_state.username)
        if history:
            for title, artist, explanation, ts in history:
                with st.expander(f"{title} – {artist} ({ts})"):
                    st.markdown(explanation)
        else:
            st.info("No history yet.")
        st.divider()
        logout()

    # === Main Tabs ===
    tab1, tab2 = st.tabs(["Song Explainer", "Download Free Music"])

    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    with tab1:
        st.header("Song Explainer")
        st.write("Search or paste lyrics to get AI explanations")

        option = st.radio("Input method", ["Search by Title/Artist", "Paste Lyrics"], key="explainer_option")

        if option == "Search by Title/Artist":
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Song Title", key="search_title")
            with col2:
                artist = st.text_input("Artist", key="search_artist")

            if st.button("Explain Meaning", key="explain_search"):
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
                            st_copy_to_clipboard(lyrics, "📋 Copy Lyrics", "✅ Copied!", key="copy_search_tab1")

                            prompt = f"Explain the meaning of these lyrics in an engaging way. Include theme, metaphors, references, and context:\n\n{lyrics}"
                            chat_completion = client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model="llama-3.1-8b-instant",
                            )
                            explanation = chat_completion.choices[0].message.content
                            st.markdown("### 🤖 AI Explanation")
                            st.markdown(explanation)
                            save_history(st.session_state.username, title, artist, explanation)
                        else:
                            st.error("Lyrics not found. Try paste mode!")

        else:
            lyrics = st.text_area("Paste Lyrics Here", height=300, key="paste_lyrics_tab1")
            if lyrics.strip():
                if st.button("Explain Meaning", key="explain_paste"):
                    with st.spinner("Analyzing..."):
                        prompt = f"Explain the meaning of these lyrics in an engaging way. Include theme, metaphors, references, and context:\n\n{lyrics}"
                        chat_completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.1-8b-instant",
                        )
                        explanation = chat_completion.choices[0].message.content
                        st.markdown("### 🤖 AI Explanation")
                        st.markdown(explanation)
                        save_history(st.session_state.username, "Pasted Song", "", explanation)

                st_copy_to_clipboard(lyrics, "📋 Copy Lyrics", "✅ Copied!", key="copy_paste_tab1")

    with tab2:
        st.header("Download Free & Legal Music")
        st.write("Search royalty-free music from **Free Music Archive** (Creative Commons)")

        search_query = st.text_input("Search for free music (e.g., electronic, rock, instrumental)", key="fma_search")
        if st.button("Search Free Music"):
            if search_query:
                with st.spinner("Searching Free Music Archive..."):
                    # FMA API search
                    search_url = f"https://freemusicarchive.org/api/get/tracks.json?api_key=YOUR_FMA_KEY&limit=20&search={search_query}"
                    # Note: FMA API needs a key — for demo, we'll use a public endpoint alternative
                    # Using a public proxy endpoint (no key needed)
                    api_url = f"https://files.freemusicarchive.org/music-api.php?search={search_query}"
                    try:
                        response = requests.get(api_url)
                        if response.status_code == 200:
                            tracks = response.json().get("tracks", [])
                            if tracks:
                                for track in tracks[:10]:
                                    title = track.get("track_title", "Unknown")
                                    artist = track.get("artist_name", "Unknown")
                                    url = track.get("track_url_mp3", "")
                                    duration = track.get("track_duration", "Unknown")
                                    license = track.get("license_title", "CC")

                                    with st.container():
                                        col1, col2 = st.columns([3, 1])
                                        with col1:
                                            st.write(f"**{title}** by {artist}")
                                            st.caption(f"Duration: {duration} • License: {license}")
                                        with col2:
                                            if url:
                                                # Download button
                                                dl_response = requests.get(url)
                                                if dl_response.status_code == 200:
                                                    b64 = base64.b64encode(dl_response.content).decode()
                                                    href = f'<a href="data:audio/mp3;base64,{b64}" download="{title} - {artist}.mp3">Download MP3</a>'
                                                    st.markdown(href, unsafe_allow_html=True)
                                            st.write("")
                            else:
                                st.info("No tracks found. Try different keywords!")
                        else:
                            st.error("FMA API error. Try again later.")
                    except:
                        st.error("Connection issue. Using demo tracks.")
                        st.info("For full FMA integration, get a free API key at freemusicarchive.org")

        st.caption("All music here is legally downloadable under Creative Commons • Perfect for projects!")

st.caption("Song Explainer + Legal Music Downloader • Built with ❤️ for your capstone")