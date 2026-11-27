import os

#import anthropic
import requests
from dotenv import load_dotenv
import psycopg2
import numpy as np
import streamlit as st
from RAG import retrieve, answer
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
load_dotenv()

MODEL_LLM = "claude-sonnet-5-5"
#MODEL_EMBED = "paraphrase-multilingual-MiniLM-L12-v2"  # multilingue, bon en français

st.set_page_config(page_title="Chatbot RAG", page_icon="📚")
st.title("📚 Chatbot RAG\n Ask me anything on the Federal Open Market Committee!")


@st.cache_resource
def load_embedder():
    encode_kwargs = {'normalize_embeddings': True}
    return  HuggingFaceEmbeddings(
                    model_name="BAAI/bge-base-en-v1.5",
                    encode_kwargs=encode_kwargs
                )


def read_file(f) -> str:
    if f.name.lower().endswith(".pdf"):
        return [page.extract_text() or "" for page in  PdfReader(f).pages]
    return [f.read().decode("utf-8", errors="ignore")]


def chunk_text(texts: list[str], size: int = 800, overlap: int = 150) -> list[str]:
    semantic_chunker = SemanticChunker(load_embedder(), breakpoint_threshold_type="percentile",
                                               add_start_index=True)
    semantic_chunks = semantic_chunker.create_documents(texts)
    return [c.page_content for c in semantic_chunks]

api_key = True

# with st.sidebar:
#     st.header("Configuration")
#     files = st.file_uploader(
#         "Documents (PDF ou TXT)", type=["pdf", "txt", "md"], accept_multiple_files=True
#     )
#     if st.button("Indexer les documents", disabled=not files):
#         with st.spinner("Indexation en cours..."):
#             chunks = []
#             for f in files:
#                 chunks += chunk_text(read_file(f))
#             embeddings = load_embedder().embed_documents(chunks)
#             st.session_state.chunks = chunks
#             st.session_state.embeddings = embeddings
#         st.success(f"{len(chunks)} passages indexés ✅")

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
        if not api_key:
            reply, sources = "Renseigne ta clé API Anthropic dans la barre latérale.", []
            st.markdown(reply)
        else:
            with st.spinner("Réflexion..."):
                embedder = load_embedder()
                q = embedder.embed_documents([question])[0]
                sources = retrieve(question,q)
                print(sources)
                texts = " ".join(sources)
                #print(sources)
                reply = answer(question, texts)
            st.markdown(reply)
            with st.expander("Sources"):
                for s in sources:
                    st.caption(s)

    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "sources": sources}
    )