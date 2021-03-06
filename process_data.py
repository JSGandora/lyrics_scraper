#!/usr/bin/env python
# coding: utf-8

# In[8]:


# SETUP IMPORTS

from os.path import join
from os import listdir
import pandas as pd
import numpy as np
import json
import nltk
import networkx as nx
from collections import Counter
from multiprocessing import Pool
import time
from sklearn.feature_extraction.text import TfidfVectorizer

GENERATE_DATA = False
GENRES = ["blues", "gospel", "rap", "country", "rock"]
DATA_DIR = "/n/fs/guoweis-18iw/get_data/lyrics"
ALL_DATA_FN = "all.data"

if GENERATE_DATA:
    # Read data
    df = pd.DataFrame(np.nan, index=[], columns=['artist', 'title', 'album', 'year', 'lyrics', 'genre'])

    ct = 0
    for genre in GENRES:
        genre_dir = join(DATA_DIR, genre)
        fns = listdir(genre_dir)
        for i, fn in enumerate(fns):
            if i % 10 == 0:
                print("Done with " + str(i) + " of " + str(len(fns)) + " files.")
            fp = join(genre_dir, fn)
            data_str = open(fp).read()
            data = json.loads(data_str)
            songs_data = data["songs"]
            for j, song in enumerate(songs_data):
                df.loc[ct, "genre"] = genre
                for key in song.keys():
                    if key == "raw" or key == "image":
                        continue
                    df.loc[ct, key] = song[key]
                ct += 1
        df.to_pickle(genre + ".data")


# In[2]:


# Extract features
from nltk.stem.snowball import SnowballStemmer
stemmer = SnowballStemmer("english")

ACCEPTED_CHARS = set('abcdefghijklmnopqrstuvwxyz \'\n')
def lyrics_strip(lyrics):
    verse = lyrics.strip().lower()
    verse = ''.join(filter(ACCEPTED_CHARS.__contains__, verse))
    return verse

def lyrics_to_linelist(lyrics):
    lyrics = lyrics.split("\n")
    lyrics = [line.split() for line in lyrics]
    return lyrics

def linelist_to_wordlist(lines):
    return [word for line in lines for word in line]

def lyrics_to_wordlist(lyrics):
    return lyrics.split()

def avg_word_len(lyrics):
    wordlist = lyrics_to_wordlist(lyrics)
    lengths = [len(word) for word in wordlist]
    return sum(lengths)/len(lengths)

def avg_line_len(lyrics):
    linelist = lyrics_to_linelist(lyrics)
    lengths = [len(line) for line in linelist]
    return sum(lengths)/len(lengths)

def total_num_lines(lyrics):
    linelist = lyrics_to_linelist(lyrics)
    return len(linelist)

def total_num_words(lyrics):
    wordlist = lyrics_to_wordlist(lyrics)
    return len(wordlist)

def num_contractions(lyrics):
    wordlist = lyrics_to_wordlist(lyrics)
    return sum([1 if "\'" in word else 0 for word in wordlist])

def contraction_density(lyrics):
    wordlist = lyrics_to_wordlist(lyrics)
    return sum([1 if "\'" in word else 0 for word in wordlist])/len(wordlist)

def vocab(lyrics):
    wordlist = lyrics_to_wordlist(lyrics)
    wordlist = [stemmer.stem(word) for word in wordlist]
    return set(wordlist)

def vocab_size(lyrics):
    return len(vocab(lyrics))

def vocab_cts(lyrics):
    wordlist = lyrics_to_wordlist(lyrics)
    wordlist = [stemmer.stem(word) for word in wordlist]
    return dict(Counter(wordlist))

lyrics = "I love you\nLike no other"
linelist = lyrics_to_linelist(lyrics)
wordlist = linelist_to_wordlist(linelist)


# In[3]:


# Extract rhyme features
### Adapted from https://github.com/edwadli/rapgraph/blob/master/src/rapper.py
from nltk.corpus import cmudict
transcr = cmudict.dict()
_NULL_ = '_NULL_'
phs = 'AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH    IY JH K L M N NG OW OY P R S SH T TH UH UW V W Y Z'.split()
phs_vowels = set('AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW'.split())

def phonemes(words):
    words = [word.lower() for word in words]
    phonemes = {}
    for word in words:
        # get possible pronunciations from dict
        possible_pronunciations =  transcr.get(word, [[_NULL_]])
        if word not in transcr:
            # TODO: generate a guess on the pronunciation
            pass
        # strip out emphasis on vowels
        for pronunciation in possible_pronunciations:
            for i in range(len(pronunciation)):
                pronunciation[i] = ''.join(c for c in pronunciation[i] if not c.isdigit())
        # remove repeats
        possible_pronunciations = list(set([tuple(p) for p in possible_pronunciations]))
        phonemes[word] = possible_pronunciations
    return phonemes

