import sys
from datetime import timedelta


def info(message, *args):
    message = str(message)
    message = message.format(*args)
    message = '\r' + message

    sys.stdout.write(message)
    sys.stdout.flush()

    lineBreak()


def lineBreak():
    sys.stdout.write('\n')
    sys.stdout.flush()


def progress(messageFormat, index, count, *args):
    index = float(index)
    count = float(count)
    percentage = 100 * index / count
    percentage = min(100, percentage)
    args = [percentage] + list(args)

    messageFormat = messageFormat.format(*args)
    messageFormat = '\r' + messageFormat

    sys.stdout.write(messageFormat)
    sys.stdout.flush()


def delta(seconds):
        deltaString = str(timedelta(seconds=seconds))
        deltaString = deltaString.split('.')[0]

        return deltaString