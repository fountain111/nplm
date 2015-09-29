import os
import glob
import log
import time
import gzip
import re
import struct
import io
import collections
import math
from datetime import timedelta


class ContextProvider:
    def __init__(self, textFilePath):
        if textFilePath.endswith('gz'):
            self.textFile = gzip.open(textFilePath)
        else:
            self.textFile = open(textFilePath, 'rb')


    def __del__(self):
        self.textFile.close()


    def next(self, contextSize, bufferSize=100):
        buffer = self.textFile.read(bufferSize)
        tail = ''

        while buffer != '':
            buffer = tail + buffer
            buffer = re.split('\.', buffer)

            tail = buffer[-1]

            for sentence in buffer[:-1]:
                words = re.split('\s+', sentence.strip())

                for wordIndex in range(len(words) - contextSize + 1):
                    window = words[wordIndex: wordIndex + contextSize]

                    yield window

            words = re.split('\s+', tail.lstrip())

            buffer = self.textFile.read(bufferSize)

            if len(words) > contextSize * 2 - 1 or buffer == '':
                if buffer != '':
                    tail = ' '.join(words[-contextSize:])
                    words = words[:-contextSize]

                for wordIndex in range(len(words) - contextSize + 1):
                    window = words[wordIndex: wordIndex + contextSize]

                    yield window


def dumpFileVocabulary(vocabulary, vocabularyFilePath):
    if os.path.exists(vocabularyFilePath):
        os.remove(vocabularyFilePath)

    itemsCount = len(vocabulary)
    itemIndex = 0

    with gzip.open(vocabularyFilePath, 'w') as file:
        file.write(struct.pack('i', itemsCount))

        for key, index in vocabulary.items():
            keyLength = len(key)
            keyLength = struct.pack('i', keyLength)
            index = struct.pack('i', index)

            file.write(keyLength)
            file.write(key)
            file.write(index)

            itemIndex += 1
            log.progress('Dumping file vocabulary: {0:.3f}%.', itemIndex, itemsCount)

        file.flush()

        log.lineBreak()


def dumpWordVocabulary(vocabulary, vocabularyFilePath):
    if os.path.exists(vocabularyFilePath):
        os.remove(vocabularyFilePath)

    itemsCount = len(vocabulary)
    itemIndex = 0

    with gzip.open(vocabularyFilePath, 'w') as file:
        file.write(struct.pack('i', itemsCount))

        for key, value in vocabulary.items():
            keyLength = len(key)
            keyLength = struct.pack('i', keyLength)
            index, frequency = value
            index = struct.pack('i', index)
            frequency = struct.pack('i', frequency)

            file.write(keyLength)
            file.write(key)
            file.write(index)
            file.write(frequency)

            itemIndex += 1
            log.progress('Dumping word vocabulary: {0:.3f}%.', itemIndex, itemsCount)

        file.flush()

        log.lineBreak()


def loadFileVocabulary(vocabularyFilePath):
    vocabulary = collections.OrderedDict()

    with gzip.open(vocabularyFilePath, 'rb') as file:
        itemsCount = file.read(4)
        itemsCount = struct.unpack('i', itemsCount)[0]

        for itemIndex in range(0, itemsCount):
            wordLength = file.read(4)
            wordLength = struct.unpack('i', wordLength)[0]

            word = file.read(wordLength)

            index = file.read(4)
            index = struct.unpack('i', index)[0]

            vocabulary[word] = index

            log.progress('Loading file vocabulary: {0:.3f}%.', itemIndex + 1, itemsCount)

        log.info('')

    return vocabulary


def loadWordVocabulary(vocabularyFilePath):
    vocabulary = collections.OrderedDict()

    with gzip.open(vocabularyFilePath, 'rb') as file:
        itemsCount = file.read(4)
        itemsCount = struct.unpack('i', itemsCount)[0]

        for itemIndex in range(0, itemsCount):
            wordLength = file.read(4)
            wordLength = struct.unpack('i', wordLength)[0]

            word = file.read(wordLength)

            index = file.read(4)
            index = struct.unpack('i', index)[0]

            frequency = file.read(4)
            frequency = struct.unpack('i', frequency)[0]

            vocabulary[word] = (index, frequency)

            log.progress('Loading word vocabulary: {0:.3f}%.', itemIndex + 1, itemsCount)

        log.info('')

    return vocabulary


def loadContexts(contextsFilePath):
    contexts = []

    with gzip.open(contextsFilePath, 'rb') as file:
        contextsCount = file.read(4)
        contextsCount = struct.unpack('i', contextsCount)[0]

        contextSize = file.read(4)
        contextSize = struct.unpack('i', contextSize)[0]

        contextSize += 1 # to include file index that preceeds context itself

        format = '{0}i'.format(contextSize)

        for contextIndex in range(0, contextsCount):
            context = file.read(contextSize * 4)
            context = struct.unpack(format, context)

            contexts.append(context)

            contextIndex += 1
            log.progress('Loading contexts: {0:.3f}%.', contextIndex, contextsCount)

        log.lineBreak()

    return contexts


