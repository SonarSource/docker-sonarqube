// internal/build/build_test.go

package build_test

import (
	"fmt"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/build"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/config"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/fetcher"
	"reflect"
	"strings"
	"testing"
)

func TestGetDockerfilePaths(t *testing.T) {
	tests := []struct {
		name        string
		editionType string
		wantPaths   []string
	}{
		{
			name:        "Commercial Editions",
			editionType: "commercialEditions",
			wantPaths: []string{
				"commercial-editions/developer/Dockerfile",
				"commercial-editions/enterprise/Dockerfile",
				"commercial-editions/datacenter/app/Dockerfile",
				"commercial-editions/datacenter/search/Dockerfile",
			},
		},
		{
			name:        "Community Build",
			editionType: "communityBuild",
			wantPaths: []string{
				"community-build/Dockerfile",
			},
		},
		{
			name:        "Legacy Build",
			editionType: "legacy",
			wantPaths: []string{
				"9/community/Dockerfile",
				"9/developer/Dockerfile",
				"9/enterprise/Dockerfile",
				"9/datacenter/app/Dockerfile",
				"9/datacenter/search/Dockerfile",
			},
		},
		{
			name:        "Unknown Type",
			editionType: "someOtherType",
			wantPaths:   []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotPaths := build.GetDockerfilePaths(tt.editionType)
			if !reflect.DeepEqual(gotPaths, tt.wantPaths) {
				t.Errorf("GetDockerfilePaths(%q) got = %v, want %v", tt.editionType, gotPaths, tt.wantPaths)
			}
		})
	}
}

const SONAR_EXPECTED_VERSION = "2025.3.0.108892"
const SONAR_EXPECTED_LTS_VERSION = "9.9.8.100196"
const SONAR_DATACENTER_STRING = "datacenter-app"

func TestExtractSonarQubeVersion(t *testing.T) {
	tests := []struct {
		name              string
		dockerfileContent string
		wantVersion       string
		wantErr           bool
	}{
		{
			name: "Valid version line",
			dockerfileContent: `
FROM alpine:latest
ARG SONARQUBE_VERSION=2025.3.0.108892
RUN echo "Hello"
`,
			wantVersion: SONAR_EXPECTED_VERSION,
			wantErr:     false,
		},
		{
			name: "Valid version line with spaces",
			dockerfileContent: `
FROM ubuntu
ARG SONARQUBE_VERSION   9.9.8.100196
`,
			wantVersion: SONAR_EXPECTED_LTS_VERSION,
			wantErr:     false,
		},
		{
			name: "No SONARQUBE_VERSION line",
			dockerfileContent: `
FROM debian
RUN apt-get update
`,
			wantVersion: "",
			wantErr:     true,
		},
		{
			name: "Malformed SONARQUBE_VERSION line",
			dockerfileContent: `
FROM alpine
SONARQUBE_VERSION 1.2.3.4
`,
			wantVersion: "",
			wantErr:     true,
		},
		{
			name:              "Empty content",
			dockerfileContent: "",
			wantVersion:       "",
			wantErr:           true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			reader := strings.NewReader(tt.dockerfileContent)
			gotVersion, err := build.ExtractSonarQubeVersion(reader)

			if (err != nil) != tt.wantErr {
				t.Errorf("ExtractSonarQubeVersion() error = %v, wantErr %v", err, tt.wantErr)
			}
			if gotVersion != tt.wantVersion {
				t.Errorf("ExtractSonarQubeVersion() gotVersion = %q, want %q", gotVersion, tt.wantVersion)
			}
		})
	}
}

