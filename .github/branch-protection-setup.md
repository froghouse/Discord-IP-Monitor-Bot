# Branch Protection Setup Guide

This guide provides instructions for configuring GitHub branch protection rules to ensure code quality and prevent direct pushes to the main branch.

## Required Branch Protection Rules

### For `main` branch:

#### Status Checks
Enable "Require status checks to pass before merging" with the following required checks:
- `ci` (main CI workflow)
- `security` (security workflow)
- `code-quality` (linting and formatting)
- `test-matrix (3.11)` (Python 3.11 tests)
- `test-matrix (3.12)` (Python 3.12 tests)  
- `test-matrix (3.13)` (Python 3.13 tests)
- `integration-tests` (integration test suite)
- `performance-tests` (performance benchmarks)
- `build-validation` (build verification)
- `documentation-check` (documentation validation)

#### Additional Settings
- ✅ Require branches to be up to date before merging
- ✅ Restrict pushes that create files larger than 100 MB
- ✅ Require pull request reviews before merging
  - Required number of reviewers: 1
  - ✅ Dismiss stale reviews when new commits are pushed
  - ✅ Require review from code owners (if CODEOWNERS file exists)
- ✅ Include administrators (apply rules to admins too)
- ✅ Allow force pushes: Disabled
- ✅ Allow deletions: Disabled

## GitHub CLI Commands (Alternative Setup)

If you have admin access and GitHub CLI installed, you can configure these programmatically:

```bash
# Enable branch protection for main
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci","security","code-quality","test-matrix (3.11)","test-matrix (3.12)","test-matrix (3.13)","integration-tests","performance-tests","build-validation","documentation-check"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

## Manual Setup Instructions

1. **Navigate to Repository Settings**
   - Go to your GitHub repository
   - Click "Settings" tab
   - Click "Branches" in the left sidebar

2. **Add Branch Protection Rule**
   - Click "Add rule" button
   - Branch name pattern: `main`

3. **Configure Protection Settings**
   - Check "Require status checks to pass before merging"
   - Check "Require branches to be up to date before merging"
   - In the search box, add each required status check listed above
   - Check "Require pull request reviews before merging"
   - Set required reviewers to 1
   - Check "Dismiss stale reviews when new commits are pushed"
   - Check "Include administrators"
   - Leave "Restrict pushes that create files larger than 100 MB" checked
   - Uncheck "Allow force pushes"
   - Uncheck "Allow deletions"

4. **Save Protection Rule**
   - Click "Create" to save the branch protection rule

## Verification

After setting up branch protection:

1. Try to push directly to main (should be blocked)
2. Create a pull request and verify status checks are required
3. Verify that the PR cannot be merged until all checks pass

## Status Check Names Reference

The status check names correspond to job names in the GitHub Actions workflows:

- **ci**: Overall workflow status from `.github/workflows/ci.yml`
- **security**: Security scanning from `.github/workflows/security.yml`  
- **code-quality**: Linting and formatting job
- **test-matrix (X.Y)**: Matrix testing jobs for each Python version
- **integration-tests**: Integration testing job
- **performance-tests**: Performance benchmarking job
- **build-validation**: Build verification job
- **documentation-check**: Documentation validation job

## Troubleshooting

### Status Checks Not Showing
- Run the CI pipeline at least once to register status check names
- Status check names are case-sensitive and must match exactly

### Cannot Push to Main
- This is expected behavior with branch protection enabled
- Create feature branches and submit pull requests instead

### Checks Failing
- Review the CI workflow logs for specific failure details
- Ensure all linting issues are resolved locally before pushing
- Run tests locally with `pytest` before submitting PRs

## Development Workflow

With branch protection enabled, follow this workflow:

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and commit locally
3. Run local tests: `pytest`
4. Run local linting: `ruff check --fix .`
5. Push feature branch: `git push origin feature/my-feature`
6. Create pull request via GitHub web interface
7. Wait for all status checks to pass
8. Request review if required
9. Merge pull request once approved and checks pass

This ensures all code changes go through proper quality gates before reaching the main branch.