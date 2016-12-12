import traceback


def test():
    raise ValueError()


if __name__ == '__main__':
    try:
        test()
    except ValueError:
        print traceback.format_exc()
