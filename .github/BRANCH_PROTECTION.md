# Repository Branch Protection Rules Configuration

#

# This file documents the recommended branch protection settings for this repository.

# These settings should be configured in GitHub repository settings under:

# Settings → Branches → Add rule (for main/develop branches)

#

# Recommended Branch Protection Rules:

#

# ✅ Require a pull request before merging

# - Require approvals: 1

# - Dismiss stale PR approvals when new commits are pushed: ✅

# - Require review from code owners: ✅

# - Restrict pushes that create files that change code owner mapping: ✅

# - Allow specified actors to bypass required pull requests: (none)

#

# ✅ Require status checks to pass before merging

# - Require branches to be up to date before merging: ✅

# - Status checks that are required:

# \* Quick Test Suite (from pr-test.yml)

# \* Test Python 3.13 (from test.yml)

# \* Code Quality Checks (from test.yml)

# \* Build Package (from test.yml)

#

# ✅ Require conversation resolution before merging

#

# ✅ Require signed commits

#

# ✅ Require linear history

#

# ✅ Include administrators

# - Administrators must follow these rules: ✅

#

# ✅ Restrict pushes that create files:

# - Restrict pushes that create files that change this rule: ✅

#

# ✅ Allow force pushes:

# - Everyone: ❌

# - Specify who can force push: (none)

#

# ✅ Allow deletions: ❌

---

# Required Status Checks for PR Merging:

required_status_checks:
strict: true # Require branches to be up to date before merging
contexts: # Core test suite - must pass - "Quick Test Suite" - "Tests" - "Code Coverage Analysis"

    # Code quality - must pass
    - "Code Quality Checks"

    # Build verification - must pass
    - "Build Package"

    # Optional but recommended
    - "Test Coverage Analysis"

# These checks ensure:

# 1. All tests in /tests folder pass (Quick Test Suite)

# 2. Tests pass on primary Python version (Test Python 3.13)

# 3. Code follows quality standards (Code Quality Checks)

# 4. Package builds successfully (Build Package)

# 5. Coverage analysis completes (Test Coverage Analysis)
