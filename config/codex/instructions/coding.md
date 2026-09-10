# Coding

## General

Adapted from [these guidelines](https://github.com/multica-ai/andrej-karpathy-skills).

- Resolve uncertainty from the repository where possible; state consequential assumptions and ask only when a consequential choice cannot be inferred safely.
- Match the surrounding style and leave unrelated code, comments and formatting alone.
- Remove imports, variables and functions your changes make unused. Leave pre-existing dead code unless its removal is part of the request.
- Define observable success before implementing. For bug fixes: reproduce the failure where practical → verify the fix against that case. Run relevant existing tests and report the results. If reproduction is impractical, explain the evidence and verification limits.

## Python

### Type hints

Assume Python >=3.12 unless project config says otherwise.

For type hints, prefer built-in generics and PEP 604 unions where available:

- `list` instead of `typing.List` (same for `dict` and `tuple`)
- `str | None` instead of `Optional[str]`

### Docstrings

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
