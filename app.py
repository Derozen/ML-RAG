import os

#import anthropic
import requests
import numpy as np
import streamlit as st
#from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

MODEL_LLM = "claude-sonnet-5-5"
MODEL_EMBED = "paraphrase-multilingual-MiniLM-L12-v2"  # multilingue, bon en français

st.set_page_config(page_title="Chatbot RAG", page_icon="📚")
st.title("📚 Chatbot RAG")


@st.cache_resource
def load_embedder():
    return SentenceTransformer(MODEL_EMBED)


def read_file(f) -> str:
    if f.name.lower().endswith(".pdf"):
        return "\n".join(page.extract_text() or "" for page in requests.t)#PdfReader(f).pages)
    return f.read().decode("utf-8", errors="ignore")


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def retrieve(question: str, k: int = 4) -> list[str]:
    embedder = load_embedder()
    q = embedder.encode([question], normalize_embeddings=True)[0]
    scores = st.session_state.embeddings @ q
    top = np.argsort(scores)[::-1][:k]
    return [st.session_state.chunks[i] for i in top]


def answer(question: str, passages: list[str], api_key: str) -> str:
    context = "\n\n---\n\n".join(passages)
    client = requests #anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL_LLM,
        max_tokens=1000,
        system=(
            "Tu es un assistant qui répond uniquement à partir du contexte fourni. "
            "Si la réponse n'est pas dans le contexte, dis-le clairement. "
            "Réponds dans la langue de la question."
        ),
        messages=[
            {
                "role": "user",
                "content": f"<contexte>\n{context}\n</contexte>\n\nQuestion : {question}",
            }
        ],
    )
    return response.content[0].text


# ---------- Barre latérale : clé API + documents ----------
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input(
        "Clé API Anthropic",
        type="password",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
    )
    files = st.file_uploader(
        "Documents (PDF ou TXT)", type=["pdf", "txt", "md"], accept_multiple_files=True
    )
    if st.button("Indexer les documents", disabled=not files):
        with st.spinner("Indexation en cours..."):
            chunks = []
            for f in files:
                chunks += chunk_text(read_file(f))
            embeddings = load_embedder().encode(chunks, normalize_embeddings=True)
            st.session_state.chunks = chunks
            st.session_state.embeddings = embeddings
        st.success(f"{len(chunks)} passages indexés ✅")

# ---------- Chat ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                for s in msg["sources"]:
                    st.caption(s)

if question := st.chat_input("Pose ta question sur tes documents..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if "chunks" not in st.session_state:
            reply, sources = "Indexe d'abord des documents dans la barre latérale.", []
            st.markdown(reply)
        elif not api_key:
            reply, sources = "Renseigne ta clé API Anthropic dans la barre latérale.", []
            st.markdown(reply)
        else:
            with st.spinner("Réflexion..."):
                sources = retrieve(question)
                reply = answer(question, sources, api_key)
            st.markdown(reply)
            with st.expander("Sources"):
                for s in sources:
                    st.caption(s)

    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "sources": sources}
    )