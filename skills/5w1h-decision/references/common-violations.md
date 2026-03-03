# Common Violations and Fixes

## Violation 1: Missing Executor/Dispatcher

### Problem
```markdown
// VIOLATION
Who: parsley-flutter-developer
- Implement ISBN validation
```

**Issue**: Missing executor/dispatcher identification, unclear responsibility separation.

### Solution
```markdown
// FIXED
Who: parsley-flutter-developer (executor) | rosemary-project-manager (dispatcher)
- Domain: BookValidator in Book Aggregate
- Existing: Searched, no duplicate found
```

---

## Violation 2: Missing Task Type

### Problem
```markdown
// VIOLATION
How: TDD implementation strategy
1. Write test
2. Implement
```

**Issue**: No Task Type marker, cannot validate executor appropriateness.

### Solution
```markdown
// FIXED
How: [Task Type: Implementation] TDD implementation strategy
1. Write failing test for ISBN validation
2. Implement BookValidator.validateISBN()
3. Refactor for readability
4. Integrate with AddBookUseCase
```

---

## Violation 3: Main Thread Doing Implementation

### Problem
```markdown
// VIOLATION
Who: rosemary-project-manager (self-execute)
How: [Task Type: Implementation] Build Domain event classes
```

**Issue**: Main thread assigned to Implementation task, violates executor/dispatcher separation.

### Solution
```markdown
// FIXED
Who: parsley-flutter-developer (executor) | rosemary-project-manager (dispatcher)
How: [Task Type: Implementation] Build Domain event classes
```

---

## Violation 4: Avoidance Language

### Problem
```markdown
// VIOLATION
Why: Need to simplify the complex validation
- Using a simpler approach for now
```

**Issue**: Contains avoidance language ("simplify", "for now"), indicates quality compromise.

### Solution
```markdown
// FIXED
Why: UC-001 Book Addition Requirement
- Requirement ID: UC-001
- Business Value: Ensure user input data format correctness
- User Scenario: User manually inputs ISBN and needs immediate validation
```

---

## Avoidance Language Detection Reference

### Blocked Phrases by Category

| Category | Blocked Phrases | Why Blocked |
|----------|-----------------|------------|
| Quality Compromise | "too complex", "workaround", "temporary fix", "quick fix" | Escaping difficulty |
| Simplification | "simpler approach", "easier way", "simplify" | Compromising quality |
| Problem Ignoring | "ignore for now", "skip for now", "deal with later" | Avoiding problem |
| Test Compromise | "simplify test", "lower test standard", "basic test only" | Reducing testing quality |
| Code Escape | "comment out", "disable", "temporarily disable" | Hiding problems |

---

## Violation 5: Missing Requirement Reference

### Problem
```markdown
// VIOLATION
Why: Need to validate user input

```

**Issue**: No requirement ID or business value, vague justification.

### Solution
```markdown
// FIXED
Why: UC-005 ISBN Format Validation
- Requirement ID: UC-005
- Business Value: Prevent invalid data from corrupting database
- User Scenario: User enters ISBN and system validates format before saving
- Document: docs/app-requirements-spec.md#UC-005
```

---

## Quick Compliance Checklist

Before finalizing any 5W1H decision:

- [ ] **Who**: Executor/Dispatcher both identified with `(executor)` and `(dispatcher)` labels
- [ ] **What**: Single responsibility, testable, no overlap with existing functions
- [ ] **When**: Trigger explicitly named, all side effects documented
- [ ] **Where**: Correct architecture layer, UseCase path clear
- [ ] **Why**: Requirement ID present, business value stated, no avoidance language
- [ ] **How**: Task Type present in `[Task Type: XXX]` format, TDD strategy included
- [ ] **Overall**: No avoidance language detected, requirement traceability complete
