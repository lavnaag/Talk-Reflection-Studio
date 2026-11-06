"""YouTube Talk Reflection — editable, transcript-grounded coursework answers."""
import os
import re
from urllib.parse import urlparse, parse_qs

import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
st.set_page_config(page_title="Talk Reflection Studio", page_icon="🎓", layout="wide")

QUESTIONS = [
    ("speaker", "Name of Speaker"),
    ("affiliation", "Affiliation of Speaker"),
    ("summary", "Summary of Talk (minimum 50 words)"),
    ("purpose", "Purpose of the Event / Presentation (at least 3 sentences)"),
    ("useful", "Most Useful Part for My Learning or Career Goals (at least 3 sentences)"),
    ("explore", "Topics to Explore More Deeply (at least 1 sentence)"),
]

class Answers(BaseModel):
    speaker: str
    affiliation: str
    summary: str
    purpose: str
    useful: str
    explore: str
    evidence: str


def youtube_id(value: str) -> str | None:
    try:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            if parsed.path == "/watch":
                vid = parse_qs(parsed.query).get("v", [None])[0]
            elif parsed.path.startswith(("/shorts/", "/live/", "/embed/")):
                vid = parsed.path.split("/")[2]
            else:
                return None
        elif host in ("youtu.be", "www.youtu.be"):
            vid = parsed.path.strip("/").split("/")[0]
        else:
            return None
        return vid if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else None
    except (ValueError, IndexError):
        return None


def get_metadata(video_id: str) -> dict:
    try:
        r = requests.get("https://www.youtube.com/oembed", params={"url":f"https://www.youtube.com/watch?v={video_id}","format":"json"}, timeout=12)
        r.raise_for_status()
        data = r.json()
        return {"title": data.get("title", ""), "channel": data.get("author_name", "")}
    except (requests.RequestException, ValueError):
        return {"title": "", "channel": ""}


def get_captions(video_id: str) -> str:
    api = YouTubeTranscriptApi()
    try:
        transcript = api.fetch(video_id, languages=["en"])
    except Exception:
        # Also allow other languages when English is missing.
        available = api.list(video_id)
        selected = next(iter(available))
        transcript = selected.fetch()
    return "\n".join(f"[{int(segment.start//60):02d}:{int(segment.start%60):02d}] {segment.text}" for segment in transcript)


def sentence_count(text: str) -> int:
    return len(re.findall(r"[^.!?\n]+[.!?](?:\s|$)", text.strip()))


def validate(answers: Answers) -> list[str]:
    issues = []
    if len(answers.summary.split()) < 50:
        issues.append("Summary must contain at least 50 words.")
    if sentence_count(answers.purpose) < 3:
        issues.append("Purpose needs at least 3 sentences ending in punctuation.")
    if sentence_count(answers.useful) < 3:
        issues.append("Career relevance needs at least 3 sentences ending in punctuation.")
    if sentence_count(answers.explore) < 1:
        issues.append("Further exploration needs at least 1 complete sentence.")
    return issues


def chunks(text: str, max_chars: int = 18000) -> list[str]:
    lines = text.splitlines()
    result, current = [], []
    length = 0
    for line in lines:
        if len(line) > max_chars:
            if current:
                result.append("\n".join(current))
                current, length = [], 0
            for pos in range(0, len(line), max_chars):
                result.append(line[pos:pos+max_chars])
            continue
        if length + len(line) + 1 > max_chars and current:
            result.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        result.append("\n".join(current))
    return result


def generate(client: OpenAI, model: str, transcript: str, metadata: dict, goals: str) -> Answers:
    parts = chunks(transcript)
    if len(parts) > 20:
        raise ValueError("Transcript is unusually long. Please provide a shorter talk or edit the transcript before generating.")
    if len(parts) > 1:
        notes = []
        for i, part in enumerate(parts):
            response = client.responses.create(
                model=model,
                instructions="Make accurate, compact speaker/affiliation clues and talk notes grounded in this excerpt only. Preserve timestamps and career-relevant ideas. Never invent. Limit to 450 words.",
                input=f"Video title: {metadata['title']}\nChannel: {metadata['channel']}\nTranscript part {i+1}/{len(parts)}:\n{part}",
            )
            notes.append(f"PART {i+1}\n{response.output_text}")
        source = "\n\n".join(notes)
        provenance = "Summarized transcript sections (with timestamps where provided)"
    else:
        source = transcript
        provenance = "Transcript"

    guidance = """Produce SIX answers for a student's reflection on a tech-related presentation, plus a brief evidence note.
- Speaker name and affiliation: ONLY when grounded in the transcript/title; channel owner is NOT automatically the speaker. If unclear write 'Not established from the available transcript.'
- Summary: >= 65 words, accurately describe specific content without exaggeration.
- Purpose: >= 3 complete sentences, describing why the talk was delivered and its intended audience/outcome; infer gently if not stated.
- Useful: >= 3 complete sentences in the first-person student voice, tied to the user's career goal. Refer to specific talk details; avoid claiming personal experience not provided by the user.
- Explore: >= 1 complete first-person sentence naming a specific topic from this video.
- Evidence: short plain-text reference to timestamps or evidence; if precise timestamps are absent, say so. Do not fabricate quotes or timestamps.
- Be natural, specific, thoughtful, not robotic. Separate factual transcript claims from personal interpretation. Do not invent credentials or events.
"""
    result = client.responses.parse(
        model=model,
        instructions=guidance,
        input=f"Video title: {metadata['title'] or 'Unavailable'}\nUploader/channel (not necessarily speaker): {metadata['channel'] or 'Unavailable'}\nCareer goal: {goals}\nSource type: {provenance}\n\n{source}",
        text_format=Answers,
    )
    if not result.output_parsed:
        raise ValueError("The model did not return usable answers. Please try again.")
    return result.output_parsed


