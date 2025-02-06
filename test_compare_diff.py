import re
import argparse
from difflib import unified_diff, SequenceMatcher
import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MODEL_NAME = "allenai/scibert_scivocab_uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)

def get_embedding(text):
    inputs = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=512
    )
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state[:, 0, :]  # CLS token embedding
    return embedding


def scibert_compare(text1, text2):
    try:
        embedding1 = get_embedding(text1)
        embedding2 = get_embedding(text2)
        similarity = cosine_similarity(embedding1.numpy(), embedding2.numpy())
        return similarity[0][0]
    except Exception:
        return 0


def tfidf_compare(text1, text2):
    try:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return similarity[0][0]
    except Exception:
        return 0
def clean_text(text):
    text = (
        text.replace("\r", "")  # Remove Windows-style line endings
        .replace("\u200b", "")  # Remove zero-width space
        .replace("\u00A0", " ")  # Replace non-breaking spaces with normal spaces
        .replace("\u00AD", "")  # Remove soft hyphen
        .encode("utf-8", "ignore").decode("utf-8")  # Remove any non-UTF characters
        .strip()  # Trim leading and trailing spaces/newlines
    )
    
    # Normalize multiple spaces to a single space
    return re.sub(r"\s+", " ", text)

writeup1 = """[Set up]  To a stirred solution of nitromethane (​3.19 g, ​52.2 mmol)​{{1080:row 2}}_XXXXX_  nitromethane (​3.19 g, ​52.2 mmol)​{{1080:row 2}}_XXXXX_  in  Ammonium hydroxide (22.0 mL, 40.15 mmol) was added Boc-piperidone (​8.0 g, ​40.15 mmol)​{{1080:row 1}}_XXXXX_  . Then the reaction mixture was stirred at 25 °C under N2 atmosphere for 12 hrs.     [Monitoring]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.     [Work up]  No work up     [Purification]  No purification     [Result]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.The reaction was unsuccessful. The reaction mixture was discared.   """

writeup2 = """[Set up]  To a stirred solution of nitromethane (3.19 g, 52.2 mmol){{9:row 2}}_XXXXX_  nitromethane (3.19 g, 52.2 mmol){{9:row 2}}_XXXXX_  in  Ammonium hydroxide (22.0 mL, 40.15 mmol) was added Boc-piperidone (8.0 g, 40.15 mmol){{9:row 1}}_XXXXX_  . Then the reaction mixture was stirred at 25 °C under N2 atmosphere for 12 hrs.     [Monitoring]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.     [Work up]  No work up     [Purification]  No purification     [Result]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.The reaction was unsuccessful. The reaction mixture was discared.   """



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare and clean text for writeups.")
    parser.add_argument(
        "--clean_text", action="store_true", help="Whether to clean the text"
    )
    args = parser.parse_args()
    if args.clean_text:
        writeup1 = clean_text(writeup1)
        writeup2 = clean_text(writeup2)
    diff = "\n".join(
        unified_diff(writeup1.splitlines(), writeup2.splitlines(), lineterm="")
    )
    matcher = SequenceMatcher(None, writeup1, writeup2)
    match_percentage = matcher.ratio() * 100
    is_match = match_percentage >= 97

    scibert_score = float(scibert_compare(writeup1, writeup2))
    tfidf_score = float(tfidf_compare(writeup1, writeup2))
    table_header = f"{'Metric':<20} {'Value'}"
    separator = "-" * len(table_header)

    # Format the table rows
    table_rows = [
        f"{'Match Percentage':<20} {match_percentage:.2f}%",
        f"{'Is Match (>= 97%)':<20} {'Yes' if is_match else 'No'}",
        f"{'SciBERT Score':<20} {scibert_score:.4f}",
        f"{'TF-IDF Score':<20} {tfidf_score:.4f}"
    ]

    # Print the table
    print(table_header)
    print(separator)
    for row in table_rows:
        print(row)
