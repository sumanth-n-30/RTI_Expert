import json
import os
from vector_db import db

def ingest_data(filepath: str):
    print(f"Loading data from {filepath}...")
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} not found.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} records.")
    
    cases_to_add = []
    for i, item in enumerate(data):
        # The existing dataset.json has "query" and "status"
        cases_to_add.append({
            "id": f"case_{i}",
            "query": item["query"],
            "metadata": {
                "decision": item.get("status", "unknown")
            }
        })
        
    print(f"Generating embeddings and storing in ChromaDB...")
    db.add_cases(cases_to_add)
    print("Ingestion complete!")

if __name__ == "__main__":
    # Assuming dataset.json is in the parent directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, "dataset.json")
    
    ingest_data(dataset_path)
