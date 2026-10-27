---
trigger: always_on
description: "Universal PEP 8 and function docstring standards for Python"
---

## Python Coding Standards (Universal)

### Critical Rules
- **CRITICAL**: **ALWAYS** follow strict PEP 8 style guidelines for all Python code (snake_case for functions/variables, PascalCase for classes, 4-space indentation, 79–88 character line limits).
- **ALWAYS** include type hints for all function arguments and return values.
- **YOU MUST** document every Python function, method, and class using my preferred docstring format below. **NEVER** leave a function undocumented.
- **NEVER** define global variables, if global variables are needed think about changing it to a class.
- Functions should **ALWAYS** return one type and a single variable. If multiple variables are needed, return them as a list/tuple or dictionary. If different types are needed, use a dataclass or dictionary.
- Functions should **only** perform one action and do one thing well. If a function is doing multiple things, break it down into smaller functions.

### Preferred Function Documentation Format
Use the following template for all Python function docstrings:

```python
def function_name(param1: int, param2: str = "default") -> bool:
    """Brief one-line summary of what the function does.

    Optional extended description explaining complex logic, side effects, 
    or edge cases if necessary.

    Parameters
    ------------
    param1: int  
        Description of the first parameter.
    param2: str
        Description of the second parameter. Defaults to "default".

    Returns
    --------
        bool: boolean object 
            Description of the return value.
    """
```
