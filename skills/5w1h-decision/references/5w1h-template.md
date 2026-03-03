# 5W1H Complete Template

## Standard Template Format

```markdown
5W1H-{YYYYMMDD}-{HHMMSS}-{random}

Who: {agent} (executor) | rosemary-project-manager (dispatcher)
- Domain: {Responsible class/module}
- Existing: {Search result for duplicates}

What: {Function Name}
- Description: {One sentence}
- Input: {Types}
- Output: {Types}

When: {Event Trigger}
- Trigger: {User action / System event}
- Side Effects: {List}

Where: {Layer / Component}
- Architecture: {Clean Architecture layer}
- UseCase: {Call chain}

Why: {Requirement}
- Requirement ID: {UC-XXX}
- Business Value: {User benefit}

How: [Task Type: {TYPE}] {Strategy}
1. Write failing test
2. Implement to pass test
3. Refactor
4. Integration verification
```

## Quick Reference

| Section | Purpose | Example |
|---------|---------|---------|
| **Who** | Responsibility attribution | `parsley-flutter-developer (executor) \| rosemary-project-manager (dispatcher)` |
| **What** | Single responsibility function | `validateISBN()` |
| **When** | Trigger timing | `Book added event with ISBN` |
| **Where** | Architecture layer | `Domain / Book Aggregate` |
| **Why** | Requirement traceability | `UC-001 Book Addition` |
| **How** | Implementation strategy | `[Task Type: Implementation] TDD steps` |

## Token Generation

### Session Token Format

```text
5W1H-{YYYYMMDD}-{HHMMSS}-{random}
Example: 5W1H-20250925-191735-a7b3c2
```

### Generate Token Script

```bash
# Generate new session token
uv run .claude/skills/5w1h-decision/scripts/generate_token.py

# Validate 5W1H content
uv run .claude/skills/5w1h-decision/scripts/validate_5w1h.py "content"
```
