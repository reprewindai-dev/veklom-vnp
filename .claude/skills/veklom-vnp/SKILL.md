```markdown
# veklom-vnp Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the `veklom-vnp` Python repository. You'll learn how to structure your code, follow naming and import conventions, and understand the current testing approach. While no automated workflows are defined, this guide provides suggested commands to streamline common tasks.

## Coding Conventions

### File Naming
- **Style:** snake_case  
  **Example:**  
  ```plaintext
  data_processor.py
  utils/helpers.py
  ```

### Import Style
- **Style:** Relative imports  
  **Example:**  
  ```python
  from .utils import helper_function
  from ..models import DataModel
  ```

### Export Style
- **Style:** Default (no explicit export lists)  
  **Example:**  
  ```python
  # All top-level functions/classes are exported by default
  def process_data(...):
      ...
  ```

### Commit Messages
- **Type:** Freeform (no enforced structure)
- **Average Length:** ~51 characters
- **Prefix Usage:** None enforced

## Workflows

_No automated workflows detected in this repository._

### Suggested: Run Tests
**Trigger:** When you want to run all tests in the project  
**Command:** `/run-tests`

1. Identify all test files matching `*.test.ts` (if any exist).
2. Use your preferred test runner to execute these files.
3. Review the output for failures and fix as needed.

### Suggested: Add a New Module
**Trigger:** When adding new functionality  
**Command:** `/add-module`

1. Create a new Python file using snake_case naming.
2. Use relative imports to reference existing modules.
3. Implement your logic, ensuring top-level functions/classes are accessible.

## Testing Patterns

- **Framework:** Unknown (not detected)
- **File Pattern:** `*.test.ts` (suggests some TypeScript tests may exist, but Python test framework is not specified)
- **Recommendation:**  
  If writing Python tests, use a standard framework like `pytest` and name test files as `test_*.py`.

  **Example:**
  ```python
  # test_data_processor.py
  from .data_processor import process_data

  def test_process_data():
      assert process_data(input) == expected_output
  ```

## Commands
| Command      | Purpose                                      |
|--------------|----------------------------------------------|
| /run-tests   | Run all test files in the project            |
| /add-module  | Create a new Python module with conventions  |
```
