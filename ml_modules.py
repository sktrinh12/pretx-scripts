import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MODEL_NAME = "allenai/scibert_scivocab_uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)

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
