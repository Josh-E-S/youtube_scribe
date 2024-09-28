import streamlit as st
from openai import OpenAI
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os

# Get API keys from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
youtube_api_key = os.getenv("YOUTUBE_API_KEY")

# Check if the keys exist
if not openai_api_key:
    raise ValueError("No OpenAI API Key found! Please set OPENAI_API_KEY as an environment variable.")
if not youtube_api_key:
    raise ValueError("No YouTube API Key found! Please set YOUTUBE_API_KEY as an environment variable.")

# Set up OpenAI client
client = OpenAI(api_key=openai_api_key)

# Set up YouTube API client
youtube = build('youtube', 'v3', developerKey=youtube_api_key)

def local_css(file_name):
    with open(file_name, "r") as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def get_youtube_video_id(url):
    video_id = re.search(r'(?<=v=)[\w-]+', url)
    if not video_id:
        video_id = re.search(r'(?<=be/)[\w-]+', url)
    return video_id.group(0) if video_id else None

def get_youtube_transcript(video_id):
    try:
        results = youtube.captions().list(
            part="snippet",
            videoId=video_id
        ).execute()

        caption_id = results['items'][0]['id']
        transcript = youtube.captions().download(
            id=caption_id,
            tfmt='srt'
        ).execute()

        # Process the SRT format to extract just the text
        lines = transcript.decode('utf-8').split('\n\n')
        full_transcript = ""
        for line in lines:
            parts = line.split('\n')
            if len(parts) >= 3:
                full_transcript += parts[2] + " "

        return full_transcript.strip()
    except HttpError as e:
        st.error(f"An error occurred: {e}")
        return None

def process_transcript(transcript, model):
    prompt = f"""
    Analyze and format the following transcript into a well-structured script with appropriate sections and headers. Follow these guidelines:

    1. First, carefully analyze the content to identify major themes, topics, or segments within the video.
    2. Organize the content into logical sections based on your analysis.
    3. Add appropriate headers (##) for each major section. These should reflect the main topic or theme of that section.
    4. Use subheaders (###) for subsections if necessary, but use them sparingly.
    5. Format the content as a script in Markdown, following these additional rules:
       - Remove any timestamps or artifacts.
       - Add appropriate tags for speakers (e.g., [Narrator], [Character Name]) when there's a clear change in speaker.
       - Maintain the flow of the dialogue and narration without excessive breaks.
       - Correct any obvious grammatical errors or run-on sentences.
    6. Ensure the final output is well-structured, easy to read, and accurately reflects the content and flow of the original video.

    Here's the transcript to process:

    {transcript}
    """
    
    messages = [
        {"role": "system", "content": "You are an expert assistant that analyzes and formats transcripts into well-structured, readable scripts with appropriate sections and headers."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True
    )
    
    return response

def stream_transcript_generator(response):
    full_response = ""
    
    for chunk in response:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_response += content
            yield content

    yield full_response

def main():
    local_css("style.css")

    with st.sidebar:
        st.image(os.path.join(os.getcwd(), "assets/youtube.png"), width=175)
        st.markdown('<div class="centered-title">____YouTube Scribe____</div>', unsafe_allow_html=True)
        st.write("")
        st.write("")
        
        model = st.selectbox(
            "--------Select GPT Model--------",
            ("gpt-4-1106-preview", "gpt-4"),
            index=0
        )

    st.header("YouTube Video Scribe")
    
    url = st.text_input("Enter YouTube URL:")
    
    if st.button("Transcribe", use_container_width=True):
        if url:
            video_id = get_youtube_video_id(url)
            if video_id:
                with st.spinner("Fetching transcript..."):
                    transcript = get_youtube_transcript(video_id)
                
                if transcript:
                    with st.spinner("Processing transcript..."):
                        response = process_transcript(transcript, model)
                        
                        final_output = st.write_stream(stream_transcript_generator(response))
                        
                        st.download_button(
                            label="Download Markdown",
                            data=final_output,
                            file_name="processed_script.md",
                            mime="text/markdown"
                        )
            else:
                st.error("Invalid YouTube URL provided.")
        else:
            st.error("Please enter a YouTube URL.")

if __name__ == "__main__":
    main()