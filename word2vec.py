#!/usr/bin/env python

import numpy as np
import random

from utils.gradcheck import gradcheck_naive, grad_tests_softmax, grad_tests_negsamp
from utils.utils import normalizeRows, softmax


def sigmoid(x):
    """
    Compute the sigmoid function for the input here.
    Arguments:
    x -- A scalar or numpy array.
    Return:
    s -- sigmoid(x)
    """

    ### YOUR CODE HERE (~1 Line)
    s = 1/(1+np.exp(-x))
    # To make it more numerically stable, denominator and numerator should be in the same scale:
    #    np.where(x >= 0, 1/(1+np.exp(-x)), np.exp(x)/(np.exp(x)+1))
    ### END YOUR CODE

    return s


def naiveSoftmaxLossAndGradient(
    centerWordVec,
    outsideWordIdx,
    outsideVectors,
    dataset
):
    """ Naive Softmax loss & gradient function for word2vec models

    Implement the naive softmax loss and gradients between a center word's 
    embedding and an outside word's embedding. This will be the building block
    for our word2vec models.

    Arguments:
    centerWordVec -- numpy ndarray, center word's embedding
                    in shape (word vector length, )
                    (v_c in the pdf handout)
    outsideWordIdx -- integer, the index of the outside word
                    (o of u_o in the pdf handout)
    outsideVectors -- outside vectors is
                    in shape (num words in vocab, word vector length) 
                    for all words in vocab (U in the pdf handout)
    dataset -- needed for negative sampling, unused here.

    Return:
    loss -- naive softmax loss
    gradCenterVec -- the gradient with respect to the center word vector
                     in shape (word vector length, )
                     (dJ / dv_c in the pdf handout)
    gradOutsideVecs -- the gradient with respect to all the outside word vectors
                    in shape (num words in vocab, word vector length) 
                    (dJ / dU)
    """

    ### YOUR CODE HERE (~6-8 Lines)

    ### Please use the provided softmax function (imported earlier in this file)
    ### This numerically stable implementation helps you avoid issues pertaining
    ### to integer overflow. 
    product = np.dot(outsideVectors, centerWordVec) # (vocab size, word vec size) * (word vec size,) = (vocab size,)
    # or centerWordVec @ outsideVectors.T  # (vocab size,)
    
    y_hat = softmax(product)  # (vocab size, 1)

    # sanity checks
    # debug_softmax_result = np.exp(centerWordVec @ outsideVectors[outsideWordIdx, :].T) / z
    # diff = np.abs(softmax_result - debug_softmax_result)
    # if (diff > 1e-6):
    #     print("Unexpected: softmax_result=%s, debug_softmax_result=%s, diff=%s" % (softmax_result, debug_softmax_result, diff))
    loss = -np.log(y_hat[outsideWordIdx])
    
    gradCenterVec = (
        -outsideVectors[outsideWordIdx, :] +
        # I initially wrote: (np.sum(y_hat * outsideVectors.T, axis=1).T)  # broadcasting
        # But this is in fact just a column-wise dot product between each of the row vectors in outsideVectors
        # with the y_hat column vector.
        np.dot(y_hat, outsideVectors)  # (vocab size, 1) * 
    )  # (1, word vec size)

    assert gradCenterVec.shape == centerWordVec.shape

    # outer product
    gradOutsideVecs = np.outer(y_hat, centerWordVec)  # (vocab size, word vec size)
    gradOutsideVecs[outsideWordIdx] -= centerWordVec

    assert gradOutsideVecs.shape == outsideVectors.shape

    ### END YOUR CODE

    return loss, gradCenterVec, gradOutsideVecs


def getNegativeSamples(outsideWordIdx, dataset, K):
    """ Samples K indexes which are not the outsideWordIdx """

    # NOTE : the check here is for the K samples not to
    #        overlap with the chosen outside word, but in fact
    #        shouldn't the overlap check be for the entire windows?

    negSampleWordIndices = [None] * K
    for k in range(K):
        newidx = dataset.sampleTokenIdx()
        while newidx == outsideWordIdx:
            newidx = dataset.sampleTokenIdx()
        negSampleWordIndices[k] = newidx
    return negSampleWordIndices


