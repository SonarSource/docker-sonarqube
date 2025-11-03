// internal/build/build.go
package build

import (
	"bufio"
	"fmt"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/config"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/fetcher"
	"io"
	"regexp"
	"strings"
)

const DOCKERFILE_STR_CONST = "/Dockerfile"

// ImageBuildMetadata represents the processed information for a single Docker image build.
// This will be the output of parsing a Dockerfile and combining it with ActiveVersionConfig info.
type ImageBuildMetadata struct {
	Branch         string
	EditionType    string   // e.g., "developer", "datacenter-app" - derived from Dockerfile path
	Version        string   // e.g., "10.5.0.0", "9.9.3" extracted from Dockerfile
	ImageDirectory string   // e.g., "2025/developer" - derived from version and Dockerfile path
	Tags           []string // e.g., ["2025.3.0-developer", "2025.3-developer", "developer"]
	Architectures  []string // Always ["amd64", "arm64v8"]
	GitCommit      string   // From ActiveVersionConfig or resolved from branch
}

// GetDockerfilePaths function remains the same
func GetDockerfilePaths(editionType string) []string {
	switch editionType {
	case "commercialEditions":
		return []string{
			"commercial-editions/developer/Dockerfile",
			"commercial-editions/enterprise/Dockerfile",
			"commercial-editions/datacenter/app/Dockerfile",
			"commercial-editions/datacenter/search/Dockerfile",
		}
	case "communityBuild":
		return []string{
			"community-build/Dockerfile",
		}
	default:
		return []string{}
	}
}

// GetEditionTypeFromPath extracts the edition type string from a relative Dockerfile path.
func GetEditionTypeFromPath(dockerfilePath string) (string, error) {
	if !strings.HasSuffix(dockerfilePath, DOCKERFILE_STR_CONST) {
		return "", fmt.Errorf("invalid Dockerfile path format: '%s' (must end with /Dockerfile)", dockerfilePath)
	}

	// Remove "/Dockerfile" suffix
	pathWithoutFilename := strings.TrimSuffix(dockerfilePath, DOCKERFILE_STR_CONST)

	// Split the path into components
	parts := strings.Split(pathWithoutFilename, "/")
	if len(parts) == 1 && parts[0] == "" {
		return "", fmt.Errorf("invalid Dockerfile path format: '%s' (no components found)", dockerfilePath)
	}

	// The edition type is typically the last component.
	// However, for "datacenter/app" or "datacenter/search", it's a two-part name.
	lastPart := parts[len(parts)-1]

	// Check for "datacenter" prefix in the second-to-last part
	if len(parts) >= 2 {
		secondToLastPart := parts[len(parts)-2]
		if secondToLastPart == "datacenter" {
			// Combine "datacenter" with the app/search part
			return fmt.Sprintf("datacenter-%s", lastPart), nil
		}
	}

	// Handle "community-build" which maps to just "community"
	if lastPart == "community-build" {
		return "community", nil
	}

	return lastPart, nil
}

func ExtractSonarQubeVersion(r io.Reader) (string, error) {
	re := regexp.MustCompile(`ARG SONARQUBE_VERSION=?\s*(\d+\.\d+\.\d+\.\d+)`)

	scanner := bufio.NewScanner(r) // Use the io.Reader directly
	for scanner.Scan() {
		line := scanner.Text()
		matches := re.FindStringSubmatch(line)
		if len(matches) > 1 {
			return matches[1], nil
		}
	}

	if err := scanner.Err(); err != nil {
		return "", fmt.Errorf("error reading Dockerfile content stream: %w", err)
	}

	return "", fmt.Errorf("SONARQUBE_VERSION not found in Dockerfile content")
}

