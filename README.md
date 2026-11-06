# Talk Reflection Studio

A local Streamlit web app that turns a YouTube talk's transcript into six editable responses for a career-oriented presentation reflection.

## Requirements

- Python 3.10+
- An OpenAI API key. **OpenAI API usage costs are separate from ChatGPT Plus.**
- Internet access to fetch YouTube captions and use the OpenAI API.

## Start

```bash
cd youtube-talk-reflection
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set your API key (or enter it into the Settings sidebar)
streamlit run app.py
```

On Windows, activate the venv using `.venv\\Scripts\\activate` instead.

## How to use

1. Paste a YouTube URL.
2. Click **Retrieve captions**.
3. If captions are unavailable, paste or upload a transcript in the text box.
4. Adjust your career goal, then click **Generate all six answers**.
5. Review speaker identity and factual claims, edit your answers, and download `.md` or `.txt`.

## Notes / limitations

- The uploader is not necessarily the speaker, and some videos have multiple speakers. The app instructs the model to avoid guessing.
- Videos with unavailable/blocked captions require a pasted or uploaded transcript; no audio download or transcription is performed.
- Transcript source can contain incorrect automatic captions. Verify before academic submission.
- Long transcripts are divided into segments and condensed into notes first, which incurs additional API usage and can lose some detail.
- An OpenAI API key is necessary for AI generation. Keys in `.env` should never be committed to a public repository.
- The app does not store data in a server database. Streamlit session state lasts for the current session.