def negSamplingLossAndGradient(
    centerWordVec,
    outsideWordIdx,
    outsideVectors,
    dataset,
    K=10
):
    """ Negative sampling loss function for word2vec models

    Implement the negative sampling loss and gradients for a centerWordVec
    and a outsideWordIdx word vector as a building block for word2vec
    models. K is the number of negative samples to take.

    Note: The same word may be negatively sampled multiple times. For
    example if an outside word is sampled twice, you shall have to
    double count the gradient with respect to this word. Thrice if
    it was sampled three times, and so forth.

    Arguments/Return Specifications: same as naiveSoftmaxLossAndGradient
    """

    # Negative sampling of words is done for you. Do not modify this if you
    # wish to match the autograder and receive points!
    negSampleWordIndices = getNegativeSamples(outsideWordIdx, dataset, K)
    indices = [outsideWordIdx] + negSampleWordIndices

    ### YOUR CODE HERE (~10 Lines)
    ### Please use your implementation of sigmoid in here.

    from collections import Counter
    counts = Counter(negSampleWordIndices)
    # this would be wrong as we want to count multiple samples as much as they are sampled
    # indices = [outsideWordIdx] + list(counts.keys())
    index_counts = np.array([1] + [counts[index] for index in indices[1:]])

    summand_sign = np.ones((len(indices),))
    summand_sign[0] = -summand_sign[0]  # -1 for center word, 1 for rest
    
    u_sub = outsideVectors[indices, :]  # (K+1, word vec size)
    # print(f'u_sub.shape={u_sub.shape}, centerWordVec.shape={centerWordVec.shape}, summand_sign.shape={summand_sign.shape}')
    product = -np.dot(u_sub, centerWordVec) * summand_sign  # (word vec size,) x (K+1, word vec size) = (K+1,)
    sig_product = sigmoid(product)  # (K+1,)
    loss = -np.sum(np.log(sig_product))  # (1,)

    dsig_product = (1-sig_product.copy()) * summand_sign  # (K+1,)
    gradCenterVec = np.dot(dsig_product, u_sub)  # (K+1,) x (K+1, word vec size) = (word vec size,)
    assert gradCenterVec.shape == centerWordVec.shape

    gradOutsideVecs = np.zeros(outsideVectors.shape)
    gradOutsideVecs_sub = np.outer(dsig_product, centerWordVec)  # (K+1,) >< (word vec size,) = (K+1, word vec size)
    assert gradOutsideVecs_sub.shape == u_sub.shape

    gradOutsideVecs[indices, :] = gradOutsideVecs_sub * index_counts.reshape(-1, 1)

    # u_sub = outsideVectors[indices, :]  # (K+1, word vec size)
    # product = centerWordVec @ u_sub.T  # (word vec size,) * (K+1, word vec size) = (K+1,)
    # product[1:] = -product[1:]  # opposite sign for outside/negative words
    # sig_product = sigmoid(product)
    # summand_sign = np.ones(sig_product.shape)
    # summand_sign[0] = -summand_sign[0]
    
    # dsig_product = -sig_product.copy()
    # dsig_product[0] = -dsig_product[0]

    # loss = -np.sum(np.log(sig_product))
    # gradCenterVec = np.sum((np.exp(-product) * dsig_product * summand_sign * u_sub.T).T, axis=0)  # broadcasting over u_sub
    # assert gradCenterVec.shape == centerWordVec.shape

    # # outer product
    # gradOutsideVecs = np.zeros(outsideVectors.shape)
    # gradOutsideVecs_sub = np.outer((np.exp(-product) * dsig_product * summand_sign), centerWordVec)
    # assert gradOutsideVecs_sub.shape == u_sub.shape
    # gradOutsideVecs[indices, :] = gradOutsideVecs_sub

    ### END YOUR CODE

    return loss, gradCenterVec, gradOutsideVecs


