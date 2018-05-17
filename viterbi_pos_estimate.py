# for POS estimation
import numpy as np
import nltk

# for printing progress-bar
import time
import sys


# remove sentence boundaries from raw bigrams made by nltk
def make_tagged_word_bigrams(sents):
    return filter(lambda x: x != (('_end', '</s>'), ('start_', '<s>')),
                  nltk.bigrams(make_sent_words(sents)))

# remake word list
def make_sent_words(sents):
    words = []
    for i in range(len(sents)):
        words += mod_sent(sents[i])
    return words

# add dummy tokens (for beginning and ending) to each sentence
def mod_sent(tokens):
    tokens.insert(0, ('start_', '<s>'))
    tokens.append(('_end', '</s>'))
    return tokens


# p(w|t)
# word emission probability with add-α smoothing
def p_t_w(t_w, tag, word, alpha=0.01):
    return (t_w[tag][word] + alpha ) / (t_w[tag].N() + alpha * t_w[tag].B())


# p(t_i|t_i-1)
# POS transition probability with add-α smoothing
def p_t_t(t_t, tag1, tag2, alpha=0.01):
    return (t_t[tag1][tag2] + alpha ) / (t_t[tag1].N() + alpha * t_t[tag1].B())


# helper method of viterbi()
def calc_table(S, T, V, i, j, pos_tags, tokens, t_w, t_t):
    ## constant 'prec_adjust' is for preventing underflow of probability calculation
    prec_adjust = 100
    max_prob = 0.0
    max_k = 0
    for k in range(S):
        prob = V[k][i-1] * p_t_w(t_w, pos_tags[j], tokens[i]) * p_t_t(t_t, pos_tags[k], pos_tags[j]) * prec_adjust
        if prob > max_prob:
            max_prob, max_k = prob, k
    return max_prob, max_k


def viterbi(sentence, pos_tags, t_w, t_t):
    
    tokens = nltk.word_tokenize(sentence)   # ['Time', 'flies', 'like', 'an', 'arrow', '.']
    tokens.insert(0, '<s>')                 # ['<s>', 'Time', 'flies', 'like', 'an', 'arrow', '.']
    
    S = len(pos_tags)                       # S: number of POS (47)
    T = len(tokens)                         # T: number of tokens
    V = np.zeros((S, T), dtype=np.float32)  # V: probability table
    B = np.zeros((S, T), dtype=int)         # B: back-pointer table
    
    ## p(<s>)=1.0 : first product in cumulative probability
    for j in range(S):
        V[j,0] = 1.0

    ## induction
    for i in range(1, T):
        for j in range(S):
            V[j][i], B[j][i] = calc_table(S, T, V, i, j, pos_tags, tokens, t_w, t_t)

    ## termination and path-readout
    X = np.zeros((T), dtype=int)
    max_prob = 0.0
    for j in range(S):
        if V[j][T-1] > max_prob:
            max_prob = V[j][T-1]
            X[T-1] = j
    for i in range(T-2, -1, -1):
        X[i] = B[X[i+1]][i+1]

    # convert POS-index to POS-tag
    pos_seq = []
    for pos_idx in X:
        pos_seq.append(pos_tags[pos_idx])

    return max_prob, list(zip(tokens[1:], pos_seq[1:]))


def setup_progbar(width):
    sys.stdout.write("[%s]" % (" " * width))
    sys.stdout.flush()
    sys.stdout.write("\b" * (width+1))

def update_progbar():
    sys.stdout.write("=")
    sys.stdout.flush()


def calc_accuracy(tagged_sents, pos_tags, t_w, t_t):

    ## setup progress bar
    test_size = len(tagged_sents)
    max_width = 40
    progbar_width = test_size if test_size < max_width else max_width 
    prog_step = test_size / progbar_width
    setup_progbar(progbar_width)

    ## create test sentences from 'tagged_sents_test'
    test_sent_list = []
    ans_tagged_sents = []
    for each_tagged_sent in tagged_sents:
        sentence = []
        for each_tagged_word in each_tagged_sent:
            sentence.append(each_tagged_word[0])
        test_sent_list.append(" ".join(str(x) for x in sentence))
        ans_tagged_sents.append(each_tagged_sent)

    ## evaluate created HMM
    prog_cnt = 0
    total_cnt = 0
    accuracy_cnt = 0
    correct_sent_count = 0
    for sentence, answer in zip(test_sent_list, ans_tagged_sents):
        token_pos = viterbi(sentence, pos_tags, t_w, t_t)[1]
        all_pos_matched = True
        for pred, ans in zip(token_pos, answer):
            if (pred[1] == ans[1]):
                accuracy_cnt += 1
            else:
                all_pos_matched = False
            total_cnt += 1
        if all_pos_matched is True:
            correct_sent_count += 1

        # update progress bar
        prog_cnt += 1
        if (prog_cnt >= prog_step):
            update_progbar()
            prog_cnt = 0

    accuracy_token = accuracy_cnt / total_cnt
    accuracy_sent = correct_sent_count / len(ans_tagged_sents)
    return accuracy_token, accuracy_sent


def main():
    print("+----------------------------------------+")
    
    ## loading of data may consume up to several seconds
    print("loading POS tagsets ...")
    
    ## load POS tagset from Penn Treebank
    tagged_sents = nltk.corpus.treebank.tagged_sents()

    ## split tagset to train and test
    train_ratio = 0.8
    train_size = int(len(tagged_sents) * train_ratio)
    tagged_sents_train = tagged_sents[:train_size]
    tagged_sents_test = tagged_sents[train_size:]

    tagged_word_bigrams = list(make_tagged_word_bigrams(tagged_sents_train))

    ## word emission count (t_w[tag][word])
    t_w = nltk.ConditionalFreqDist([(d[0][1], d[0][0]) for d in tagged_word_bigrams])

    ## state transition count (t_t[t1][t2])
    t_t = nltk.ConditionalFreqDist([(d[0][1], d[1][1]) for d in tagged_word_bigrams])

    ## a list of possible pos tags (</s> is not included)
    pos_tags = list(t_t.keys())

    print(" ---------------------------------------- ")

    ## sentence to evaluate POS
    sentence = input("sentence: ")
    prob, token_pos = viterbi(sentence, pos_tags, t_w, t_t)

    ## show results
    print("probability:", prob)
    for each_token_pos in token_pos:
        print(each_token_pos)

    ## test model precision (may consume several minutes to compute)
    print(" ---------------------------------------- ")
    print("measuring precision of model ...")
    prec_token, prec_sent = calc_accuracy(tagged_sents_test, pos_tags, t_w, t_t)
    print("\nmodel precision")
    print("token based accuracy   :", prec_token)
    print("sentence based accuracy:", prec_sent)
    print("+----------------------------------------+")

if __name__ == '__main__':
    main()
