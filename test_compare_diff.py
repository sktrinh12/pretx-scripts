import re
from os import getenv
from difflib import unified_diff, SequenceMatcher
import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import psycopg2
import random
from dotenv import load_dotenv

MODEL_NAME = "allenai/scibert_scivocab_uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)
load_dotenv(override=True)

def fetch_random_writeups():
    query = """
    SELECT exp_id, diff 
    FROM eln_writeup_comparison 
    WHERE diff LIKE '%?%' 
    AND analysis_date = '2025-02-05' 
    AND diff NOT LIKE '%(? mg, ? mmol,%' 
    ORDER BY RANDOM() 
    LIMIT 15;
    """
    
    connection = psycopg2.connect(f"dbname={getenv('DB_NAME')} user={getenv('DB_USER')} password={getenv('DB_PASS')} host={getenv('DB_HOST')}")
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    connection.close()
    
    return results

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


def extract_writeups_from_diff(diff_text):
    lines = diff_text.splitlines()[3:]  # Skip the first 3 lines
    writeup1_lines = []
    writeup2_lines = []

    for line in lines:
        if line.startswith('-'):
            writeup1_lines.append(line[1:].strip())
        elif line.startswith('+'):
            writeup2_lines.append(line[1:].strip())

    writeup1 = " ".join(writeup1_lines)
    writeup2 = " ".join(writeup2_lines)

    return writeup1, writeup2


