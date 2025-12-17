import streamlit as st
import requests  # NEW: For lyrics.ovh API
from groq import Groq
from st_copy_to_clipboard import st_copy_to_clipboard  # For copy button

# === Groq API (using secrets for deployment) ===
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

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
            with st.spinner("Searching lyrics and analyzing..."):
                # Fetch from free lyrics.ovh API (no key, reliable on cloud)
                url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
                response = requests.get(url)
                
                if response.status_code == 200 and response.json().get("lyrics"):
                    lyrics = response.json()["lyrics"]
                    st.subheader(f"{title} by {artist}")

                    # Display lyrics
                    st.text_area("Lyrics", lyrics, height=250, disabled=True)

                    # Working copy button
                    st_copy_to_clipboard(
                        lyrics,
                        before_copy_label="📋 Copy Lyrics to Clipboard",
                        after_copy_label="✅ Copied!",
                        key="copy_search"
                    )

                    # AI explanation
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
                    st.error("Lyrics not found for this song. Try 'Paste Lyrics' mode or a different title/artist!")

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

        # Copy button for paste mode too
        st_copy_to_clipboard(
            lyrics,
            before_copy_label="📋 Copy Lyrics to Clipboard",
            after_copy_label="✅ Copied!",
            key="copy_paste"
        )

st.caption("Search uses free lyrics.ovh API – works great on hosted apps! Paste mode always perfect.")