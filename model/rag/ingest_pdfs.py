import os
import glob
import PyPDF2
from vector_db import db

def extract_text_from_pdf(filepath):
    text = ""
    try:
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return text.strip()

def ingest_pdfs(raw_test_dir):
    print(f"Scanning for PDFs in {raw_test_dir}...")
    pdf_files = glob.glob(os.path.join(raw_test_dir, "*.pdf"))
    print(f"Found {len(pdf_files)} PDF files.")

    cases_to_add = []
    
    print("Resetting existing collection to remove dummy cases...")
    try:
        collection_name = db.collection.name
        db.client.delete_collection(collection_name)
        db.collection = db.client.create_collection(collection_name)
        print("Collection reset successfully.")
    except Exception as e:
        print(f"Could not reset collection: {e}")

    for filepath in pdf_files:
        filename = os.path.basename(filepath)
        print(f"Processing {filename}...")
        text = extract_text_from_pdf(filepath)
        if not text:
            print(f"Warning: No text extracted from {filename}")
            continue
        
        # Determine decision based on filename for UI tags
        decision = "unknown"
        if "-App-" in filename:
            decision = "pending"
        elif "-Reply-" in filename:
            decision = "accepted"

        # Limit text length to avoid token limit errors for sentence-transformers
        text_preview = text[:1500] 
        
        cases_to_add.append({
            "id": filename, # ID is exactly the filename
            "query": text_preview, 
            "metadata": {
                "decision": decision,
                "type": "pdf_document"
            }
        })

    if cases_to_add:
        print(f"Generating embeddings and storing {len(cases_to_add)} documents in ChromaDB...")
        db.add_cases(cases_to_add)
        print("Ingestion complete!")
    else:
        print("No documents were added.")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raw_test_dir = os.path.join(base_dir, "raw test")
    
    ingest_pdfs(raw_test_dir)