def phonemeSimilarity(ph_a, ph_b):
    # Heuristic phoneme rhyming similarity in range [0, 1]    
    relative_score = 0.
    if ph_a == _NULL_ or ph_b == _NULL_:
        return 0.
    if ph_a == ph_b:
        # rhyme
        relative_score = 1.
    elif ph_a in phs_vowels:
        if ph_b in phs_vowels:
            # both vowels, likely to rhyme
            relative_score = 0.3
    elif ph_b not in phs_vowels:
        # both consonants, could help rhyme
        relative_score = 0.05
    return relative_score

def alignPhonemeSequences(a_seq, b_seq):
    # Smith-Waterman alignment with custom phoneme similarity scoring
    GAP_PENALTY = -1.
    MIN_SCORE = -10.
    MAX_SCORE = 10.
    score_range = MAX_SCORE - MIN_SCORE
    width = len(a_seq)+1
    height = len(b_seq)+1
    H = [[0] * width for i in range(height)]
    # Run the DP alg
    for row in range(1,height):
        for col in range(1,width):
            relative_score = phonemeSimilarity(a_seq[col-1], b_seq[row-1])
            align = H[row-1][col-1] + relative_score * score_range + MIN_SCORE
            deletion = H[row-1][col] + GAP_PENALTY
            insertion = H[row][col-1] + GAP_PENALTY
            H[row][col] = max(0, align, deletion, insertion)
    # extract the solution
    # find max value in H
    max_value = 0
    max_row = None
    max_col = None
    for row in range(height):
        for col in range(width):
            if H[row][col] >= max_value:
                max_value = H[row][col]
                max_row = row
                max_col = col
    return max_value, H

def end_rhyme_score(a_seq, b_seq):
    max_val, h = alignPhonemeSequences(a_seq, b_seq)
    return h[-1][-1]

def aligned_rhyme_score(a_seq, b_seq):
    max_val, h = alignPhonemeSequences(a_seq, b_seq)
    return max_val

def aligned_matrix(a_seq, b_seq):
    max_val, h = alignPhonemeSequences(a_seq, b_seq)
    return h


# In[4]:


# Get line adjacency graph
def get_rhyme_adj_graph(lyrics, thresh = 0):
    linelist = lyrics_to_linelist(lyrics)
    wordlist = lyrics_to_wordlist(lyrics)
    get_phonemes = phonemes(wordlist)
    num_wrds = len(wordlist)
    graph = np.zeros((num_wrds, num_wrds))
    i = 0
    for j, line in enumerate(linelist):
        full_phrase = line
        if j < len(linelist)-1:
            full_phrase = linelist[j] + linelist[j+1]
        for k, word in enumerate(line):
            word1 = word
            for l, word2 in enumerate(full_phrase[k+1:]):
                ph1 = get_phonemes[word1]
                ph2 = get_phonemes[word2]
                w = 0
                for p1 in ph1:
                    for p2 in ph2:
                        w = max(w, aligned_rhyme_score(p1, p2))
                graph[i, i+1+l] = w
                graph[i+1+l, i] = w
            i += 1
    graph[graph <= thresh] = 0
    return graph

def edge_density(rhyme_graph, weighted=False):
    if weighted:
        return np.sum(rhyme_graph)/(np.size(rhyme_graph) - rhyme_graph.shape[0])
    return np.count_nonzero(rhyme_graph)/(np.size(rhyme_graph) - rhyme_graph.shape[0])

def edge_var(rhyme_graph):
    return np.var(rhyme_graph[rhyme_graph > 0])

def degree_var(rhyme_graph, weighted=False):
    if weighted:
        degrees = [np.sum(vertex) for vertex in rhyme_graph]
    else:
        degrees = [np.count_nonzero(vertex) for vertex in rhyme_graph]
    return np.var(degrees)

def degree_avg(rhyme_graph, weighted=False):
    if weighted:
        return np.sum(rhyme_graph)/len(rhyme_graph)
    return np.count_nonzero(rhyme_graph)/len(rhyme_graph)

def comp_size_avg(rhyme_graph):
    return len(rhyme_graph)/nx.number_connected_components(nx.from_numpy_matrix(rhyme_graph))

def num_comp(rhyme_graph):
    return nx.number_connected_components(nx.from_numpy_matrix(rhyme_graph))


# In[5]:


# SPLIT TRAINING, TEST, AND VALIDATION SET
def split_train_test(df):
    df["randn"] = np.random.uniform(0, 1, df.shape[0])
    def split_name(x):
        if x > 0.8:
            return "test"
        if x > 0.6:
            return "val"
        else:
            return "train"
    
    df["data_split"] = np.array([split_name(n) for n in df["randn"]])
    return df

