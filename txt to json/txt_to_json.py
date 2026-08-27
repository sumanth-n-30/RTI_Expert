import os
import re
import json

# ==============================
# CONFIG
# ==============================
FOLDER_PATH = r"D:\MAJOR PROJECT\test1.1\orc text test"     # folder containing .txt files
OUTPUT_FILE = r"D:\MAJOR PROJECT\test1.1\txt to json\database.json"


# ==============================
# CLEAN TEXT
# ==============================
def clean_text(text):
    text = re.sub(r'\s+', ' ', text)   # remove extra spaces/newlines
    return text.strip()


# ==============================
# READ FILE
# ==============================
def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return clean_text(f.read())
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return ""


# ==============================
# EXTRACT SECTIONS
# ==============================
def extract_sections(text):
    query = ""
    reply = ""
    decision = ""

    try:
        q_match = re.search(r'(information sought|query)(.*?)(reply|response)', text, re.I)
        r_match = re.search(r'(reply|response)(.*?)(decision|order)', text, re.I)
        d_match = re.search(r'(decision|order)(.*)', text, re.I)

        if q_match:
            query = q_match.group(2)

        if r_match:
            reply = r_match.group(2)

        if d_match:
            decision = d_match.group(2)

    except Exception as e:
        print("Extraction error:", e)

    return query.strip(), reply.strip(), decision.strip()


# ==============================
# DETECT STATUS
# ==============================
def detect_status(text):
    text = text.lower()

    if "rejected" in text or "denied" in text:
        return "rejected"
    return "accepted"


# ==============================
# CREATE RECORD
# ==============================
def create_record(file_name, text):
    query, reply, decision = extract_sections(text)

    record = {
        "id": file_name,
        "query": query,
        "reply": reply,
        "decision": decision,
        "status": detect_status(text),
        "reason": "",   # fill manually later
        "raw_text": text
    }

    return record


# ==============================
# MAIN PIPELINE
# ==============================
def process_files():
    dataset = []

    files = [f for f in os.listdir(FOLDER_PATH) if f.endswith(".txt")]

    print(f"Found {len(files)} files...\n")

    for file in files:
        path = os.path.join(FOLDER_PATH, file)

        text = read_file(path)

        if not text:
            continue

        record = create_record(file, text)
        dataset.append(record)

        # DEBUG PRINT
        print("FILE:", file)
        print("QUERY PREVIEW:", record["query"][:100])
        print("STATUS:", record["status"])
        print("-" * 50)

    return dataset


# ==============================
# SAVE JSON
# ==============================
def save_json(data):
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"\nDataset saved to {OUTPUT_FILE}")
    except Exception as e:
        print("Error saving JSON:", e)

def extract_rti_block(text):
    text_lower = text.lower()

    start_keywords = ["सेवा में", "विषय", "महोदय"]
    end_keywords = ["प्रार्थिया", "दिनांक", "मो0"]

    start_index = -1
    end_index = -1

    # find start
    for kw in start_keywords:
        idx = text_lower.find(kw)
        if idx != -1:
            start_index = idx
            break

    # find end
    for kw in end_keywords:
        idx = text_lower.find(kw)
        if idx != -1:
            end_index = idx
            break

    if start_index != -1 and end_index != -1:
        return text[start_index:end_index]

    return text  # fallback


# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    dataset = process_files()
    save_json(dataset)