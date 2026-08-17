# Python

## Type hints

Assume Python >=3.12 unless project config says otherwise.

For type hints, prefer built-in generics and PEP 604 unions where available:

- `list` instead of `typing.List` (same for `dict` and `tuple`)
- `str | None` instead of `Optional[str]`

## Docstrings

Very simple, easy-to-understand functions can use a one-liner docstring (e.g. `"""Raise input 'n' to the power of 2."""`)

For more complex functions, you must use the following docstring format which is a derivative of Google-style docstring convention with some minor changes. Docstring types must match annotations. The example of a valid docstring looks like this:

```python
def my_function(input_1: str, input_2: int | None = None) -> tuple[str, dict[str, str]]:
    """
    <Explanation of the function in imperative mood>

    Args:
        > input_1 (str):
            Description of input_1.
        > input_2 (int | None):
            Description of input_2. Defaults to None.

    Returns:
        - str: <explanation of the first element in the returned tuple>
        - dict[str, str]: <explanation of the second element in the returned tuple>

    Raises:
        - ValueError: When <explanation>
    """
```

*(!)* Note that `> input` style is custom, it's intentional.