func GetBuildMetadataFromConfig(cfg config.ActiveVersionConfig, fileFetcher fetcher.FileContentFetcher) ([]ImageBuildMetadata, error) {
	var allMetadata []ImageBuildMetadata

	branchOrCommit := cfg.Branch
	if cfg.CommitSHA != "" {
		branchOrCommit = cfg.CommitSHA
	} else {
		gotSHA, err := fileFetcher.ResolveBranchToSHA(cfg.Branch)
		if err == nil {
			branchOrCommit = gotSHA
		} else {
			return nil, fmt.Errorf("branch '%s' not found and no CommitSHA provided", cfg.Branch)
		}
	}

	relPaths := GetDockerfilePaths(cfg.Type)
	if len(relPaths) == 0 {
		return nil, fmt.Errorf("no Dockerfile paths found for type %q", cfg.Type)
	}

	for _, relPath := range relPaths {
		// Fetch Dockerfile content from the Git repository.
		content, err := fileFetcher.Fetch(branchOrCommit, relPath)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch Dockerfile content for %s/%s: %w", branchOrCommit, relPath, err)
		}

		// Extract SONARQUBE_VERSION from the fetched content.
		reader := strings.NewReader(content)
		version, err := ExtractSonarQubeVersion(reader)
		if err != nil {
			return nil, fmt.Errorf("failed to extract SONARQUBE_VERSION from %s/%s: %w", branchOrCommit, relPath, err)
		}

		// Extract EditionType here
		editionType, err := GetEditionTypeFromPath(relPath)
		if err != nil {
			return nil, fmt.Errorf("failed to determine edition type for '%s': %w", relPath, err)
		}

		// Generate tags based on the version, edition type, and LTS/LTA status.
		tags, err := GenerateTags(version, editionType, cfg.IsLatestLTSTag, cfg.IsLatestLTATag, cfg.IsLatest, cfg.Type)

		if err != nil {
			return nil, fmt.Errorf("GenerateTags(%q, %q, %t, %t, %t, %q) error = %v", version, editionType, cfg.IsLatestLTSTag, cfg.IsLatestLTATag, cfg.IsLatest, cfg.Type, err)
		}

		branch := cfg.Branch
		if strings.HasPrefix(branch, "origin/") {
			branch = strings.Replace(branch, "origin/", "refs/heads/", 1)
		}

		metadata := ImageBuildMetadata{
			Branch:         branch,
			Version:        version,
			Architectures:  []string{"amd64", "arm64v8"},
			GitCommit:      branchOrCommit,
			EditionType:    editionType,
			ImageDirectory: strings.TrimSuffix(relPath, DOCKERFILE_STR_CONST),
			Tags:           tags,
		}

		allMetadata = append(allMetadata, metadata)
	}

	return allMetadata, nil
}

// GenerateTags computes a list of Docker image tags based on version, edition type, and LTA status.
func GenerateTags(version string, editionType string, isLatestLTSTag bool, isLatestLTATag bool, isLatest bool, activeVersiontype string) ([]string, error) {

	if editionType == "" {
		return nil, fmt.Errorf("editionType cannot be empty")
	}

	versionPattern := `^\d+\.\d+\.\d+\.\d+$`
	if matched, err := regexp.MatchString(versionPattern, version); err != nil || !matched {
		return nil, fmt.Errorf("error matching version pattern or invalid version: %w", err)
	}

	majorVersion := strings.Split(version, ".")[0]
	minorVersion := strings.Split(version, ".")[1]
	patchVersion := strings.Split(version, ".")[2]
	buildNumber := strings.Split(version, ".")[3]

	if activeVersiontype == "communityBuild" {
		tags := []string{
			fmt.Sprintf("%s.%s.%s.%s-%s", majorVersion, minorVersion, patchVersion, buildNumber, editionType),
			fmt.Sprintf("community"),
			fmt.Sprintf("latest"),
		}
		return tags, nil
	}
	if activeVersiontype == "commercialEditions" {
		tags := []string{
			fmt.Sprintf("%s.%s.%s-%s", majorVersion, minorVersion, patchVersion, editionType),
			fmt.Sprintf("%s.%s-%s", majorVersion, minorVersion, editionType),
		}
		if isLatestLTATag {
			// Special case for 2025.1 - use major version only for LTA tag
			if majorVersion == "2025" && minorVersion == "1" {
				tags = append(tags, fmt.Sprintf("%s-lta-%s", majorVersion, editionType))
			} else {
				tags = append(tags, fmt.Sprintf("%s.%s-lta-%s", majorVersion, minorVersion, editionType))
			}
		}
		if isLatest {
			tags = append(tags, fmt.Sprintf("%s", editionType))
		}
		return tags, nil
	}

	return nil, fmt.Errorf("Unsupported activeVersiontype: %s", activeVersiontype)
}
