import streamlit as st
import requests
from groq import Groq
from st_copy_to_clipboard import st_copy_to_clipboard
import sqlite3
import hashlib
from datetime import datetime
import base64  # For browser download button

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
    st.title("Register New Account")
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
                st.success("Registered successfully! Switch to Login tab.")
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
    tab_login, tab_register = st.tabs(["Login", "Register"])
    with tab_login:
        login()
    with tab_register:
        register()
else:
    # Sidebar
    with st.sidebar:
        st.write(f"**Logged in as:** {st.session_state.username}")
        st.divider()
        st.subheader("Explanation History")
        history = get_history(st.session_state.username)
        if history:
            for title, artist, explanation, ts in history:
                with st.expander(f"{title} – {artist} ({ts})"):
                    st.markdown(explanation)
        else:
            st.info("No history yet.")
        st.divider()
        logout()

    # Main Tabs
    tab_explainer, tab_downloader = st.tabs(["Song Explainer", "Download Free Music"])

    # Groq client
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    with tab_explainer:
        st.header("Song Explainer")
        st.write("Search lyrics or paste them to get an AI-powered explanation")

        option = st.radio("Input method", ["Search by Title/Artist", "Paste Lyrics"], key="explainer_option")

        if option == "Search by Title/Artist":
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Song Title", key="search_title")
            with col2:
                artist = st.text_input("Artist", key="search_artist")

            if st.button("Explain Meaning", key="explain_search"):
                if not title or not artist:
                    st.warning("Please enter both title and artist.")
                else:
                    with st.spinner("Fetching lyrics and analyzing..."):
                        url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
                        response = requests.get(url)
                        if response.status_code == 200 and response.json().get("lyrics"):
                            lyrics = response.json()["lyrics"]
                            st.subheader(f"{title} by {artist}")
                            st.text_area("Lyrics", lyrics, height=250, disabled=True)
                            st_copy_to_clipboard(lyrics, "📋 Copy Lyrics", "✅ Copied!", key="copy_search")

                            prompt = f"Explain the meaning of these song lyrics in an engaging, insightful way. Include overall theme, story, line-by-line breakdown of key parts, metaphors, references, symbolism, and emotional/cultural context:\n\n{lyrics}"
                            chat_completion = client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model="llama-3.1-8b-instant",
                            )
                            explanation = chat_completion.choices[0].message.content
                            st.markdown("### 🤖 AI Explanation")
                            st.markdown(explanation)

                            save_history(st.session_state.username, title, artist, explanation)
                        else:
                            st.error("Lyrics not found for this song. Try 'Paste Lyrics' mode or different spelling.")

        else:  # Paste Lyrics
            lyrics = st.text_area("Paste Lyrics Here", height=300, key="paste_lyrics")
            if lyrics.strip():
                if st.button("Explain Meaning", key="explain_paste"):
                    with st.spinner("Analyzing with AI..."):
                        prompt = f"Explain the meaning of these song lyrics in an engaging, insightful way. Include overall theme, story, line-by-line breakdown of key parts, metaphors, references, symbolism, and emotional/cultural context:\n\n{lyrics}"
                        chat_completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.1-8b-instant",
                        )
                        explanation = chat_completion.choices[0].message.content
                        st.markdown("### 🤖 AI Explanation")
                        st.markdown(explanation)

                        save_history(st.session_state.username, "Pasted Song", "", explanation)

                st_copy_to_clipboard(lyrics, "📋 Copy Lyrics", "✅ Copied!", key="copy_paste")

    with tab_downloader:
        st.header("Download Free & Legal Music")
        st.write("Discover independent music from **Jamendo** – all tracks are Creative Commons licensed and free to download!")

        search_query = st.text_input("Search for music (e.g., rock, chill, instrumental, pop)", key="jamendo_search")
        if st.button("Search Music", key="jamendo_btn"):
            if search_query:
                with st.spinner("Searching Jamendo for free tracks..."):
                    url = "https://api.jamendo.com/v3.0/tracks/"
                    params = {
                    "client_id": st.secrets["JAMENDO_CLIENT_ID"],
                    "format": "json",
                    "limit": 15,
                    "fuzzytags": search_query,  # Changed to fuzzytags
                    "audioformat": "mp3",
                    "include": "musicinfo+licenses"
}
                    response = requests.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        tracks = data.get("results", [])
                        if tracks:
                            st.success(f"Found {len(tracks)} free tracks!")
                            for track in tracks:
                                title = track["name"]
                                artist = track["artist_name"]
                                audio_url = track["audiodownload"]
                                duration = track["duration"]
                                license_url = track.get("license_ccurl", "https://creativecommons.org/licenses/")

                                col1, col2 = st.columns([4, 1])
                                with col1:
                                    st.write(f"**{title}** – {artist}")
                                    st.caption(f"Duration: {duration}s • [License]({license_url})")
                                with col2:
                                    if audio_url:
                                        # Download link with client_id
                                        full_url = audio_url + f"?client_id={st.secrets['JAMENDO_CLIENT_ID']}"
                                        dl_resp = requests.get(full_url)
                                        if dl_resp.status_code == 200:
                                            b64 = base64.b64encode(dl_resp.content).decode()
                                            href = f'<a href="data:audio/mp3;base64,{b64}" download="{title} - {artist}.mp3"><button>⬇️ Download MP3</button></a>'
                                            st.markdown(href, unsafe_allow_html=True)
                        else:
                            st.info("No tracks found. Try broader keywords like 'chill', 'rock', or 'instrumental'.")
                    else:
                        st.error("Jamendo API error. Check your client_id in Secrets.")
            else:
                st.warning("Enter a search term!")

        st.caption("All music from Jamendo is legally downloadable under Creative Commons • Supports independent artists worldwide!")

st.caption("Song Explainer AI + Legal Music Downloader • Built for learning & fun")