writeups = [
( """[Set up]  To a stirred solution of nitromethane (​3.19 g, ​52.2 mmol)​{{1080:row 2}}_XXXXX_  nitromethane (​3.19 g, ​52.2 mmol)​{{1080:row 2}}_XXXXX_  in  Ammonium hydroxide (22.0 mL, 40.15 mmol) was added Boc-piperidone (​8.0 g, ​40.15 mmol)​{{1080:row 1}}_XXXXX_  . Then the reaction mixture was stirred at 25 °C under N2 atmosphere for 12 hrs.     [Monitoring]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.     [Work up]  No work up     [Purification]  No purification     [Result]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.The reaction was unsuccessful. The reaction mixture was discared.   """,

"""[Set up]  To a stirred solution of nitromethane (3.19 g, 52.2 mmol){{9:row 2}}_XXXXX_  nitromethane (3.19 g, 52.2 mmol){{9:row 2}}_XXXXX_  in  Ammonium hydroxide (22.0 mL, 40.15 mmol) was added Boc-piperidone (8.0 g, 40.15 mmol){{9:row 1}}_XXXXX_  . Then the reaction mixture was stirred at 25 °C under N2 atmosphere for 12 hrs.     [Monitoring]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.     [Work up]  No work up     [Purification]  No purification     [Result]  TLC(PE/EA=1/1) showed the reactant 1 was consumed completely, many spots formed.The reaction was unsuccessful. The reaction mixture was discared.   """
),

("""a mixture of 5-bromo-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]-1,3-thiazole-2-carboxamide​​​(15​, 0.04759 mmol)​{{1063:uid 1}}_XXXXX_    and 6-(cyclopropanecarboxamido)-​4-((2-methoxy-3-(4,4,5,5-tetramethyl-1,3,2-dioxaborolan-2-yl)phenyl)amino)-N-methylpyridazine-3-carboxamide​​​(26.688​, 0.05711 mmol)​{{1063:uid 2}}_XXXXX_    Pd(dppf)Cl2​​​(6.9646​, 0.00952 mmol)​{{1063:uid 3}}_XXXXX_   and K2CO3​​​(19.731​, 0.14277 mmol)​{{1063:uid 4}}_XXXXX_    in 1,4-Dioxane (3 mL){{3:uid 1}}_XXXXX_    ,Water (0.60 mL){{3:uid 2}}_XXXXX_     was addedand nitrogen bubbled through the slurry for about 10-15min.the reaction heated  to 100°C   for 2 h.LCMS showed complete reaction of raw materials.the reaction was alowed to cool to room temperature before diuting with ea and water. the separated aqueeous phase was further extracted with ea,and the combined organic layer were then dried(na2so4) and concentrated under vacuum to give the crude produte.the crude product was purified by pre-hplc. the pre-hplc solution was freeze-dried to give 5-[3-[[6-(cyclopropanecarbonylamino)-3-(methylcarbamoyl)pyridazin-4-yl]amino]-2-methoxyphenyl]-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]-1,3-thiazole-2-carboxamide​(4​mg, ​0.00662 mmol, ​13.915 %Yield)​{{1060:uid 1}}_XXXXX_    as a yellow soild. 1H NMR (400 MHz, dmso) δ 11.36 (s, 1H), 10.99 (s, 1H), 9.21 (d, J = 5.2 Hz, 1H), 8.55 (d, J = 21.1 Hz, 1H), 8.12 (s, 1H), 7.77 (s, 1H), 7.70 (d, J = 14.5 Hz, 1H), 7.51 (d, J = 7.7 Hz, 1H), 7.41 (d, J = 14.1 Hz, 1H), 7.33 (s, 1H), 5.14 (s, 1H), 4.50 (s, 1H), 3.80 (d, J = 5.3 Hz, 3H), 3.67 (d, J = 4.2 Hz, 3H), 3.48 (s, 3H), 2.87 (d, J = 4.7 Hz, 3H), 2.11 – 2.05 (m, 1H), 0.86 – 0.78 (m, 4H).""",

"""a mixture of 5-bromo-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]-1,3-thiazole-2-carboxamide (30.0 mg, 0.1 mmol){{9:uid 1}}_XXXXX_    and 6-(cyclopropanecarboxamido)-4-((2-methoxy-3-(4,4,5,5-tetramethyl-1,3,2-dioxaborolan-2-yl)phenyl)amino)-N-methylpyridazine-3-carboxamide (53.38 mg, 0.11 mmol){{9:uid 2}}_XXXXX_    Pd(dppf)Cl2 (13.93 mg, 0.02 mmol){{9:uid 3}}_XXXXX_   and K2CO3 (39.46 mg, 0.29 mmol){{9:uid 4}}_XXXXX_    in 1,4-Dioxane (3 mL){{3:uid 1}}_XXXXX_    ,Water (0.60 mL){{3:uid 2}}_XXXXX_     was addedand nitrogen bubbled through the slurry for about 10-15min.the reaction heated  to 100 °C{{8:row 1}}_XXXXX_    for 2 h.LCMS showed complete reaction of raw materials.the reaction was alowed to cool to room temperature before diuting with ea and water. the separated aqueeous phase was further extracted with ea,and the combined organic layer were then dried(na2so4) and concentrated under vacuum to give the crude produte.the crude product was purified by pre-hplc. the pre-hplc solution was freeze-dried to give 5-[3-[[6-(cyclopropanecarbonylamino)-3-(methylcarbamoyl)pyridazin-4-yl]amino]-2-methoxyphenyl]-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]-1,3-thiazole-2-carboxamide (? mg, ? mmol, ?% yield){{2:uid 1}}_XXXXX_    as a yellow soild.  """
),
(
"""1-(cyanomethyl)-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]-4-[rac-(3R)-3-methyl-2,3-dihydro-1H-indol-4-yl]indazole-7-carboxamide (30.0 mg, 0.07 mmol){{9:uid 1}}_XXXXX_   and Methyl 4,6-dichloro-3-pyridazinecarboxylate (21.19 mg, 0.1 mmol){{9:uid 2}}_XXXXX_    dissolved in MeCN (1 mL){{3:uid 1}}_XXXXX_    Add N,N-Diisopropylethylamine (0.06 mL, 0.34 mmol){{9:uid 3}}_XXXXX_    stir at r.t. stir at r.t. small amount of rxn but not much heat to 60 C overnight ~70% stirred another 24 hours to complete reaction concentrated purified to obtain methyl 6-chloro-4-[rac-(3R)-4-[1-(cyanomethyl)-7-[methyl-[(1-methylpyrazol-4-yl)methyl]carbamoyl]indazol-4-yl]-3-methyl-2,3-dihydroindol-1-yl]pyridazine-3-carboxylate (19 mg, 0.03114 mmol, 45.627% yield){{2:uid 1}}_XXXXX_   M+1 = 610.3 found """,

"""1-(cyanomethyl)-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]-4-[rac-(3R)-3-methyl-2,3-dihydro-1H-indol-4-yl]indazole-7-carboxamide (30.0 mg, 0.07 mmol){{9:uid 1}}_XXXXX_   and Methyl 4,6-dichloro-3-pyridazinecarboxylate (21.19 mg, 0.1 mmol){{9:uid 2}}_XXXXX_    dissolved in MeCN (1 mL){{3:uid 1}}_XXXXX_    Add N,N-Diisopropylethylamine (0.06 mL, 0.34 mmol){{9:uid 3}}_XXXXX_    stir at r.t. stir at r.t. small amount of rxn but not much heat to 60 C overnight ~70% stirred another 24 hours to complete reaction concentrated purified to obtain methyl 6-chloro-4-[rac-(3R)-4-[1-(cyanomethyl)-7-[methyl-[(1-methylpyrazol-4-yl)methyl]carbamoyl]indazol-4-yl]-3-methyl-2,3-dihydroindol-1-yl]pyridazine-3-carboxylate (? mg, ? mmol, ?% yield){{2:uid 1}}_XXXXX_   M+1 = 610.3 found """
),
("""A mixture of (2S,6R)-6-[(6-bromo-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl)methyl]-N,N-dimethyloxane-2-carboxamide (​20.0 mg, ​0.05 mmol)​{{1080:uid 1}}_XXXXX_  , [3-[(2-aminopyrido[3,2-d]pyrimidin-4-yl)amino]-2-methoxyphenyl]boronic acid (​20.68 mg, ​0.07 mmol)​{{1080:uid 2}}_XXXXX_  , Xphos Pd G2 (​7.47 mg, ​0.01 mmol)​{{1080:uid 3}}_XXXXX_   and CsOAc (​18.22 mg, ​0.09 mmol)​{{1080:uid 4}}_XXXXX_  in 1,4-Dioxane (1 mL){{3:uid 1}}_XXXXX_   and Water (60 uL){{3:uid 2}}_XXXXX_  was purged with N2 for 1 mins. The reaction was stirred at 100 °C overnight. The reaction was cooled to rt and was poured into brine. The mixture was extracted by DCM/MeOH (v/v=15/1) three times.  The combined organic phase was dried over Na2SO4. After removal of solvent, the residue was purified by prep-HPLC on C18 column (30 x 250 mm, 10 μm) using mobile phase 15% to 40% MeCN/H2O (w/ 0.05% TFA) (tR = 18 min). The desired fractions were collected, concentrated and freeze-dried to give (2S,6R)-6-[[6-[3-[(2-aminopyrido[3,2-d]pyrimidin-4-yl)amino]-2-methoxyphenyl]-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl]methyl]-N,N-dimethyloxane-2-carboxamide (? mg, ? mmol, ?% yield){{2:uid 1}}_XXXXX_  as white solids. LC-MS calc. for C34H38N7O4 [MS+H]+:608.3 ;Found:608.5.""",
"""A mixture of (2S,6R)-6-[(6-bromo-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl)methyl]-N,N-dimethyloxane-2-carboxamide (20.0 mg, 0.05 mmol){{9:uid 1}}_XXXXX_  , [3-[(2-aminopyrido[3,2-d]pyrimidin-4-yl)amino]-2-methoxyphenyl]boronic acid (20.68 mg, 0.07 mmol){{9:uid 2}}_XXXXX_  , Xphos Pd G2 (7.47 mg, 0.01 mmol){{9:uid 3}}_XXXXX_   and CsOAc (18.22 mg, 0.09 mmol){{9:uid 4}}_XXXXX_  in 1,4-Dioxane (1 mL){{3:uid 1}}_XXXXX_   and Water (60 uL){{3:uid 2}}_XXXXX_  was purged with N2 for 1 mins. The reaction was stirred at 100 °C overnight. The reaction was cooled to rt and was poured into brine. The mixture was extracted by DCM/MeOH (v/v=15/1) three times.  The combined organic phase was dried over Na2SO4. After removal of solvent, the residue was purified by prep-HPLC on C18 column (30 x 250 mm, 10 μm) using mobile phase 15% to 40% MeCN/H2O (w/ 0.05% TFA) (tR = 18 min). The desired fractions were collected, concentrated and freeze-dried to give (2S,6R)-6-[[6-[3-[(2-aminopyrido[3,2-d]pyrimidin-4-yl)amino]-2-methoxyphenyl]-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl]methyl]-N,N-dimethyloxane-2-carboxamide (? mg, ? mmol, ?% yield){{2:uid 1}}_XXXXX_  as white solids. LC-MS calc. for C34H38N7O4 [MS+H]+:608.3 ;Found:608.5."""
),
("""To a 250 mL RBF was added (4-Chloro-2-pyridinyl)methanol (​20.0 mg, ​0.14 mmol)​{{1080:uid 1}}_XXXXX_   and a magnetic stir bar. The chloride was dissolved in ? (? ?){{3:uid 1}}_XXXXX_   and to this was added Pyridine 4-boronic acid (​35.96 mg, ​0.29 mmol)​{{1080:uid 2}}_XXXXX_   and ? (​?, ​? mmol)​{{1080:uid 3}}_XXXXX_  , respectively. The vessel was sealed and flushed with nitrogen gas for 20 mins, after which Potassium Carbonate (​57.76 mg, ​0.42 mmol)​{{1080:uid 4}}_XXXXX_   was added and flushed for an additional 10 mins. The reaction was heated to 95°C and allowed to stir overnight. The HPLC and LCMS showed consumption of the desired product, and formation of the desired product. The reaction will be combined with a scaled-up batch (RRJ03-65) for workup and purification. """,
"""To a 250 mL RBF was added (4-Chloro-2-pyridinyl)methanol (20.0 mg, 0.14 mmol){{9:uid 1}}_XXXXX_   and a magnetic stir bar. The chloride was dissolved in ? (? ?){{3:uid 1}}_XXXXX_   and to this was added Pyridine 4-boronic acid (35.96 mg, 0.29 mmol){{9:uid 2}}_XXXXX_   and ? (?, ? mmol){{9:uid 3}}_XXXXX_  , respectively. The vessel was sealed and flushed with nitrogen gas for 20 mins, after which Potassium Carbonate (57.76 mg, 0.42 mmol){{9:uid 4}}_XXXXX_   was added and flushed for an additional 10 mins. The reaction was heated to 95°C and allowed to stir overnight. The HPLC and LCMS showed consumption of the desired product, and formation of the desired product. The reaction will be combined with a scaled-up version for workup and purification. """
),
("""To a solution of(9S,10S)-4-chloro-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-triene (​3000.0 mg, ​12.52 mmol)​{{1080:uid 1}}_XXXXX_  in  DCE (60 mL){{3:uid 2}}_XXXXX_  was added DIPEA (​8087.9 mg, ​62.58 mmol)​{{1080:uid 3}}_XXXXX_ , followed by the addition of Boc-piperidone (​4987.28 mg, ​25.03 mmol)​{{1080:uid 2}}_XXXXX_   and sodium triacetoxyborohydride (​7957.37 mg, ​37.55 mmol)​{{1080:uid 4}}_XXXXX_ . The reaction mixture was stirred at rt for 12 h. LCMS showed that the starting material was consumed. The crude was added H2O (10 mL) and extracted with DCM (10 mL x 3). The combined organic layers were dired over Na2SO4, filtered and concentrated. The resulting soild was then suspened in 20 mL 10% ethyl acetate in heptane and stirred for 15 min. The solid was filtered and provide tert-butyl 4-[(9S,10S)-4-chloro-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-12-yl]piperidine-1-carboxylate (? g, ? mmol, ?% yield){{2:uid 1}}_XXXXX_ .""",

"""To a solution of(9S,10S)-4-chloro-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-triene (3000.0 mg, 12.52 mmol){{9:uid 1}}_XXXXX_  in  DCE (60 mL){{3:uid 2}}_XXXXX_  was added DIPEA (8087.9 mg, 62.58 mmol){{9:uid 3}}_XXXXX_ , followed by the addition of Boc-piperidone (4987.28 mg, 25.03 mmol){{9:uid 2}}_XXXXX_   and sodium triacetoxyborohydride (7957.37 mg, 37.55 mmol){{9:uid 4}}_XXXXX_ . The reaction mixture was stirred at rt for 12 h. LCMS showed that the starting material was consumed. The crude was added H2O (10 mL) and extracted with DCM (10 mL x 3). The combined organic layers were dired over Na2SO4, filtered and concentrated. The resulting soild was then suspened in 20 mL 10% ethyl acetate in heptane and stirred for 15 min. The solid was filtered and provide tert-butyl 4-[(9S,10S)-4-chloro-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-12-yl]piperidine-1-carboxylate (? g, ? mmol, ?% yield){{2:uid 1}}_XXXXX_ ."""
),
("""To a solution of 1-[[(2S)-5-(carbamoylamino)-1-[4-[[2-[(10S)-12-[[1-[(2-methylpropan-2-yl)oxycarbonyl]piperidin-4-yl]methyl]-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-4-yl]phenoxy]methyl]anilino]-1-oxopentan-2-yl]carbamoyl]cyclobutane-1-carboxylic acid (​49.0 mg, ​0.06 mmol)​{{1080:uid 1}}_XXXXX_  in DCM (1 mL){{3:uid 1}}_XXXXX_  was added TFA (​0.7 mL, ​? mmol)​{{1080:uid 2}}_XXXXX_ . The mixture was then stirred at rt for 30 min. LCMS showed that the starting material was consumed. The solvent was removed under reduced pressure. The residue was then purified by prep-HPLC using 5-50% MeCN in H2O (0.05% formic acid) to afford 1-[[(2S)-5-(carbamoylamino)-1-oxo-1-[4-[[2-[(10S)-12-(piperidin-4-ylmethyl)-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-4-yl]phenoxy]methyl]anilino]pentan-2-yl]carbamoyl]cyclobutane-1-carboxylic acid (20.6 mg, 0.02679 mmol, 47.515% yield){{2:uid 1}}_XXXXX_ .""",

"""To a solution of 1-[[(2S)-5-(carbamoylamino)-1-[4-[[2-[(10S)-12-[[1-[(2-methylpropan-2-yl)oxycarbonyl]piperidin-4-yl]methyl]-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-4-yl]phenoxy]methyl]anilino]-1-oxopentan-2-yl]carbamoyl]cyclobutane-1-carboxylic acid (49.0 mg, 0.06 mmol){{9:uid 1}}_XXXXX_  in DCM (1 mL){{3:uid 1}}_XXXXX_  was added TFA (0.7 mL, ? mmol){{9:uid 2}}_XXXXX_ . The mixture was then stirred at rt for 30 min. LCMS showed that the starting material was consumed. The solvent was removed under reduced pressure. The residue was then purified by prep-HPLC using 5-50% MeCN in H2O (0.05% formic acid) to afford 1-[[(2S)-5-(carbamoylamino)-1-oxo-1-[4-[[2-[(10S)-12-(piperidin-4-ylmethyl)-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-4-yl]phenoxy]methyl]anilino]pentan-2-yl]carbamoyl]cyclobutane-1-carboxylic acid (20.6 mg, 0.02679 mmol, 47.515% yield){{2:uid 1}}_XXXXX_ ."""
),
("""To a 250 mL RBF was added (4-Chloro-2-pyridinyl)methanol (​20.0 mg, ​0.14 mmol)​{{1080:uid 1}}_XXXXX_   and a magnetic stir bar. The chloride was dissolved in ? (? ?){{3:uid 1}}_XXXXX_   and to this was added Pyridine 4-boronic acid (​35.96 mg, ​0.29 mmol)​{{1080:uid 2}}_XXXXX_   and ? (​?, ​? mmol)​{{1080:uid 3}}_XXXXX_  , respectively. The vessel was sealed and flushed with nitrogen gas for 20 mins, after which Potassium Carbonate (​57.76 mg, ​0.42 mmol)​{{1080:uid 4}}_XXXXX_   was added and flushed for an additional 10 mins. The reaction was heated to 95°C and allowed to stir overnight. The HPLC and LCMS showed consumption of the desired product, and formation of the desired product. The reaction will be combined with a scaled-up batch (RRJ03-65) for workup and purification. """,

"""To a 250 mL RBF was added (4-Chloro-2-pyridinyl)methanol (20.0 mg, 0.14 mmol){{9:uid 1}}_XXXXX_   and a magnetic stir bar. The chloride was dissolved in ? (? ?){{3:uid 1}}_XXXXX_   and to this was added Pyridine 4-boronic acid (35.96 mg, 0.29 mmol){{9:uid 2}}_XXXXX_   and ? (?, ? mmol){{9:uid 3}}_XXXXX_  , respectively. The vessel was sealed and flushed with nitrogen gas for 20 mins, after which Potassium Carbonate (57.76 mg, 0.42 mmol){{9:uid 4}}_XXXXX_   was added and flushed for an additional 10 mins. The reaction was heated to 95°C and allowed to stir overnight. The HPLC and LCMS showed consumption of the desired product, and formation of the desired product. The reaction will be combined with a scaled-up version for workup and purification."""
),
("""A mixture of 5-bromo-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]pyridine-2-carboxamide (​30.0 mg, ​0.1 mmol)​{{1080:uid 1}}_XXXXX_   , 5-amino-6-methoxy-1H-pyridin-2-one (​27.2 mg, ​0.19 mmol)​{{1080:uid 2}}_XXXXX_   ,? (​?, ​? mmol)​{{1080:uid 3}}_XXXXX_   ,CuI (​4.62 mg, ​0.02 mmol)​{{1080:uid 4}}_XXXXX_    in Toluene (0.20 mL){{3:uid 1}}_XXXXX_    was added K2CO3 (​26.82 mg, ​0.19 mmol)​{{1080:uid 5}}_XXXXX_  . The mixture was purged with N2 for 1 min and was stirred at 120 °C for 3 h. The reaction was cooled rt. The LC-MS showed no desired product formed, while 5-amino-6-methoxy-1H-pyridin-2-one was all consumed. The reaction failed and was discarded.""",

"""A mixture of 5-bromo-N-methyl-N-[(1-methylpyrazol-4-yl)methyl]pyridine-2-carboxamide (30.0 mg, 0.1 mmol){{9:uid 1}}_XXXXX_   , 5-amino-6-methoxy-1H-pyridin-2-one (27.2 mg, 0.19 mmol){{9:uid 2}}_XXXXX_   ,? (?, ? mmol){{9:uid 3}}_XXXXX_   ,CuI (4.62 mg, 0.02 mmol){{9:uid 4}}_XXXXX_    in Toluene (0.20 mL){{3:uid 1}}_XXXXX_    was added K2CO3 (26.82 mg, 0.19 mmol){{9:uid 5}}_XXXXX_  . The mixture was purged with N2 for 1 min and was stirred at 120 °C for 3 h. The reaction was cooled rt. The LC-MS showed no desired product formed, while 5-amino-6-methoxy-1H-pyridin-2-one was all consumed. The reaction failed and was discarded."""
),
("""To a solution of 4-bromo-3-(difluoromethoxy)pyridin-2-amine (​3.0 mg, ​0.01 mmol)​{{1080:uid 2}}_XXXXX_    in THF (1.4 mL){{3:uid 1}}_XXXXX_  was added 4,6-dichloro-N-methylpyridazine-3-carboxamide (​2.84 mg, ​0.01 mmol)​{{1080:uid 1}}_XXXXX_   and LiHMDS (​6.3 mg, ​0.04 mmol)​{{1080:uid 3}}_XXXXX_     at 0 ? °C{{1100:row 1}}_XXXXX_   stirred for 15 minutes and allowed to room temperature for 30 minutes. Product 4-[[4-bromo-3-(difluoromethoxy)-2-pyridinyl]amino]-6-chloro-N-methylpyridazine-3-carboxamide (1 mg, 0.00245 mmol, 19.5% yield){{2:uid 1}}_XXXXX_  formation was  observed and the reaction mixture was used for large batch. LCMS calc. for C12H9BrClF2N5O2 [M+H]+: m/z = 410. 6; found m/z = 410.3.      """,

"""To a solution of 4-bromo-3-(difluoromethoxy)pyridin-2-amine (3.0 mg, 0.01 mmol){{9:uid 2}}_XXXXX_   in THF was added 4,6-dichloro-N-methylpyridazine-3-carboxamide (2.84 mg, 0.01 mmol){{9:uid 1}}_XXXXX_  and LiHMDS (6.3 mg, 0.04 mmol){{9:uid 3}}_XXXXX_    at 0°C stirred for 15 minutes and allowed to room temperature for 30 minutes. Product formation was not observed and the reaction mixture was discarded.       """
),
("""To a solution of 6-[[6-(3-amino-6-ethenyl-2-methoxyphenyl)-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl]methyl]-N,N-dimethylpyridine-2-carboxamide (​150.0 mg, ​0.31 mmol)​{{1080:uid 1}}_XXXXX_    in THF (3 mL){{3:uid 1}}_XXXXX_    was added Pd/C (​30.0 mg, ​? mmol)​{{1080:uid 2}}_XXXXX_   , the reaction mixture was stirred at 25 °C  for two hours under H2. THe reaction was monitored by LCMS. After completion, the mixture was filtered and the filtrate was concentrated to dryness, the residue was purified by silica gel chromatography eluted with DCM:MeOH=20:1 to give 6-[[6-(3-amino-6-ethyl-2-methoxyphenyl)-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl]methyl]-N,N-dimethylpyridine-2-carboxamide (100 mg, 0.20636 mmol, 66.389% yield){{2:uid 1}}_XXXXX_  as a light yellow solid.""",

"""To a solution of 6-[[6-(3-amino-6-ethenyl-2-methoxyphenyl)-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl]methyl]-N,N-dimethylpyridine-2-carboxamide (150.0 mg, 0.31 mmol){{9:uid 1}}_XXXXX_    in THF (3 mL){{3:uid 1}}_XXXXX_    was added Pd/C (30.0 mg, ? mmol){{9:uid 2}}_XXXXX_   , the reaction mixture was stirred at 25 °C  for two hours under H2. THe reaction was monitored by LCMS. After completion, the mixture was filtered and the filtrate was concentrated to dryness, the residue was purified by silica gel chromatography eluted with DCM:MeOH=20:1 to give 6-[[6-(3-amino-6-ethyl-2-methoxyphenyl)-1-oxospiro[3H-isoquinoline-4,1'-cyclopropane]-2-yl]methyl]-N,N-dimethylpyridine-2-carboxamide (100 mg, 0.20636 mmol, 66.389% yield){{2:uid 1}}_XXXXX_  as a light yellow solid."""
),
("""mix 6-bromo-4-iodo-2-methylpyridin-3-ol (​300.0 mg, ​0.96 mmol)​{{1080:uid 1}}_XXXXX_  , ? (​?, ​? mmol)​{{1080:uid 2}}_XXXXX_  , in """,
"""mix 6-bromo-4-iodo-2-methylpyridin-3-ol (300.0 mg, 0.96 mmol){{9:uid 1}}_XXXXX_  , ? (?, ? mmol){{9:uid 2}}_XXXXX_  , in """
),
("""To a solution of 3-chloro-4-ethenyl-2-methoxyaniline (​20.0 mg, ​0.11 mmol)​{{1080:uid 5}}_XXXXX_   in THF (1 mL){{3:uid 1}}_XXXXX_   was added Pd/C (​4.0 mg, ​? mmol)​{{1080:uid 6}}_XXXXX_ , the reaction mixture was stirred at 25 °C{{1100:row 1}}_XXXXX_  for four hours under H2. The reaction was monitored by LCMS and no desired mass found. The reaction was failed and discarded.""",

"""To a solution of 3-chloro-4-ethenyl-2-methoxyaniline (20.0 mg, 0.11 mmol){{9:uid 5}}_XXXXX_   in THF (1 mL){{3:uid 1}}_XXXXX_   was added Pd/C (4.0 mg, ? mmol){{9:uid 6}}_XXXXX_ , the reaction mixture was stirred at 25 °C{{8:row 1}}_XXXXX_  for four hours under H2. The reaction was monitored by LCMS and no desired mass found. The reaction was failed and discarded."""
),
("""A solution of tert-butyl 4-[(9S,10S)-4-chloro-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-12-yl]piperidine-1-carboxylate (​2250.0 mg, ​5.32 mmol)​{{1080:uid 1}}_XXXXX_  ,2-(methoxymethoxy)phenylboronic acid (​1936.14 mg, ​10.64 mmol)​{{1080:uid 2}}_XXXXX_  , [2-(2-aminophenyl)phenyl]-chloropalladium;dicyclohexyl-[2-[2,4,6-tri(propan-2-yl)phenyl]phenyl]phosphane (​209.28 mg, ​0.27 mmol)​{{1080:uid 4}}_XXXXX_  and Potassium phosphate tribasic (​3387.45 mg, ​15.96 mmol)​{{1080:uid 3}}_XXXXX_  in 1,4-Dioxane (20 mL){{3:uid 1}}_XXXXX_  and Water (6.67 mL){{3:uid 2}}_XXXXX_  was heated to  100 °C  under N2 atmosphere for 30 min.LC-MS confirmed the consumption of the SM and the formation of the desired product. The mixture was cooled to rt. concentrated and partitioned with DCM (30 mL) and water (30 mL),, the organic phase was separated, and the aqueous phase was extracted with DCM (3 x 100mL). The combined organic phases were dried over Na2SO4, concentrated and purified by flash column chromatography (0%-20% MeOH/DCM) to give tert-butyl 4-[(9S,10S)-4-[2-(methoxymethoxy)phenyl]-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-12-yl]piperidine-1-carboxylate (2.18 g, 4.155 mmol, 78.106% yield){{2:uid 1}}_XXXXX_  , a brown solid.""",
"""A solution of tert-butyl 4-[(9S,10S)-4-chloro-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-12-yl]piperidine-1-carboxylate (2250.0 mg, 5.32 mmol){{9:uid 1}}_XXXXX_  ,2-(methoxymethoxy)phenylboronic acid (1936.14 mg, 10.64 mmol){{9:uid 2}}_XXXXX_  , [2-(2-aminophenyl)phenyl]-chloropalladium;dicyclohexyl-[2-[2,4,6-tri(propan-2-yl)phenyl]phenyl]phosphane (209.28 mg, 0.27 mmol){{9:uid 4}}_XXXXX_  and Potassium phosphate tribasic (3387.45 mg, 15.96 mmol){{9:uid 3}}_XXXXX_  in 1,4-Dioxane (20 mL){{3:uid 1}}_XXXXX_  and Water (6.67 mL){{3:uid 2}}_XXXXX_  was heated to  100 °C  under N2 atmosphere for 40 in.LC-MS confirmed the consumption of the SM and the formation of the desired product. The mixture was cooled to rt. concentrated and partitioned with DCM (30 mL) and water (30 mL),, the organic phase was separated, and the aqueous phase was extracted with DCM (3 x 100mL). The combined organic phases were dried over Na2SO4, concentrated and purified by flash column chromatography (0%-20% MeOH/DCM) to give tert-butyl 4-[(9S,10S)-4-[2-(methoxymethoxy)phenyl]-9-methyl-1,5,6,8,12-pentazatricyclo[8.4.0.02,7]tetradeca-2,4,6-trien-12-yl]piperidine-1-carboxylate (? g, 1.8297 mmol, 34.396% yield){{2:uid 1}}_XXXXX_  , a brown solid."""
),
]



