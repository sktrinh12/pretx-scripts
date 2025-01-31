import psycopg2
from os import getenv
from dotenv import load_dotenv
from difflib import unified_diff, SequenceMatcher
from transformers import AutoTokenizer, AutoModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


load_dotenv(override=True)
system_name1='prelude-masks'
system_name2='prelude-prod-sdpo-8251'
DB_CONFIG = {
    "dbname": getenv("DB_NAME"),
    "user": getenv("DB_USER"),
    "password": getenv("DB_PASS"),
    "host": getenv("DB_HOST"),
    "port": getenv("DB_PORT"),
}
MODEL_NAME = "allenai/scibert_scivocab_uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)
query_missing_eid = """
SELECT COALESCE(e1.exp_id, e2.exp_id) AS missing_exp_id
FROM eln_writeup_api_extract e1
FULL OUTER JOIN eln_writeup_comparison e2
ON e1.exp_id = e2.exp_id
WHERE e1.exp_id IS NULL OR e2.exp_id IS NULL
"""
query_retrieve_writeup = "SELECT write_up from eln_writeup_api_extract where system_name = '{0}' and exp_id = '{1}'"



def save_compr_to_db(
    cursor,
    exp_id,
    system_name_1,
    system_name_2,
    diff,
    match_percentage,
    is_match,
    scibert_score,
    tfidf_score,
):
    """
    Saves comparison data to the database with on conflict logic.

    Args:
        exp_id (str): Experiment ID.
        system_name_1 (str): First system name.
        system_name_2 (str): Second system name.
        diff (str): Diff content.
        match_percentage (float): Match percentage.
        is_match (bool): Whether the match percentage meets the threshold.
        scibertt_score (float): scibert model cosine similarity score.
        tfidf_score (float): tf-idf model cosine similarity score.
    """
    cursor.execute(
        """
        INSERT INTO ELN_WRITEUP_COMPARISON 
        (exp_id, system_name_1, system_name_2, diff, match_percentage, is_match, scibert_score, tfidf_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (exp_id, system_name_1, system_name_2) 
        DO UPDATE SET 
        diff = EXCLUDED.diff,
        match_percentage = EXCLUDED.match_percentage,
        is_match = EXCLUDED.is_match,
        scibert_score = EXCLUDED.scibert_score,
        tfidf_score = EXCLUDED.tfidf_score
        """,
        (exp_id, system_name_1, system_name_2, diff, match_percentage, is_match, scibert_score, tfidf_score)
    )


def get_embedding(text):
    """
    Generate embedding for a given text using SciBERT.
    """
    inputs = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=512
    )
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state[:, 0, :]  # CLS token embedding
    return embedding


def scibert_compare(text1, text2):
    """
    Compare two texts using scibert model followed by cosine similarity.

    Pre-trained BERT: Good for general understanding including scientific texts.
    SciBERT is trained on papers from the corpus of semanticscholar.org.
    Corpus size is 1.14M papers, 3.1B tokens
    """
    try:
        embedding1 = get_embedding(text1)
        embedding2 = get_embedding(text2)
        similarity = cosine_similarity(embedding1.numpy(), embedding2.numpy())
        return similarity[0][0]
    except Exception:
        return 0


def tfidf_compare(text1, text2):
    """
    Compare two texts using TF-IDF and cosine similarity.

    TF-IDF: Measures word importance in documents.
    Matrix of Vectors: Represents documents in a high-dimensional space.
    Cosine Similarity: Measures similarity between these vectors.
    """
    try:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return similarity[0][0]
    except Exception:
        return 0


def upload_compr(query):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute(query)
    exp_ids = [row[0] for row in cursor.fetchall()]
    for eid in exp_ids:
        print(eid, '\n')

        cursor.execute(query_retrieve_writeup.format(system_name1, eid))
        writeup1 = cursor.fetchone()
        writeup1 = writeup1[0] if writeup1 else "" 

        cursor.execute(query_retrieve_writeup.format(system_name2, eid))
        writeup2 = cursor.fetchone()
        writeup2 = writeup2[0] if writeup2 else ""

        diff = "\n".join(
            unified_diff(writeup1.splitlines(), writeup2.splitlines(), lineterm="")
        )
        matcher = SequenceMatcher(None, writeup1, writeup2)
        match_percentage = matcher.ratio() * 100
        is_match = match_percentage >= 95

        scibert_score = float(scibert_compare(writeup1, writeup2))
        tfidf_score = float(tfidf_compare(writeup1, writeup2))

        # print(diff)
        # print(match_percentage)
        # print(is_match)
        # print(scibert_score)
        # print(tfidf_score)

        save_compr_to_db(
            cursor,
            eid,
            system_name1,
            system_name2,
            diff,
            match_percentage,
            is_match,
            scibert_score,
            tfidf_score,
        )

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    upload_compr(query_missing_eid)
