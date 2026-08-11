# Numerix Fix

## Milestone Science

### Stabilize quantity parsing

#### Quantity round-trip

## Requirements

- Accept exact decimal strings only

## Assets

- reference table of unit strings

```python
def parse_qty(value: str) -> str:
    return value
```

The critical relation is:

$$E = mc^2$$

and inline $a_0 = 1.0e-6$ must be preserved.