def readWhiteList(whiteListFilePath):
    with open(whiteListFilePath, 'r') as whiteListFile:
        text = whiteListFile.read()
        whiteList = [word for word in re.split('\s+', text) if word]

        return whiteList


pruningStepIndex = 0
def pruneWordVocabulary(wordVocabulary, maxVocabularySize, whiteList):
    global pruningStepIndex

    originalVocabularyLength = len(wordVocabulary)
    prunedVocabularyLength = min(originalVocabularyLength, maxVocabularySize)

    pruningStepsCount = 0
    if originalVocabularyLength > maxVocabularySize:
        pruningStepsCount += originalVocabularyLength * math.log(originalVocabularyLength)
    pruningStepsCount += prunedVocabularyLength * math.log(prunedVocabularyLength)
    pruningStepsCount += prunedVocabularyLength

    def whiteListPriorityComparator(wordInfoX, wordInfoY):
        global pruningStepIndex

        pruningStepIndex += 1
        if pruningStepIndex % 1000:
            log.progress('Pruning word vocabulary: {0:.3f}%.', pruningStepIndex, pruningStepsCount)

        wordX, infoX = wordInfoX
        wordY, infoY = wordInfoY

        wordXIsWhite = wordX in whiteList
        wordYIsWhite = wordY in whiteList

        if wordXIsWhite and wordYIsWhite:
            return 0
        elif wordXIsWhite:
            return -1
        elif wordYIsWhite:
            return 1

        frequencyX = infoX[1]
        frequencyY = infoY[1]

        if frequencyX < frequencyY:
            return 1
        elif frequencyX > frequencyY:
            return -1

        return 0

    prunedWordVocabulary = wordVocabulary.items()

    if originalVocabularyLength > maxVocabularySize:
        prunedWordVocabulary = sorted(prunedWordVocabulary, cmp=whiteListPriorityComparator)
        prunedWordVocabulary = prunedWordVocabulary[:maxVocabularySize]

    def frequencyComparator(wordInfoX, wordInfoY):
        global pruningStepIndex

        pruningStepIndex += 1
        if pruningStepIndex % 1000:
            log.progress('Pruning word vocabulary: {0:.3f}%.', pruningStepIndex, pruningStepsCount)

        wordX, infoX = wordInfoX
        wordY, infoY = wordInfoY

        frequencyX = infoX[1]
        frequencyY = infoY[1]

        if frequencyX < frequencyY:
            return 1
        elif frequencyX > frequencyY:
            return -1

        return 0

    prunedWordVocabulary = sorted(prunedWordVocabulary, cmp=frequencyComparator)
    prunedWordVocabulary = collections.OrderedDict(prunedWordVocabulary)

    wordIndexMap = {}
    for wordIndex, wordInfo in enumerate(prunedWordVocabulary.items()):
        word, info = wordInfo
        previousIndex, wordFrequency = info
        wordIndexMap[previousIndex] = wordIndex

        prunedWordVocabulary[word] = wordIndex, wordFrequency

        log.progress('Pruning word vocabulary: {0:.3f}%.', pruningStepIndex, pruningStepsCount)
        pruningStepIndex += 1

    log.progress('Pruning word vocabulary: {0:.3f}%.', pruningStepsCount, pruningStepsCount)
    log.lineBreak()

    return prunedWordVocabulary, wordIndexMap


