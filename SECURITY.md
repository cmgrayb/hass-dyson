# Security Guidelines

## Sensitive Data Management

### ✅ Protected Data Locations

The following directories are **protected** and excluded from version control:

- `.local/` - Contains real device data, API responses, and sensitive test data
- `docker/` - Contains Docker development environment with potential credentials
- `__pycache__/`, `.pytest_cache/`, `.mypy_cache/` - Build artifacts

### 🚨 Data that MUST be kept secure:

1. **Real Device Serial Numbers** - Replace with `MOCK-SERIAL-TEST123` in tests/docs
2. **Authentication Tokens** - Replace with `MOCK-TOKEN-12345`
3. **Email Addresses** - Replace with `test@example.com`  
4. **MQTT Credentials** - Replace with mock credentials
5. **Account IDs** - Replace with `00000000-0000-0000-0000-000000000000`
6. **API Responses** - Store real responses only in `.local/`

### 📁 File Security Status

#### ✅ **SAFE - Mock data only:**
- `tests/fixtures/mock_device_api.json` - Mock device API response
- `tests/test_*.py` - All test files use mock data
- `README.md`, `SETUP.md`, `TESTING.md` - Documentation with mock examples

#### 🔒 **PROTECTED - Real data allowed:**
- `.local/438M_api.json` - Real API response (gitignored)
- `.local/438M_mqtt.txt` - Real MQTT logs (gitignored)
- `docker/` directory - Development logs (gitignored)

### 🛡️ Security Practices

1. **Before committing:** Always run `git status` and verify no `.local/` files are staged
2. **Test data:** Use mock values that look realistic but are clearly fake
3. **Documentation:** Only use obviously fake examples like `MOCK-SERIAL-TEST123`
4. **Real testing:** Keep real device data in `.local/` for development only

### 🔍 Security Verification Commands

Check for sensitive data before committing:

```bash
# Check for Dyson serial number patterns (format: 3Letters-2Letters-3Letters4Numbers1Letter)
grep -r "[0-9A-Z]{3}-[A-Z]{2}-[A-Z]{3}[0-9]{4}[A-Z]" . --exclude-dir=.local --exclude-dir=docker --exclude-dir=.git --exclude-dir=.venv

# Check for email addresses in non-test files  
grep -r "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" . --exclude-dir=.local --exclude-dir=docker --exclude-dir=.git --exclude-dir=.venv --exclude="*test*"

# Check for long authentication tokens (40+ character strings)
grep -r "[A-Z0-9]{40,}" . --exclude-dir=.local --exclude-dir=docker --exclude-dir=.git --exclude-dir=.venv

# Verify .local is gitignored
git check-ignore .local/

# Check staged files don't include sensitive directories  
git diff --staged --name-only | grep -E "^\.(local|docker)/"
```

All checks should return no results or confirm files are ignored.

### 📋 Development Workflow

1. **Local development:** Use real data in `.local/` for testing
2. **Creating tests:** Use mock data from `tests/fixtures/`  
3. **Documentation:** Use obviously fake examples
4. **Before pushing:** Run security verification commands above

**Remember:** If you see real serial numbers or credentials in your commits, stop and sanitize the data!

---

*This security guide is safe for public repositories as it contains no sensitive data, only patterns and procedures for protecting sensitive information.*