def as_markdown(values: dict, link: str, title: str) -> str:
    header = f"# Presentation Reflection\n\n**Video:** {title or link}\n**Link:** {link}\n\n"
    return header + "\n\n".join(f"## {label}\n\n{values.get(key, '').strip()}" for key, label in QUESTIONS)

st.title("🎓 Talk Reflection Studio")
st.write("Paste a YouTube talk and get **six editable, transcript-grounded answers** tailored to your tech job application goals.")
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("OpenAI API key", value=os.getenv("OPENAI_API_KEY", ""), type="password", help="Only sent to OpenAI for generating the responses. You can also store it in .env locally.")
    model = st.text_input("OpenAI model", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    st.caption("API calls are billed separately from ChatGPT subscriptions. Auto-captions are not guaranteed to be available.")

url = st.text_input("YouTube video link", placeholder="https://www.youtube.com/watch?v=...")
goals = st.text_area("My learning / career goal", value="Prepare for software engineering and related tech job applications by improving technical knowledge, interview readiness, industry awareness, networking, and professional communication.", height=95)
video_id = youtube_id(url) if url else None
if url and not video_id:
    st.warning("Please paste a valid youtube.com or youtu.be video link.")

if "last_video" not in st.session_state:
    st.session_state.last_video = None
if video_id and video_id != st.session_state.last_video:
    st.session_state.last_video = video_id
    st.session_state.transcript = ""
    st.session_state.answers = None
    st.session_state.meta = get_metadata(video_id)

if video_id:
    meta = st.session_state.get("meta", {})
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader(meta.get("title") or "YouTube presentation")
        st.caption("Uploaded by: " + (meta.get("channel") or "Unknown") + " · Uploader is not necessarily the speaker")
    with c2:
        st.image(f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)

    if st.button("1 · Retrieve captions", use_container_width=True):
        try:
            with st.spinner("Retrieving available YouTube captions…"):
                st.session_state.transcript = get_captions(video_id)
            st.success("Captions retrieved. Review them before generating.")
        except Exception:
            st.warning("Captions could not be retrieved. This can happen with disabled captions, restrictions, or YouTube blocking automated requests. Paste or upload a transcript instead.")

    uploaded = st.file_uploader("Optional: upload transcript (.txt)", type=["txt"])
    transcript_text = st.text_area("Transcript (automatically retrieved or paste/edit your own)", value=(uploaded.getvalue().decode("utf-8-sig", errors="replace") if uploaded else st.session_state.get("transcript", "")), height=200, key="transcript_editor")
    if st.button("2 · Generate all six answers", type="primary", use_container_width=True):
        if not api_key:
            st.error("Enter an OpenAI API key in Settings first.")
        elif len(transcript_text.strip()) < 100:
            st.error("A transcript of at least 100 characters is needed for accurate answers.")
        else:
            try:
                with st.spinner("Analyzing the talk and drafting your reflection…"):
                    output = generate(OpenAI(api_key=api_key), model, transcript_text, st.session_state.get("meta", {}), goals)
                    st.session_state.answers = output.model_dump()
                st.success("Draft generated. Review the speaker identity and the first-person reflections before submitting.")
            except Exception as exc:
                st.error(f"Generation failed: {exc}")

if st.session_state.get("answers"):
    st.divider()
    st.header("Your editable reflection")
    values = {}
    for key, question in QUESTIONS:
        text = st.session_state.answers[key]
        values[key] = st.text_area(question, value=text, height=(150 if key in ("summary", "purpose", "useful") else 85), key=f"answer_{key}")
    st.caption("Evidence / source cues: " + st.session_state.answers.get("evidence", ""))
    current = Answers(**values, evidence=st.session_state.answers.get("evidence", ""))
    problems = validate(current)
    if problems:
        for problem in problems:
            st.warning(problem)
    else:
        st.success("All minimum word/sentence requirements are met.")
    markdown = as_markdown(values, url, st.session_state.get("meta", {}).get("title", ""))
    st.download_button("Download reflection (.md)", markdown, file_name="presentation_reflection.md", mime="text/markdown", use_container_width=True)
    st.download_button("Download reflection (.txt)", markdown, file_name="presentation_reflection.txt", mime="text/plain", use_container_width=True)
    with st.expander("Copyable final response"):
        st.code(markdown, language="markdown")

st.divider()
st.caption("Uses the video's available captions or a transcript you supply. YouTube transcripts may be incomplete or wrong; speaker identity and affiliations should always be verified before submission.")