func TestGetBuildMetadataFromConfig(t *testing.T) {

	gitFetcher := fetcher.NewGitFetcher()

	tests := []struct {
		name              string
		activeConfig      config.ActiveVersionConfig
		fetcher           fetcher.FileContentFetcher
		wantMetadataCount int
		wantErr           bool
		expectedVersion   string
		expectedCommit    string
	}{
		{
			name: "Commercial Edition - Master Branch",
			activeConfig: config.ActiveVersionConfig{
				Branch: "408a6865f494736d3a428e31d964271785f67d77",
				Type:   "commercialEditions",
			},
			fetcher:           gitFetcher,
			wantMetadataCount: 4,
			wantErr:           false,
			expectedVersion:   SONAR_EXPECTED_VERSION,
			expectedCommit:    "",
		},
		{
			name: "Community Build - Main Branch",
			activeConfig: config.ActiveVersionConfig{
				Branch: "408a6865f494736d3a428e31d964271785f67d77",
				Type:   "communityBuild",
			},
			fetcher:           gitFetcher,
			wantMetadataCount: 1, // 1 Dockerfile for community build
			wantErr:           false,
			expectedVersion:   "25.6.0.109173",
			expectedCommit:    "",
		},
		{
			name: "Legacy - Release 9.9 Branch",
			activeConfig: config.ActiveVersionConfig{
				Branch: "408a6865f494736d3a428e31d964271785f67d77",
				Type:   "legacy",
			},
			fetcher:           gitFetcher,
			wantMetadataCount: 5, // 5 Dockerfiles for legacy
			wantErr:           false,
			expectedVersion:   SONAR_EXPECTED_LTS_VERSION,
			expectedCommit:    "",
		},
		{
			name: "Commercial Edition - Specific Commit",
			activeConfig: config.ActiveVersionConfig{
				Branch:    "ignored-branch", // Branch is ignored if CommitSHA is present
				CommitSHA: "408a6865f494736d3a428e31d964271785f67d77",
				Type:      "commercialEditions",
			},
			fetcher:           gitFetcher,
			wantMetadataCount: 4,
			wantErr:           false,
			expectedVersion:   SONAR_EXPECTED_VERSION,
		},
		{
			name: "Dockerfile Not Found by Fetcher",
			activeConfig: config.ActiveVersionConfig{
				Branch: "non-existent-branch", // No content mapped for this branch
				Type:   "communityBuild",
			},
			fetcher:           fetcher.NewMockFetcher(nil, nil), // A fetcher with no content mapped
			wantMetadataCount: 0,
			wantErr:           true, // Expect an error from fetcher.Fetch
		},
		{
			name: "No Dockerfile Paths For Type",
			activeConfig: config.ActiveVersionConfig{
				Branch: "origin/master",
				Type:   "unknownType", // Will return no paths from GetDockerfilePaths
			},
			fetcher:           gitFetcher,
			wantMetadataCount: 0,
			wantErr:           true, // Expect an error because no paths are found
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotMetadata, err := build.GetBuildMetadataFromConfig(tt.activeConfig, tt.fetcher)

			// Assert error condition first
			if (err != nil) != tt.wantErr {
				t.Errorf("GetBuildMetadataFromConfig() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err != nil { // If an error was expected and matched, we're done for this test case
				if tt.name == "Dockerfile Not Found by Fetcher" && !strings.Contains(err.Error(), "not found and no CommitSHA provided") {
					t.Errorf("Expected 'not found and no CommitSHA provided' error, got: %v", err)
				}
				if tt.name == "No Dockerfile Paths For Type" && !strings.Contains(err.Error(), "no Dockerfile paths found") {
					t.Errorf("Expected 'no Dockerfile paths found' error, got: %v", err)
				}
				return
			}

			// Assert count for successful cases
			if len(gotMetadata) != tt.wantMetadataCount {
				t.Errorf("GetBuildMetadataFromConfig() got %d metadata entries, want %d", len(gotMetadata), tt.wantMetadataCount)
				return
			}

			// For successful cases, assert the content of the first item (or all if needed)
			if tt.wantMetadataCount > 0 { // Only check if metadata was expected
				// Check common fields that should always be correct
				if gotMetadata[0].Branch != tt.activeConfig.Branch {
					t.Errorf("Expected first metadata Branch %q, got %q", tt.activeConfig.Branch, gotMetadata[0].Branch)
				}
				// Check version if an expected version is provided (e.g., for specific version tests)
				if tt.expectedVersion != "" && gotMetadata[0].Version != tt.expectedVersion {
					t.Errorf("Expected first metadata Version %q, got %q", tt.expectedVersion, gotMetadata[0].Version)
				}
				// Architectures should be hardcoded
				if !reflect.DeepEqual(gotMetadata[0].Architectures, []string{"amd64", "arm64v8"}) {
					t.Errorf("Expected first metadata Architectures %v, got %v", []string{"amd64", "arm64v8"}, gotMetadata[0].Architectures)
				}
			}
		})
	}
}

