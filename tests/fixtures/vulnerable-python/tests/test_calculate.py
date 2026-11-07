import unittest

from app import calculate


class ArithmeticTests(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(calculate("2 + 3"), 5)

    def test_precedence(self):
        self.assertEqual(calculate("2 + 3 * 4"), 14)

    def test_parentheses(self):
        self.assertEqual(calculate("(2 + 3) * 4"), 20)

    def test_negative_numbers(self):
        self.assertEqual(calculate("-5 + 2"), -3)


if __name__ == "__main__":
    unittest.main()
