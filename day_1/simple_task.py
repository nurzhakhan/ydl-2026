def greeting(name):
    """Return a hello message for the given name.

    The pure logic lives here (no input/print) so it can be unit-tested
    without simulating the keyboard or capturing the screen.
    """
    name = name.strip()
    if not name:
        return "Hello, stranger!"
    return f"Hello, {name}!"


def parse_age(age):
    """Turn the raw input string into a whole number.

    Returns the int if `age` is a valid whole number, otherwise None.
    Keeping this pure (no input/print) means we can test it directly
    and reuse it in the re-ask loop below.
    """
    try:
        return int(age.strip())
    except ValueError:
        return None


def ask_age():
    """Keep asking until the user types a valid number, then return it."""
    while True:
        years = parse_age(input("How old are you? "))
        if years is not None:
            return years
        print("That doesn't look like a number. Please try again.")


def main():
    name = input("What is your name? ")
    print(greeting(name))
    years = ask_age()
    print(f"You are {years} years old.")


if __name__ == "__main__":
    main()