// TestGetEditionTypeFromPath tests the extraction of edition type from a Dockerfile path.
func TestGetEditionTypeFromPath(t *testing.T) {
	tests := []struct {
		name        string
		filePath    string
		wantEdition string
		wantErr     bool
	}{
		{
			name:        "Commercial Developer",
			filePath:    "commercial-editions/developer/Dockerfile",
			wantEdition: "developer",
			wantErr:     false,
		},
		{
			name:        "Commercial Enterprise",
			filePath:    "commercial-editions/enterprise/Dockerfile",
			wantEdition: "enterprise",
			wantErr:     false,
		},
		{
			name:        "Commercial Datacenter App",
			filePath:    "commercial-editions/datacenter/app/Dockerfile",
			wantEdition: SONAR_DATACENTER_STRING, // Note the dash for "datacenter-app"
			wantErr:     false,
		},
		{
			name:        "Commercial Datacenter Search",
			filePath:    "commercial-editions/datacenter/search/Dockerfile",
			wantEdition: "datacenter-search", // Note the dash for "datacenter-search"
			wantErr:     false,
		},
		{
			name:        "Community Build",
			filePath:    "community-build/Dockerfile",
			wantEdition: "community",
			wantErr:     false,
		},
		{
			name:        "Legacy Community (9/community)",
			filePath:    "9/community/Dockerfile",
			wantEdition: "community",
			wantErr:     false,
		},
		{
			name:        "Legacy Developer (9/developer)",
			filePath:    "9/developer/Dockerfile",
			wantEdition: "developer",
			wantErr:     false,
		},
		{
			name:        "Legacy Datacenter App (9/datacenter/app)",
			filePath:    "9/datacenter/app/Dockerfile",
			wantEdition: SONAR_DATACENTER_STRING,
			wantErr:     false,
		},
		{
			name:        "Malformed Path (no Dockerfile suffix)",
			filePath:    "commercial-editions/developer",
			wantEdition: "",
			wantErr:     true, // Expect an error if it doesn't end with Dockerfile
		},
		{
			name:        "Empty Path",
			filePath:    "",
			wantEdition: "",
			wantErr:     true,
		},
		{
			name:        "Invalid Path",
			filePath:    "/Dockerfile",
			wantEdition: "",
			wantErr:     true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotEdition, err := build.GetEditionTypeFromPath(tt.filePath)

			if (err != nil) != tt.wantErr {
				t.Errorf("GetEditionTypeFromPath(%q) error = %v, wantErr %v", tt.filePath, err, tt.wantErr)
			}
			if gotEdition != tt.wantEdition {
				t.Errorf("GetEditionTypeFromPath(%q) gotEdition = %q, want %q", tt.filePath, gotEdition, tt.wantEdition)
			}
		})
	}
}