def skipgram(currentCenterWord, windowSize, outsideWords, word2Ind,
             centerWordVectors, outsideVectors, dataset,
             word2vecLossAndGradient=naiveSoftmaxLossAndGradient):
    """ Skip-gram model in word2vec

    Implement the skip-gram model in this function.

    Arguments:
    currentCenterWord -- a string of the current center word
    windowSize -- integer, context window size
    outsideWords -- list of no more than 2*windowSize strings, the outside words
    word2Ind -- a dictionary that maps words to their indices in
              the word vector list
    centerWordVectors -- center word vectors (as rows) is in shape 
                        (num words in vocab, word vector length) 
                        for all words in vocab (V in pdf handout)
    outsideVectors -- outside vectors is in shape 
                        (num words in vocab, word vector length) 
                        for all words in vocab (U in the pdf handout)
    word2vecLossAndGradient -- the loss and gradient function for
                               a prediction vector given the outsideWordIdx
                               word vectors, could be one of the two
                               loss functions you implemented above.

    Return:
    loss -- the loss function value for the skip-gram model
            (J in the pdf handout)
    gradCenterVec -- the gradient with respect to the center word vector
                     in shape (word vector length, )
                     (dJ / dv_c in the pdf handout)
    gradOutsideVecs -- the gradient with respect to all the outside word vectors
                    in shape (num words in vocab, word vector length) 
                    (dJ / dU)
    """

    loss = 0.0
    gradCenterVecs = np.zeros(centerWordVectors.shape)
    gradOutsideVectors = np.zeros(outsideVectors.shape)

    ### YOUR CODE HERE (~8 Lines)
    # Naive implementation:
    centerWordIdx = word2Ind[currentCenterWord]
    centerWordVec = centerWordVectors[centerWordIdx]
    outsideWordIdxs = [word2Ind[outsideWord] for outsideWord in outsideWords]

    for outsideWordIdx in outsideWordIdxs:
        wordLoss, wordGradCenterVec, wordGradOutsideVecs = word2vecLossAndGradient(
            centerWordVec, outsideWordIdx, outsideVectors, dataset)
        assert wordGradCenterVec.shape == (gradCenterVecs.shape[1],)
        assert gradOutsideVectors.shape == wordGradOutsideVecs.shape
        loss += wordLoss
        gradCenterVecs[centerWordIdx,:] += wordGradCenterVec
        gradOutsideVectors += wordGradOutsideVecs
    ### END YOUR CODE
    
    return loss, gradCenterVecs, gradOutsideVectors


#############################################
# Testing functions below. DO NOT MODIFY!   #
#############################################

def word2vec_sgd_wrapper(word2vecModel, word2Ind, wordVectors, dataset, 
                         windowSize,
                         word2vecLossAndGradient=naiveSoftmaxLossAndGradient):
    batchsize = 50
    loss = 0.0
    grad = np.zeros(wordVectors.shape)
    N = wordVectors.shape[0]
    centerWordVectors = wordVectors[:int(N/2),:]
    outsideVectors = wordVectors[int(N/2):,:]
    for i in range(batchsize):
        windowSize1 = random.randint(1, windowSize)
        centerWord, context = dataset.getRandomContext(windowSize1)

        c, gin, gout = word2vecModel(
            centerWord, windowSize1, context, word2Ind, centerWordVectors,
            outsideVectors, dataset, word2vecLossAndGradient
        )
        loss += c / batchsize
        grad[:int(N/2), :] += gin / batchsize
        grad[int(N/2):, :] += gout / batchsize

    return loss, grad


def test_word2vec():
    """ Test the two word2vec implementations, before running on Stanford Sentiment Treebank """
    dataset = type('dummy', (), {})()
    def dummySampleTokenIdx():
        return random.randint(0, 4)

    def getRandomContext(C):
        tokens = ["a", "b", "c", "d", "e"]
        return tokens[random.randint(0,4)], \
            [tokens[random.randint(0,4)] for i in range(2*C)]
    dataset.sampleTokenIdx = dummySampleTokenIdx
    dataset.getRandomContext = getRandomContext

    random.seed(31415)
    np.random.seed(9265)
    dummy_vectors = normalizeRows(np.random.randn(10,3))
    dummy_tokens = dict([("a",0), ("b",1), ("c",2),("d",3),("e",4)])

    print("==== Gradient check for skip-gram with naiveSoftmaxLossAndGradient ====")
    gradcheck_naive(lambda vec: word2vec_sgd_wrapper(
        skipgram, dummy_tokens, vec, dataset, 5, naiveSoftmaxLossAndGradient),
        dummy_vectors, "naiveSoftmaxLossAndGradient Gradient")
    grad_tests_softmax(skipgram, dummy_tokens, dummy_vectors, dataset)

    print("==== Gradient check for skip-gram with negSamplingLossAndGradient ====")
    gradcheck_naive(lambda vec: word2vec_sgd_wrapper(
        skipgram, dummy_tokens, vec, dataset, 5, negSamplingLossAndGradient),
        dummy_vectors, "negSamplingLossAndGradient Gradient")

    grad_tests_negsamp(skipgram, dummy_tokens, dummy_vectors, dataset, negSamplingLossAndGradient)


if __name__ == "__main__":
    test_word2vec()

