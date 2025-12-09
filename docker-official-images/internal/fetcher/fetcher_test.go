// internal/fetcher/fetcher_test.go
package fetcher_test

import (
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/fetcher"
	"testing"
)

// testGitFetcherFetch tests the GitFetcher's ability to fetch file content
// from the current working directory's Git repository.
func TestGitFetcherFetch(t *testing.T) {
	// Define the exact commit SHA and content from your repository
	const testCommitSHA = "08c53884fb331f184f41b07cb502160ca40ea426"
	const testFilePath = "NOTICE.txt"
	const expectedContent = `docker-sonarqube
Copyright (C) 2015-2025 SonarSource Sàrl
mailto:info AT sonarsource DOT com

This product includes software developed at
SonarSource (http://www.sonarsource.com/).
`

	gitFetcher := fetcher.NewGitFetcher() // No arguments, assumes current directory is repo root

	tests := []struct {
		name           string
		branchOrCommit string
		relativePath   string
		wantContent    string
		wantErr        bool
	}{
		{
			name:           "Fetch existing file by specific commit SHA",
			branchOrCommit: testCommitSHA,
			relativePath:   testFilePath,
			wantContent:    expectedContent,
			wantErr:        false,
		},
		{
			name:           "Fetch existing file from 'master' branch (assuming it points to the commit or has this content)",
			branchOrCommit: "origin/master",
			relativePath:   testFilePath,
			wantContent:    expectedContent,
			wantErr:        false,
		},
		{
			name:           "Fetch non-existent file at specific commit",
			branchOrCommit: testCommitSHA,
			relativePath:   "non/existent/file.txt",
			wantContent:    "",
			wantErr:        true,
		},
		{
			name:           "Fetch from non-existent branch/commit ref",
			branchOrCommit: "non-existent-ref",
			relativePath:   testFilePath,
			wantContent:    "",
			wantErr:        true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotContent, err := gitFetcher.Fetch(tt.branchOrCommit, tt.relativePath)

			if (err != nil) != tt.wantErr {
				t.Errorf("Fetch() error = %v, wantErr %v", err, tt.wantErr)
			}
			if gotContent != tt.wantContent {
				t.Errorf("Fetch() gotContent = %q, want %q", gotContent, tt.wantContent)
			}
		})
	}
}

func TestGitFetcherResolveBranchToSHA(t *testing.T) {
	fetcher := fetcher.NewGitFetcher() // GitFetcher will act as GitRefResolver, operating on current repo

	tests := []struct {
		name    string
		branch  string
		wantSHA string
		wantErr bool
	}{
		{
			name:    "Resolve a specific, known commit SHA",
			branch:  "408a6865f494736d3a428e31d964271785f67d77",
			wantSHA: "408a6865f494736d3a428e31d964271785f67d77",
			wantErr: false,
		},
		{
			name:    "Resolve another feature branch",
			branch:  "origin/release/10.8",
			wantSHA: "e871c0c6e82a55e3a7eb0ea59b5307c895c5b010",
			wantErr: false,
		},
		{
			name:    "Resolve non-existent branch",
			branch:  "non-existent-branch-xyz",
			wantSHA: "",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotSHA, err := fetcher.ResolveBranchToSHA(tt.branch)

			if (err != nil) != tt.wantErr {
				t.Errorf("ResolveBranchToSHA() error = %v, wantErr %v", err, tt.wantErr)
			}
			if gotSHA != tt.wantSHA {
				t.Errorf("ResolveBranchToSHA() gotSHA = %q, want %q", gotSHA, tt.wantSHA)
			}
		})
	}
}
