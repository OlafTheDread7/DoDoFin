# utils.py
# Helper functions for input validation

from decimal import Decimal, ROUND_HALF_UP

def get_decimal_input(prompt, allow_negative=False):
    """ Gets non-negative Decimal input from the user, optionally allowing negatives. """
    while True:
        try:
            value_str = input(prompt).strip().replace('$', '').replace(',', '')
            if not value_str:
                 print("Input cannot be empty.")
                 continue
            value = Decimal(value_str)
            if not value.is_finite():
                 print("Invalid input (NaN or Infinity). Please enter a valid number.")
                 continue
            if value >= Decimal('0') or allow_negative:
                return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                print("Value cannot be negative. Please enter zero or a positive number.")
        except Exception as e:
            print(f"Invalid input. Please enter a number. ({e})")

def get_string_input(prompt, allow_empty=False):
     """ Gets string input from the user. """
     while True:
         value = input(prompt).strip()
         if value or allow_empty:
             return value
         elif not allow_empty:
             print("Input cannot be empty.")