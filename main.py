# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import unittest


class TestSum(unittest.TestCase):

    def test_quicksort(self):
        p = PyToGraal(quicksort)
        p.parse()
        p.print_pdf("quicksort")

    def test_mccarthy91(self):
        p = PyToGraal(mccarthy91)
        p.parse()
        p.print_pdf("mccarthy91")

    def test_for_loop(self):
        p = PyToGraal(for_loop)
        p.parse()
        p.print_pdf("for_loop")

    def test_list_comp(self):
        p = PyToGraal(list_comp)
        p.parse()
        p.print_pdf("list_comp")


from PyToGraal import PyToGraal


def list_comp(lst):
    return [x+2 for x in lst]

def for_loop(lst):
    count = 0
    for x in lst:
        count += x
    return count


def mccarthy91(l: float) -> float:
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


def quicksort(a, m, n) -> None:
    if n <= m:
        return
    i = m - 1
    j = n
    v = a[n]
    while True:
        i += 1
        while a[i] < v:
            i += 1
        j -= 1
        while a[j] > v:
            i -= 1
        if i >= j:
            break
        x = a[i]
        a[i] = a[j]
        a[j] = x

    x = a[i]
    a[i] = a[n]
    a[n] = x

    quicksort(a, m, j)
    quicksort(a, i + 1, n)


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
    while a < 10:
        y = a
        while y < 10:
            y += 1
        a += 1
    return print(count)


if __name__ == '__main__':
    unittest.main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