def processData(inputDirectoryPath, fileVocabularyPath, wordVocabularyPath, contextsPath, contextSize, maxVocabularySize):
    if os.path.exists(contextsPath):
        os.remove(contextsPath)

    fileVocabulary = collections.OrderedDict()
    wordVocabulary = collections.OrderedDict()

    uncompressedContextsPath = contextsPath + '.uncompressed'

    if os.path.exists(uncompressedContextsPath):
        os.remove(uncompressedContextsPath)

    with open(uncompressedContextsPath, 'wb+') as tempContextsFile:
        tempContextsFile.write(struct.pack('i', 0)) # this is a placeholder for contexts count
        tempContextsFile.write(struct.pack('i', contextSize))

        pathName = inputDirectoryPath + '/*/*.txt.gz'
        textFilePaths = glob.glob(pathName)[:100]
        textFileCount = len(textFilePaths)
        startTime = time.time()

        contextFormat = '{0}i'.format(contextSize + 1)
        contextsCount = 0

        for textFileIndex, textFilePath in enumerate(textFilePaths):
            fileVocabulary[textFilePath] = textFileIndex

            contextProvider = ContextProvider(textFilePath)
            for wordContext in contextProvider.next(contextSize):
                for word in wordContext:
                    if word not in wordVocabulary:
                        wordVocabulary[word] = (len(wordVocabulary), 1)
                    else:
                        wordIndex, frequency = wordVocabulary[word]
                        wordVocabulary[word] = (wordIndex, frequency + 1)

                indexContext = map(lambda w: wordVocabulary[w][0], wordContext)
                indexContext = [textFileIndex] + indexContext

                tempContextsFile.write(struct.pack(contextFormat, *indexContext))
                contextsCount += 1

            textFileName = os.path.basename(textFilePath)
            currentTime = time.time()
            elapsed = currentTime - startTime
            secondsPerFile = elapsed / (textFileIndex + 1)

            log.progress('Reading contexts: {0:.3f}%. Elapsed: {1} ({2:.3f} sec/file). Vocabulary: {3}.',
                         textFileIndex + 1,
                         textFileCount,
                         timedelta(seconds=elapsed),
                         secondsPerFile,
                         len(wordVocabulary))

        log.lineBreak()

        tempContextsFile.seek(0, io.SEEK_SET)
        tempContextsFile.write(struct.pack('i', contextsCount))
        tempContextsFile.flush()

    whiteList = readWhiteList(whiteListPath)
    originalVocabularyLength = len(wordVocabulary)
    prunedWordVocabulary, wordIndexMap = pruneWordVocabulary(wordVocabulary, maxVocabularySize, whiteList)

    log.info('Vocabulary has been pruned. {0} items left out of {1}.', len(prunedWordVocabulary), originalVocabularyLength)

    uncompressedPrunedContextsPath = contextsPath + '.uncompressed-pruned'

    with open(uncompressedContextsPath, 'rb') as tempContextsFile:
        contextsCount = tempContextsFile.read(4)
        contextSize = tempContextsFile.read(4)

        contextsCount = struct.unpack('i', contextsCount)[0]
        contextSize = struct.unpack('i', contextSize)[0]

        format = '{0}i'.format(contextSize + 1) # plus one spot for file index
        bufferSize = (contextSize + 1) * 4
        prunedContextsCount = 0
        with open(uncompressedPrunedContextsPath, 'wb+') as uncompressedPrunedContexts:
            uncompressedPrunedContexts.write(struct.pack('i', 0)) # placeholder for contexts count
            uncompressedPrunedContexts.write(struct.pack('i', contextSize))

            contextIndex = 0
            while contextIndex < contextsCount:
                buffer = tempContextsFile.read(bufferSize)

                context = struct.unpack(format, buffer)
                fileIndex = context[0]
                indexContext = context[1:]

                if all([index in wordIndexMap for index in indexContext]):
                    prunedContextsCount += 1
                    indexContext = map(lambda wordIndex: wordIndexMap[wordIndex], indexContext)
                    context = [fileIndex] + indexContext
                    buffer = struct.pack(format, *context)
                    uncompressedPrunedContexts.write(buffer)

                contextIndex += 1
                log.progress('Pruning contexts: {0:.3f}%. Pruned contexts: {1}. Original contexts: {2}',
                             contextIndex,
                             contextsCount,
                             prunedContextsCount,
                             contextsCount)

            log.lineBreak()

            uncompressedPrunedContexts.seek(0, io.SEEK_SET)
            uncompressedPrunedContexts.write(struct.pack('i', prunedContextsCount))
            uncompressedPrunedContexts.flush()

    with open(uncompressedPrunedContextsPath, 'rb') as uncompressedPrunedContexts:
        contextsCount = uncompressedPrunedContexts.read(4)
        contextSize = uncompressedPrunedContexts.read(4)

        contextsCount = struct.unpack('i', contextsCount)[0]
        contextSize = struct.unpack('i', contextSize)[0]

        format = '{0}i'.format(contextSize + 1) # plus one spot for file index
        bufferSize = (contextSize + 1) * 4
        with gzip.open(contextsPath, 'wb+') as contextsFile:
            contextsFile.write(struct.pack('i', contextsCount))
            contextsFile.write(struct.pack('i', contextSize))

            contextIndex = 0
            while contextIndex < contextsCount:
                buffer = uncompressedPrunedContexts.read(bufferSize)
                contextsFile.write(buffer)

                contextIndex += 1
                log.progress('Compressing contexts: {0:.3f}%.', contextIndex, contextsCount)

            contextsFile.flush()

        log.lineBreak()

    os.remove(uncompressedContextsPath)
    os.remove(uncompressedPrunedContextsPath)

    dumpFileVocabulary(fileVocabulary, fileVocabularyPath)
    dumpWordVocabulary(prunedWordVocabulary, wordVocabularyPath)


if __name__ == '__main__':
    inputDirectoryPath = '../data/Fake/Dumps'
    fileVocabularyPath = '../data/Fake/Processed/file_vocabulary.bin.gz'
    wordVocabularyPath = '../data/Fake/Processed/word_vocabulary.bin.gz'
    contextsPath = '../data/Fake/Processed/contexts.bin.gz'
    contextSize = 5
    maxVocabularySize = 6
    whiteListPath = '../data/Fake/Tools/white_list.txt'

    processData(inputDirectoryPath, fileVocabularyPath, wordVocabularyPath, contextsPath, contextSize, maxVocabularySize)