if __name__ == "__main__":
    writeups = fetch_random_writeups()
    print(writeups)
    results = []
    for index, (exp_id, diff_text) in enumerate(writeups, start=1):
        data = {'index': index, 'exp_id': exp_id}
        writeup1, writeup2 = extract_writeups_from_diff(diff_text)
        for mode in ['raw', 'cleaned']:
            if mode =='cleaned':
                data[f'writeup1_{mode}'] = clean_text(writeup1)
                data[f'writeup2_{mode}'] = clean_text(writeup2)
            else:
                data[f'writeup1_{mode}'] = writeup1
                data[f'writeup2_{mode}'] = writeup1

            matcher = SequenceMatcher(None, data[f'writeup1_{mode}'], data[f'writeup2_{mode}'])
            match_percentage = matcher.ratio() * 100
            is_match = match_percentage >= 97

            scibert_score = float(scibert_compare(data[f'writeup1_{mode}'], data[f'writeup2_{mode}']))
            tfidf_score = float(tfidf_compare(data[f'writeup1_{mode}'], data[f'writeup2_{mode}']))

            data[f'match_percentage_{mode}'] = match_percentage
            data[f'is_match_{mode}'] = "Yes" if is_match else "No"
            data[f'scibert_score_{mode}'] = scibert_score
            data[f'tfidf_score_{mode}'] = tfidf_score

        results.append(data)

    for data in results:
        table_header = f"{'Index':<5} {'Exp ID':<20} {'With Pre-Processing':<20} {'Without Pre-Processing'}"
        separator = "-" * len(table_header)

        table_rows = [
            f"{data['index']:<5} {data['exp_id']:<10} {'Match Percentage':<20} {data['match_percentage_cleaned']:.2f}%{' ' * 10}{data['match_percentage_raw']:.2f}%",
            f"{data['index']:<5} {data['exp_id']:<10} {'Is Match (>= 97%)':<20} {data['is_match_cleaned']:<20} {data['is_match_raw']}",
            f"{data['index']:<5} {data['exp_id']:<10} {'SciBERT Score':<20} {data['scibert_score_cleaned']:.4f}{' ' * 10}{data['scibert_score_raw']:.4f}",
            f"{data['index']:<5} {data['exp_id']:<10} {'TF-IDF Score':<20} {data['tfidf_score_cleaned']:.4f}{' ' * 10}{data['tfidf_score_raw']:.4f}"
        ]

        print(table_header)
        print(separator)
        for row in table_rows:
            print(row)
        print("\n")
