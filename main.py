# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.


from PyToGraal import PyToGraal


def mccarthy91(l: float, b, c) -> float:
    n = l
    c = 1
    while c != 0:
        c -= 1
        if n > 100:
            n -= 10
        else:
            n += 11
            c += 2
    return n


class A:
    def __init__(self, x):
        self.x = x

    def getx(self):
        return self.x

    def calme(self, y):
        return self.x + y


def add(x, y):
    return x + y


def opaqueCall():
    return 5


def mc(count):
    a = count
    while a > 0:
        y = count
        while y > 0:
            y = y - 1
        a = a - 1
    return count


if __name__ == '__main__':
    print()
    p = PyToGraal(mc)
    p.parse()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
