import streamlit as st
import os
import pickle
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from openai import OpenAI

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Set up OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("No OpenAI API Key found! Please set OPENAI_API_KEY as an environment variable.")
client = OpenAI(api_key=openai_api_key)

def get_authenticated_service():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def get_youtube_transcript(video_id):
    try:
        youtube = get_authenticated_service()
        results = youtube.captions().list(
            part="snippet",
            videoId=video_id
        ).execute()

        if not results['items']:
            return None  # No captions found

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

def get_youtube_video_id(url):
    video_id = re.search(r'(?<=v=)[\w-]+', url)
    if not video_id:
        video_id = re.search(r'(?<=be/)[\w-]+', url)
    return video_id.group(0) if video_id else None

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
    st.title("YouTube Video Scribe")
    
    model = st.sidebar.selectbox(
        "Select GPT Model",
        ("gpt-3.5-turbo", "gpt-4"),
        index=0
    )

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