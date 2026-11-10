# Contributing to AERIS Exposure

Thank you for your interest in contributing to AERIS Exposure! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue on GitHub with:
- A clear, descriptive title
- Steps to reproduce the issue
- Expected vs. actual behavior
- Your environment (Python version, OS, package versions)
- Any relevant error messages or logs

### Suggesting Features

We welcome feature suggestions! Please open an issue describing:
- The feature and its use case
- How it would benefit users
- Any potential implementation considerations

### Contributing Code

1. **Fork the repository** and clone your fork
2. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Set up development environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[all]"
   pip install pytest black ruff mypy  # Development tools
   ```

4. **Make your changes**:
   - Follow the existing code style
   - Add docstrings to new functions/classes
   - Update tests if needed
   - Update documentation (README, docstrings) as necessary

5. **Run tests**:
   ```bash
   pytest tests/
   ```

6. **Check code quality**:
   ```bash
   black aeris.exposure/ tests/  # Format code
   ruff check aeris.exposure/ tests/  # Lint code
   ```

7. **Commit your changes**:
   ```bash
   git commit -m "Description of your changes"
   ```
   - Use clear, descriptive commit messages
   - Reference issue numbers if applicable (e.g., "Fix #123: Description")

8. **Push and create a Pull Request**:
   ```bash
   git push origin feature/your-feature-name
   ```
   - Provide a clear description of your changes
   - Reference any related issues
   - Ensure all tests pass

## Code Style Guidelines

- **Python style**: Follow PEP 8
- **Docstrings**: Use Google-style docstrings
- **Type hints**: Include type hints for function parameters and return values
- **Imports**: Organize imports (stdlib, third-party, local) with blank lines between groups
- **Line length**: Aim for 88 characters (Black default)

## Testing

- Write tests for new functionality
- Ensure all existing tests pass
- Aim for good test coverage
- Use descriptive test names

## Documentation

- Update README.md if adding new features or changing behavior
- Add docstrings to all public functions and classes
- Update examples if API changes

## Pull Request Process

1. Ensure your code follows the style guidelines
2. Make sure all tests pass
3. Update documentation as needed
4. Request review from maintainers
5. Address any feedback
6. Once approved, a maintainer will merge your PR

## Questions?

Feel free to open an issue with questions or reach out to the maintainers.

Thank you for contributing to AERIS Exposure!