func TestGenerateTags(t *testing.T) {
	tests := []struct {
		name              string
		version           string
		editionType       string
		isLatestLTSTag    bool
		isLatestLTATag    bool
		isLatest          bool
		activeVersiontype string
		wantTags          []string
		wantErr           bool
	}{
		{
			name:              "Commercial Edition - Developer (Standard)",
			version:           SONAR_EXPECTED_VERSION,
			editionType:       "developer",
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			isLatest:          true,
			activeVersiontype: "commercialEditions",
			wantTags:          []string{"2025.3.0-developer", "2025.3-developer", "developer"},
			wantErr:           false,
		},
		{
			name:              "Commercial Edition - Enterprise (Standard)",
			version:           SONAR_EXPECTED_VERSION,
			editionType:       "enterprise",
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			isLatest:          false,
			activeVersiontype: "commercialEditions",
			wantTags:          []string{"2025.3.0-enterprise", "2025.3-enterprise"},
			wantErr:           false,
		},
		{
			name:              "Commercial Edition - Datacenter App (Standard)",
			version:           SONAR_EXPECTED_VERSION,
			editionType:       SONAR_DATACENTER_STRING,
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			isLatest:          true,
			activeVersiontype: "commercialEditions",
			wantTags:          []string{"2025.3.0-datacenter-app", "2025.3-datacenter-app", "datacenter-app"},
			wantErr:           false,
		},
		{
			name:              "Community Edition (Standard)",
			version:           "25.6.0.109173", // Example from your output
			editionType:       "community",
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			activeVersiontype: "communityBuild",
			wantTags:          []string{"25.6.0.109173-community", "community", "latest"},
			wantErr:           false,
		},
		{
			name:              "Legacy Edition - Community (9.9.8)",
			version:           SONAR_EXPECTED_LTS_VERSION,
			editionType:       "community",
			isLatestLTSTag:    true,
			isLatestLTATag:    false,
			activeVersiontype: "legacy",
			wantTags:          []string{"9.9.8-community", "9.9-community", "9-community", "lts", "lts-community"},
			wantErr:           false,
		},
		{
			name:              "Legacy Edition - Developer (9.9.8)",
			version:           SONAR_EXPECTED_LTS_VERSION,
			editionType:       "developer",
			isLatestLTSTag:    true,
			isLatestLTATag:    false,
			activeVersiontype: "legacy",
			wantTags:          []string{"9.9.8-developer", "9.9-developer", "9-developer", "lts-developer"},
			wantErr:           false,
		},
		{
			name:              "Commercial Edition - Developer (with LTA tag)",
			version:           "2025.1.2.1234",
			editionType:       "developer",
			isLatestLTSTag:    false,
			isLatestLTATag:    true,
			activeVersiontype: "commercialEditions",
			wantTags:          []string{"2025.1.2-developer", "2025.1-developer", "2025-lta-developer"}, // Note: no `developer` only tag
			wantErr:           false,
		},
		{
			name:              "Invalid Version Format",
			version:           "invalid.version",
			editionType:       "developer",
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			activeVersiontype: "commercialEditions",
			wantTags:          nil,
			wantErr:           true, // Expect an error for unparseable version
		},
		{
			name:              "Empty Version",
			version:           "",
			editionType:       "developer",
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			activeVersiontype: "commercialEditions",
			wantTags:          nil,
			wantErr:           true,
		},
		{
			name:              "Empty Edition Type",
			version:           "10.0.0.0",
			editionType:       "",
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			activeVersiontype: "commercialEditions",
			wantTags:          nil,
			wantErr:           true, // Edition type should not be empty
		},
		{
			name:              "Empty Active Version Type",
			version:           "10.0.0.0",
			editionType:       "",
			isLatestLTSTag:    false,
			isLatestLTATag:    false,
			activeVersiontype: "",
			wantTags:          nil,
			wantErr:           true, // Active Version Type should not be empty
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotTags, err := build.GenerateTags(tt.version, tt.editionType, tt.isLatestLTSTag, tt.isLatestLTATag, tt.isLatest, tt.activeVersiontype) // Function call

			if (err != nil) != tt.wantErr {
				t.Errorf("GenerateTags(%q, %q, %t, %t, %t, %q) error = %v, wantErr %v", tt.version, tt.editionType, tt.isLatestLTSTag, tt.isLatestLTATag, tt.isLatest, tt.activeVersiontype, err, tt.wantErr)
			}
			if err == nil && !reflect.DeepEqual(gotTags, tt.wantTags) {
				t.Errorf("GenerateTags(%q, %q, %t, %t, %t, %q) got tags = %v, want %v\nDiff: %s",
					tt.version, tt.editionType, tt.isLatestLTSTag, tt.isLatestLTATag, tt.isLatest, tt.activeVersiontype, gotTags, tt.wantTags,
					strings.Join(diffSlice(gotTags, tt.wantTags), "\n"))
			}
		})
	}
}

// Helper to diff string slices (useful for debugging tag lists)
func diffSlice(got, want []string) []string {
	missing := []string{}
	extra := []string{}

	gotMap := make(map[string]bool)
	for _, s := range got {
		gotMap[s] = true
	}
	wantMap := make(map[string]bool)
	for _, s := range want {
		wantMap[s] = true
	}

	for _, s := range want {
		if !gotMap[s] {
			missing = append(missing, fmt.Sprintf("Missing: %q", s))
		}
	}
	for _, s := range got {
		if !wantMap[s] {
			extra = append(extra, fmt.Sprintf("Extra: %q", s))
		}
	}
	return append(missing, extra...)
}
