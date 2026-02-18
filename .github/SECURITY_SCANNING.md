# Security Scanning with Trivy

This repository uses [Trivy](https://github.com/aquasecurity/trivy) to scan Docker images for security vulnerabilities.

## Overview

The Trivy security scanning workflow automatically runs on:
- **Pull Requests**: Scans all Docker images when PRs are opened or updated
- **Nightly Builds**: Runs daily at 2AM UTC after the CI build completes
- **Manual Trigger**: Can be run on-demand via GitHub Actions

## What Gets Scanned

The workflow scans all SonarQube Docker images:
1. **Developer Edition** (`commercial-editions/developer`)
2. **Enterprise Edition** (`commercial-editions/enterprise`)
3. **Data Center App** (`commercial-editions/datacenter/app`)
4. **Data Center Search** (`commercial-editions/datacenter/search`)
5. **Community Edition** (`community-build`)

## Scan Types

### 1. Dockerfile Configuration Scan
- Scans Dockerfile for misconfigurations
- Checks for security best practices
- Reports issues like running as root, exposed secrets, etc.

### 2. Image Vulnerability Scan
- Builds the Docker image
- Scans OS packages and libraries for known vulnerabilities
- Reports CVEs from the National Vulnerability Database (NVD)

## Understanding Results

### Severity Levels
- **🔴 CRITICAL**: Requires immediate attention
- **🟠 HIGH**: Should be addressed soon
- **🟡 MEDIUM**: Monitor and plan for remediation
- **🔵 LOW**: Informational

### Where to Find Results

1. **GitHub Security Tab**: Detailed SARIF reports (PRIMARY)
   - Navigate to: `Security` → `Code scanning`
   - Filter by edition: `dockerfile-*` or `image-*`
   - Click on alerts for full CVE details, remediation advice, and links to CVE databases
   - **Private to repository maintainers only**

2. **Workflow Logs**: Console output
   - View table-formatted results directly in the workflow run logs
   - Quick overview of vulnerabilities by severity
   - Access via Actions → Trivy Security Scan → build-and-scan-images job

## Configuration

### Ignore Specific Vulnerabilities

To suppress false positives or accepted risks:

1. Add CVE IDs to [`.trivyignore`](../.trivyignore):

```
# Example
CVE-2023-12345  # Not applicable to our use case
CVE-2024-67890  # Accepted risk - documented in ticket JIRA-123
```

2. Always include a justification comment

### Customize Scan Settings

Modify [`.github/trivy.yaml`](.github/trivy.yaml) to adjust:
- Scan timeout
- Directories to skip
- Vulnerability types
- Database update behavior

## Running Scans Locally

### Scan a Dockerfile
```bash
docker run --rm \
  -v $(pwd):/workspace \
  aquasec/trivy:latest \
  config /workspace/commercial-editions/developer/Dockerfile
```

### Scan a Built Image
```bash
# Build the image
docker build -t sonarqube-dev:local commercial-editions/developer

# Scan it
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest \
  image sonarqube-dev:local
```

### Scan with Custom Config
```bash
trivy image \
  --config .github/trivy.yaml \
  --severity CRITICAL,HIGH \
  sonarqube-dev:local
```

## Manual Workflow Trigger

To run a scan manually:

1. Go to: `Actions` → `Trivy Security Scan`
2. Click `Run workflow`
3. Select branch
4. Click `Run workflow`

## Nightly Security Scanning

The workflow automatically runs as part of the nightly build at **2AM UTC**:

1. **CI builds all editions** (push_and_pr.yml)
2. **Security scan runs after builds** (trivy-security-scan.yml)
3. **Results uploaded to Security tab and visible in workflow logs**

### Why Nightly Scans?
- **New CVEs**: Vulnerability databases update daily
- **No disruption**: Runs overnight, doesn't block development
- **Trend monitoring**: Track security posture over time
- **Fresh images**: Scans the latest builds from master branch

### Viewing Nightly Results
- Go to: `Actions` → `CI Scheduled (master nightly)`
- Check the `Security Scan` job logs for table output
- View detailed results in the Security tab