SPLIT_DATA = False
if SPLIT_DATA:
    # Preprocess Dataframe
    df = pd.read_pickle(ALL_DATA_FN)

    if 'lyrics_stripped' not in df.columns:
        df["lyrics_stripped"] = [lyrics_strip(lyric) for lyric in df["lyrics"]]

    df = split_train_test(df)
    df.to_pickle(ALL_DATA_FN)

    # Get label distributions of training and test sets
    def get_distribution(labels):
        ct = {}
        for lab in labels:
            if lab in ct:
                ct[lab] += 1
            else:
                ct[lab] = 1

        return ct

    # Calculate dataset statistics
    print("Entire Dataset")
    print(get_distribution(df["genre"]))
    print("Training Set")
    print(get_distribution(df.query("data_split == 'train'")["genre"]))
    print("Test Set")
    print(get_distribution(df.query("data_split == 'test'")["genre"]))


# In[ ]:


def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        print('{:s} function took {:.3f} ms'.format(f.__name__, (time2-time1)*1000.0))
        return ret
    return wrap

# Temporary Functions
def get_rhyme_adj_graph_thresholded(x):
    return get_rhyme_adj_graph(x, 10.0)

def edge_density_weighted(x):
    return edge_density(x, True)

def degree_avg_weighted(x):
    return degree_avg(x, True)

def degree_var_weighted(x):
    return degree_var(x, True)

def edge_density_fromlyrics(x):
    return edge_density(get_rhyme_adj_graph(x, 10.0))

def edge_var_fromlyrics(x):
    return edge_var(get_rhyme_adj_graph(x, 10.0))

def degree_var_fromlyrics(x):
    return degree_var(get_rhyme_adj_graph(x, 10.0))

def degree_avg_fromlyrics(x):
    return degree_avg(get_rhyme_adj_graph(x, 10.0))

def comp_size_avg_fromlyrics(x):
    return comp_size_avg(get_rhyme_adj_graph(x, 10.0))

def edge_density_weighted_fromlyrics(x):
    return edge_density(get_rhyme_adj_graph(x, 10.0), True)

def degree_var_weighted_fromlyrics(x):
    return degree_var(get_rhyme_adj_graph(x, 10.0), True)

def degree_avg_weighted_fromlyrics(x):
    return degree_avg(get_rhyme_adj_graph(x, 10.0), True)
    
# Extract independent features
@timing
def extract_oneoff_feats(df, recalculate=False):
    if 'n_wrds' not in df.columns or recalculate:
        print("Calculating total number of words")
        df["n_wrds"] = df["lyrics_stripped"].apply(total_num_words)
        # Only keep songs with at least one word
        df = df.query("n_wrds > 10").copy()
        print("Calculated total number of words")
        df.to_pickle(ALL_DATA_FN)
        return df

    if 'avg_wrd_len' not in df.columns or recalculate: 
        print("Calculating the average word length")
        df['avg_wrd_len'] = df["lyrics_stripped"].apply(avg_word_len)
        print("Calculated the average word length")
        df.to_pickle(ALL_DATA_FN)
        return df

    if 'n_lines' not in df.columns or recalculate:
        print("Calculating the total number of lines")
        df['n_lines'] = df["lyrics_stripped"].apply(total_num_lines)
        print("Calculated the total number of lines")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "avg_line_len" not in df.columns or recalculate:
        print("Calculating the average line length")
        df["avg_line_len"] = df["lyrics_stripped"].apply(avg_line_len)
        print("Calculated the average line length")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "n_contractions" not in df.columns or recalculate:
        print("Calculating the number of contractions")
        df["n_contractions"] = df["lyrics_stripped"].apply(num_contractions)
        print("Calculated the number of contractions")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "contraction_density" not in df.columns or recalculate:
        print("Calculating the density of contractions")
        df["contraction_density"] = df["lyrics_stripped"].apply(contraction_density)
        print("Calculated the density of contractions")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "vocab_size" not in df.columns or recalculate:
        print("Calculating the size of the vocabulary")
        with Pool(processes=30) as pool:
            df["vocab_size"] = pool.map(vocab_size, df["lyrics_stripped"])
        print("Calculated the size of the vocabulary")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "vocab_cts" not in df.columns or recalculate:
        print("Calculating the counts of the vocabulary")
        with Pool(processes=30) as pool:
            df["vocab_cts"] = pool.map(vocab_cts, df["lyrics_stripped"])
        print("Calculated the counts of the vocabulary")
        df.to_pickle(ALL_DATA_FN)
        return df

