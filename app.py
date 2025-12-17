import streamlit as st
import requests
from groq import Groq
from st_copy_to_clipboard import st_copy_to_clipboard
import sqlite3
import hashlib
from datetime import datetime
import os
import tempfile
import re
import yt_dlp  # Reliable YouTube downloader

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
                st.success("Registered successfully! Go to Login tab.")
            except sqlite3.IntegrityError:
                st.error("Username already taken.")
            conn.close()
        else:
            st.warning("Fill in both fields.")

def login():
    st.title("Login")
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
            st.error("Wrong username or password")

def logout():
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
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
        st.write(f"**Welcome, {st.session_state.username}!**")
        st.divider()
        st.subheader("Your Explanation History")
        history = get_history(st.session_state.username)
        if history:
            for title, artist, explanation, ts in history:
                with st.expander(f"{title} – {artist} ({ts})"):
                    st.markdown(explanation)
        else:
            st.info("No explanations saved yet.")
        st.divider()
        logout()

    # Main Tabs
    tab_explainer, tab_youtube = st.tabs(["Song Explainer", "YouTube MP3 Downloader"])

    # Groq client
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

    # ====================== SONG EXPLAINER TAB ======================
    with tab_explainer:
        st.header("Song Explainer")
        st.write("Get deep AI explanations of any song lyrics")

        option = st.radio("How do you want to input lyrics?", ["Search by Title & Artist", "Paste Lyrics Directly"], key="input_method")

        if option == "Search by Title & Artist":
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Song Title", key="title_search")
            with col2:
                artist = st.text_input("Artist", key="artist_search")

            if st.button("Fetch Lyrics & Explain", key="fetch_explain"):
                if title and artist:
                    with st.spinner("Fetching lyrics..."):
                        url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
                        resp = requests.get(url)
                        if resp.status_code == 200 and resp.json().get("lyrics"):
                            lyrics = resp.json()["lyrics"]
                            st.subheader(f"{title} – {artist}")
                            st.text_area("Lyrics", lyrics, height=250, disabled=True)
                            st_copy_to_clipboard(lyrics, "Copy Lyrics")

                            with st.spinner("Generating AI explanation..."):
                                prompt = f"Explain the meaning of these lyrics in an engaging and insightful way. Include theme, story, key metaphors, symbolism, and context:\n\n{lyrics}"
                                completion = client.chat.completions.create(
                                    messages=[{"role": "user", "content": prompt}],
                                    model="llama-3.1-8b-instant"
                                )
                                explanation = completion.choices[0].message.content
                                st.markdown("### AI Explanation")
                                st.markdown(explanation)
                                save_history(st.session_state.username, title, artist, explanation)
                        else:
                            st.error("Lyrics not found. Try different spelling or paste them manually.")
                else:
                    st.warning("Please enter both song title and artist.")

        else:  # Paste lyrics
            lyrics = st.text_area("Paste your lyrics here", height=300, key="pasted_lyrics")
            if lyrics.strip():
                st_copy_to_clipboard(lyrics, "Copy Lyrics")
                if st.button("Explain These Lyrics", key="explain_pasted"):
                    with st.spinner("Analyzing with AI..."):
                        prompt = f"Explain the meaning of these lyrics in an engaging and insightful way. Include theme, story, key metaphors, symbolism, and context:\n\n{lyrics}"
                        completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.1-8b-instant"
                        )
                        explanation = completion.choices[0].message.content
                        st.markdown("### AI Explanation")
                        st.markdown(explanation)
                        save_history(st.session_state.username, "Pasted Lyrics", "", explanation)

    # ====================== YOUTUBE DOWNLOADER TAB (RELIABLE yt-dlp) ======================
    with tab_youtube:
        st.header("YouTube to MP3 Downloader")
        st.info("Paste any YouTube video URL → get high-quality MP3 with preview!")
        st.warning("⚠️ Only download content you have permission for (personal use, fair use, your own videos). Respect copyright laws.")

        youtube_url = st.text_input(
            "Paste YouTube URL here",
            placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
            key="youtube_url_input"
        )

        if st.button("Extract MP3 Audio", key="download_mp3"):
            if not youtube_url.strip():
                st.warning("Please paste a valid YouTube URL.")
            else:
                with st.spinner("Downloading and converting audio (yt-dlp + FFmpeg)..."):
                    try:
                        with tempfile.TemporaryDirectory() as tmp_dir:
                            ydl_opts = {
                                'format': 'bestaudio/best',
                                'postprocessors': [{
                                    'key': 'FFmpegExtractAudio',
                                    'preferredcodec': 'mp3',
                                    'preferredquality': '192',
                                }],
                                'outtmpl': os.path.join(tmp_dir, '%(title)s - %(uploader)s.%(ext)s'),
                                'quiet': True,
                                'noplaylist': True,
                            }

                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                info = ydl.extract_info(youtube_url, download=True)
                                title = info.get('title', 'YouTube Audio')
                                uploader = info.get('uploader', 'Unknown')

                            # Find the converted MP3
                            mp3_files = [f for f in os.listdir(tmp_dir) if f.endswith('.mp3')]
                            if not mp3_files:
                                st.error("MP3 conversion failed — FFmpeg may be missing or not in PATH.")
                            else:
                                mp3_path = os.path.join(tmp_dir, mp3_files[0])
                                with open(mp3_path, "rb") as f:
                                    audio_bytes = f.read()

                                safe_name = re.sub(r'[^\w\s-]', '', f"{title} - {uploader}").strip()
                                safe_name = re.sub(r'\s+', '_', safe_name)
                                filename = f"{safe_name}.mp3" if safe_name else "audio.mp3"

                                st.success(f"✅ **{title}** by **{uploader}** – Ready!")
                                st.audio(audio_bytes, format="audio/mp3")
                                st.download_button(
                                    label="⬇️ Download MP3",
                                    data=audio_bytes,
                                    file_name=filename,
                                    mime="audio/mpeg",
                                    key="mp3_download"
                                )

                    except Exception as e:
                        error_msg = str(e).lower()
                        st.error(f"Download failed: {str(e)}")
                        if "ffmpeg" in error_msg or "ffprobe" in error_msg:
                            st.error("FFmpeg not found! Download from https://www.gyan.dev/ffmpeg/builds/ and add 'bin' to PATH.")

st.caption("Song Explainer AI + YouTube MP3 Downloader • Built with ❤️ using Streamlit, Groq & yt-dlp")