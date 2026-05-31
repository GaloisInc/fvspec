from test2 import *

def calculate_mean(numbers):
    if not numbers:  
        return None
    total_sum = sum(numbers)  
    count = calculate_length(numbers)      
    mean = total_sum / count  
    return mean

def print_random():
    print("I am an irrelevant function!")

from hypothesis import given, strategies as st
import unittest

class TestCalculateMean(unittest.TestCase):

    @given(st.lists(st.integers(), min_size=1))
    def test_mean_of_non_empty_list(self, numbers):
        # Test that the mean is calculated correctly for non-empty lists
        expected_mean = sum(numbers) / len(numbers)
        calculated_mean = calculate_mean(numbers)
        self.assertAlmostEqual(calculated_mean, expected_mean, places=5)

    @given(st.lists(st.integers()))
    def test_mean_of_empty_list(self, numbers):
        # Test that None is returned for empty lists
        if not numbers:
            self.assertIsNone(calculate_mean(numbers))
        else:
            self.assertIsNotNone(calculate_mean(numbers))

    @given(st.lists(st.just(42), min_size=1))  # All elements are 42
    def test_mean_of_constant_elements(self, numbers):
        # Test that the mean of a list of identical elements is the element itself
        self.assertEqual(calculate_mean(numbers), 42)

    @given(st.lists(st.integers(min_value=1, max_value=100), min_size=1))
    def test_type_stability(self, numbers):
        # Test that the result is an integer if it divides evenly
        if sum(numbers) % len(numbers) == 0:
            self.assertIsInstance(calculate_mean(numbers), int)

if __name__ == "__main__":
    unittest.main()
