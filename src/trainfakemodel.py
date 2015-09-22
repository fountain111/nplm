from makeembeddings import *
from processgooglenews import *
import theano
import theano.tensor as T


def train(vocabulary, trainingInput, trainingTargetOutput, defaultWordEmbeddings, learningRate=0.13, epochs=100):
    floatX = theano.config.floatX

    contextSize = trainingInput.shape[1]
    embeddingSize = defaultWordEmbeddings.shape[1]
    outputsCount = len(vocabulary)

    contextIndexes = T.imatrix('contextIndexes')
    wordEmbeddings = theano.shared(defaultWordEmbeddings, name='wordEmbeddings')

    context = wordEmbeddings[contextIndexes]
    context = context.reshape((contextIndexes.shape[0], contextSize * embeddingSize))

    defaultWeight = np.random.randn(contextSize*embeddingSize, outputsCount)
    defaultBias = np.random.randn(outputsCount)

    weight = theano.shared(defaultWeight, name='weight', borrow=True)
    bias = theano.shared(defaultBias, name='bias', borrow=True)

    output = T.nnet.softmax(T.dot(context, weight))
    targetOutput = T.ivector('targetOutput')

    cost = -T.mean(T.log(output)[T.arange(targetOutput.shape[0]), targetOutput])

    parameters = [wordEmbeddings, weight]
    gradients = [T.grad(cost, wrt=p) for p in parameters]
    updates = [(p, p - learningRate * g) for p, g in zip(parameters, gradients)]

    trainModel = theano.function(
        inputs=[contextIndexes, targetOutput],
        outputs=cost,
        updates=updates
    )

    for epoch in xrange(epochs):
        trainModel(trainingInput, trainingTargetOutput)
        log.progress(epoch + 1, epochs)

    log.newline()

    trainedWordEmbeddings = wordEmbeddings.get_value()

    return trainedWordEmbeddings


def sim(left, right, vocabulary, wordEmbeddings):
    leftVector = wordEmbeddings[vocabulary[left]]
    rightVector = wordEmbeddings[vocabulary[right]]

    return cosineSimilarity(leftVector, rightVector)


if __name__ == '__main__':
    pagesDirectoryPath = '../data/Fake'
    pageFilePath = pagesDirectoryPath + '/full.txt'

    A = lambda x, dtype=None: np.asarray(x, dtype=dtype)

    vocabulary, windows = processPage(pageFilePath, bufferSize=100, windowSize=5)
    wordEmbeddings = makeEmbeddings(vocabulary, embeddingSize=2)

    vocabulary = vocabulary
    windows = A(windows)
    input, targetOutput = A(windows[:,:-1], 'int32'), A(windows[:,-1], 'int32')
    wordEmbeddings = A(wordEmbeddings)

    print 'A & a: {0}'.format(sim('A', 'a', vocabulary, wordEmbeddings))
    print 'A & e: {0}'.format(sim('A', 'e', vocabulary, wordEmbeddings))

    trainedWordEmbeddings = train(vocabulary, input, targetOutput, wordEmbeddings, learningRate=0.03, epochs=1000)

    print 'A & a: {0}'.format(sim('A', 'a', vocabulary, trainedWordEmbeddings))
    print 'A & e: {0}'.format(sim('A', 'e', vocabulary, trainedWordEmbeddings))