#     if "rhyme_graph" not in df.columns or recalculate:
#         df["rhyme_graph"] = df["lyrics_stripped"].apply(get_rhyme_adj_graph_thresholded)
#         print("Calculated the rhyme graph")
#         df.to_pickle(ALL_DATA_FN)
#         return df

    if "edge_density" not in df.columns or recalculate:
        print("Calculating the edge density")
        with Pool(processes=30) as pool:
            df["edge_density"] = pool.map(edge_density_fromlyrics, df["lyrics_stripped"])
        print("Calculated the edge density")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "edge_density_weighted" not in df.columns or recalculate:
        print("Calculating the weighted edge density")
        with Pool(processes=30) as pool:
            df["edge_density_weighted"] = pool.map(edge_density_weighted_fromlyrics, df["lyrics_stripped"])
        print("Calculated the weighted edge density")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "edge_weight_var" not in df.columns or recalculate:
        print("Calculating the edge weight variance")
        with Pool(processes=30) as pool:
            df["edge_weight_var"] = pool.map(edge_var_fromlyrics, df["lyrics_stripped"])
        print("Calculated the edge weight variance")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "degree_var" not in df.columns or recalculate:
        print("Calculating the variance of the vertex degrees")
        with Pool(processes=30) as pool:
            df["degree_var"] = pool.map(degree_var_fromlyrics, df["lyrics_stripped"])
        print("Calculated the variance of the vertex degrees")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "degree_var_weighted" not in df.columns or recalculate:
        print("Calculating the variance of the weighted vertex degrees")
        with Pool(processes=30) as pool:
            df["degree_var_weighted"] = pool.map(degree_var_weighted_fromlyrics, df["lyrics_stripped"])
        print("Calculated the variance of the weighted vertex degrees")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "degree_avg" not in df.columns or recalculate:
        print("Calculating the average vertex degree")
        with Pool(processes=30) as pool:
            df["degree_avg"] = pool.map(degree_avg_fromlyrics, df["lyrics_stripped"])
        print("Calculated the average vertex degree")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "degree_avg_weighted" not in df.columns or recalculate:
        print("Calculating the average weighted vertex degree")
        with Pool(processes=30) as pool:
            df["degree_avg_weighted"] = pool.map(degree_avg_weighted_fromlyrics, df["lyrics_stripped"])
        print("Calculated the average weighted vertex degree")
        df.to_pickle(ALL_DATA_FN)
        return df

    if "comp_size_avg" not in df.columns or recalculate:
        print("Calculating the average size of a connected component")
        with Pool(processes=30) as pool:
            df["comp_size_avg"] = pool.map(comp_size_avg_fromlyrics, df["lyrics_stripped"])
        print("Calculated the average size of a connected component")
        df.to_pickle(ALL_DATA_FN)
        return df

    return df

df = pd.read_pickle(ALL_DATA_FN)
while True:
    df = extract_oneoff_feats(df)


# In[25]:


# Calculate tf-idf data
def get_topk(df, k=100):
    df_train = df.query("data_split == 'train'").copy()
    df_test = df.query("data_split == 'test'").copy()
    df_val = df.query("data_split == 'val'").copy()
    
    vectorizer = TfidfVectorizer(stop_words = "english", max_df = 0.9)
    tokenizer = vectorizer.build_tokenizer()
    
    corpus = []
    for genre in GENRES:
        df_genre = df_train.query("genre == '%s'" % genre).copy()
        tokenized = df_genre["lyrics_stripped"].apply(lambda x: " ".join(list(set(tokenizer(x)))))
        corpus.append(" ".join(tokenized))
    
    X = vectorizer.fit_transform(corpus)
    top_k_wrds = []
    for i, genre in enumerate(GENRES):
        words_freq = [(word, X[i, idx]) for word, idx in vectorizer.vocabulary_.items()]
        words_freq = sorted(words_freq, key = lambda x: x[1], reverse=True)
        words = [pair[0] for pair in words_freq]
        top_k_wrds += words[:k]
    top_k_wrds = list(set(top_k_wrds))
    return top_k_wrds

def get_tfidf(df, vocab):
    df_train = df.query("data_split == 'train'").copy()
    df_test = df.query("data_split == 'test'").copy()
    df_val = df.query("data_split == 'val'").copy()
    
    vectorizer = TfidfVectorizer(vocabulary=vocab)
    corpus_train = df_train["lyrics_stripped"]
    X_train = vectorizer.fit_transform(corpus_train)
    
    X_all = vectorizer.transform(df["lyrics_stripped"])
    return X_all

def calculate_tfidf(df):
    vocab = get_topk(df)
    x = get_tfidf(df, vocab)
    df["topk"] = x
    df.to_pickle(ALL_DATA_FN)
    
CALCULATE_TFIDF = False
if CALCULATE_TFIDF:
    df = pd.read_pickle(ALL_DATA_FN)
    calculate_tfidf(df)


# In[26]:





# In[43]:





# In[ ]:




