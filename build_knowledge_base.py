import os
import shutil
from langchain_community.vectorstores import FAISS # <--- CHANGED
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import Config

def ingest_all_policies():
    print(f"🚀 Starting Ingestion (Engine: FAISS)...")
    
    embeddings = OpenAIEmbeddings(
        model=Config.EMBEDDING_MODEL,
        api_key=Config.OPENAI_API_KEY,
        base_url=Config.OPENAI_BASE_URL
    )

    # 1. Reset
    if os.path.exists(Config.VECTOR_DB_PATH):
        shutil.rmtree(Config.VECTOR_DB_PATH)

    # 2. Load Docs
    files = [f for f in os.listdir(Config.POLICIES_DIR) if f.endswith(".pdf")]
    all_docs = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    for file in files:
        file_path = os.path.join(Config.POLICIES_DIR, file)
        try:
            region = file.split("_")[1].replace(".pdf", "")
        except:
            region = "General"
            
        print(f"📖 Reading {file}...")
        loader = PyPDFLoader(file_path)
        chunks = text_splitter.split_documents(loader.load())
        
        for doc in chunks:
            doc.metadata["region"] = region
            
        all_docs.extend(chunks)

    # 3. Build & Save
    if all_docs:
        vector_db = FAISS.from_documents(all_docs, embeddings)
        vector_db.save_local(Config.VECTOR_DB_PATH)
        print(f"🎉 Success! Saved FAISS index to {Config.VECTOR_DB_PATH} with {len(all_docs)} chunks.")
    else:
        print("❌ No documents found.")

if __name__ == "__main__":
    ingest_all_policies()