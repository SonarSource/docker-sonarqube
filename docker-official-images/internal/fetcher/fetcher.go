// internal/fetcher/fetcher.go
package fetcher

import (
	"bytes"
	"fmt"
	"os/exec"
	"strings"
)

type FileContentFetcher interface {
	Fetch(branchOrCommit, relativePath string) (string, error)
	ResolveBranchToSHA(branchName string) (string, error)
}

type GitFetcher struct {
}

func NewGitFetcher() *GitFetcher {
	return &GitFetcher{}
}

// Fetch retrieves the content of a file from the current local Git repository
// at a specific branch/commit without checking out the local directory.
func (f *GitFetcher) Fetch(branchOrCommit, relativePath string) (string, error) {
	// Use 'git show' to get the content of the file at the specific branch/commit.
	// Format: <ref>:<path_to_file>
	cmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", branchOrCommit, relativePath))

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		return "", fmt.Errorf("failed to fetch content for '%s' from '%s': %w", relativePath, branchOrCommit, err)
	}

	return stdout.String(), nil
}

// ResolveBranchToSHA resolves a branch name (or any Git reference) to its full commit SHA.
func (f *GitFetcher) ResolveBranchToSHA(branchName string) (string, error) {
	cmd := exec.Command("git", "rev-parse", branchName)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		stderrStr := stderr.String()
		if strings.Contains(stderrStr, "unknown revision") || strings.Contains(stderrStr, "bad revision") || strings.Contains(stderrStr, "ambiguous argument") {
			return "", fmt.Errorf("branch or ref '%s' not found: %w", branchName, err)
		}
		return "", fmt.Errorf("failed to resolve ref '%s' to SHA: %w (Stderr: %s)", branchName, err, stderrStr)
	}

	return strings.TrimSpace(stdout.String()), nil // Trim newline from git rev-parse output
}

// mockFetcher implements fetcher.FileContentFetcher for testing purposes.
type mockFetcher struct {
	// A map where key is "branchOrCommit/relativePath" and value is Dockerfile content.
	contents map[string]string
	// Optional: store errors to return for specific fetches
	errors map[string]error
}

// NewMockFetcher creates a new mockFetcher.
func NewMockFetcher(contents map[string]string, errors map[string]error) *mockFetcher {
	if contents == nil {
		contents = make(map[string]string)
	}
	if errors == nil {
		errors = make(map[string]error)
	}
	return &mockFetcher{
		contents: contents,
		errors:   errors,
	}
}

// Fetch implements the fetcher.FileContentFetcher interface for the mock.
func (m *mockFetcher) Fetch(branchOrCommit, relativePath string) (string, error) {
	key := fmt.Sprintf("%s/%s", branchOrCommit, relativePath)
	if err, ok := m.errors[key]; ok && err != nil {
		return "", err
	}
	if content, ok := m.contents[key]; ok {
		return content, nil
	}
	// Simulate content not found for a given branch/path combination
	return "", fmt.Errorf("mock: content not found for %s on %s", relativePath, branchOrCommit)
}

// Fetch implements the fetcher.FileContentFetcher interface for the mock.
func (m *mockFetcher) ResolveBranchToSHA(branchOrCommit string) (string, error) {
	return "", fmt.Errorf("not implemented")
}
