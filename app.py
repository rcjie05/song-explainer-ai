import streamlit as st
from lyricsgenius import Genius
from groq import Groq
from st_copy_to_clipboard import st_copy_to_clipboard  # NEW: Import the working copy component

# === API Keys ===
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genius = Genius(st.secrets["GENIUS_TOKEN"])

st.title("🎵 Song Explainer AI")
st.write("Get deep, fun explanations of any song lyrics instantly!")

option = st.radio("Input method", ["Search by Title/Artist", "Paste Lyrics"])

if option == "Search by Title/Artist":
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Song Title")
    with col2:
        artist = st.text_input("Artist")

    if st.button("Explain Meaning"):
        if not title or not artist:
            st.warning("Please enter both song title and artist.")
        else:
            with st.spinner("Searching lyrics on Genius and analyzing..."):
                song = genius.search_song(title, artist)
                if song and song.lyrics:
                    lyrics = song.lyrics
                    st.subheader(f"{song.title} by {song.artist}")

                    # Display lyrics
                    st.text_area("Lyrics", lyrics, height=250, disabled=True)

                    # === REAL WORKING COPY BUTTON ===
                    st_copy_to_clipboard(
                        lyrics,
                        before_copy_label="📋 Copy Lyrics to Clipboard",
                        after_copy_label="✅ Copied!",
                        key="copy_search_lyrics"
                    )

                    # Run AI explanation
                    prompt = f"""
                    Explain the meaning of these song lyrics in an engaging, insightful way.
                    Include:
                    - Overall theme and story
                    - Line-by-line breakdown of key parts
                    - Metaphors, references, and symbolism
                    - Emotional or cultural context
                    Keep it fun and easy to read:

                    {lyrics}
                    """
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama-3.1-8b-instant",
                    )
                    explanation = chat_completion.choices[0].message.content
                    st.markdown("### 🤖 AI Explanation")
                    st.markdown(explanation)
                else:
                    st.error("Song not found or lyrics unavailable. Try 'Paste Lyrics' mode instead!")

else:  # Paste Lyrics mode
    lyrics = st.text_area("Paste Lyrics Here", height=300)

    if lyrics.strip():
        if st.button("Explain Meaning"):
            with st.spinner("Analyzing with AI..."):
                prompt = f"""
                Explain the meaning of these song lyrics in an engaging, insightful way.
                Include:
                - Overall theme and story
                - Line-by-line breakdown of key parts
                - Metaphors, references, and symbolism
                - Emotional or cultural context
                Keep it fun and easy to read:

                {lyrics}
                """
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.1-8b-instant",
                )
                explanation = chat_completion.choices[0].message.content
                st.markdown("### 🤖 AI Explanation")
                st.markdown(explanation)

        # Optional: Add copy button in paste mode too
        st_copy_to_clipboard(
            lyrics,
            before_copy_label="📋 Copy Lyrics to Clipboard",
            after_copy_label="✅ Copied!",
            key="copy_paste_lyrics"
        )

st.caption("Tip: Auto-search sometimes fails due to Genius restrictions. Pasting lyrics always works perfectly!")