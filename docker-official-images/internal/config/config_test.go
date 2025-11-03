// internal/config/config_test.go
package config_test // We use _test suffix to indicate this is an external test package

import (
	"encoding/json"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/config"
	"os"
	"path/filepath"
	"testing"
)

func TestParseSingleActiveVersionConfig(t *testing.T) {
	// 1. Define a sample JSON input
	jsonInput := `
    {
        "branch": "main",
        "type": "communityBuild",
        "isLatestLTATag": true,
        "isLatestLTSTag": true,
        "isLatest": true,
        "commitSha": "abc123def456"
    }`

	// 2. Declare a variable to hold the unmarshaled data
	var cfg config.ActiveVersionConfig

	// 3. Attempt to unmarshal the JSON
	err := json.Unmarshal([]byte(jsonInput), &cfg)

	// 4. Assertions: What should happen?
	// We expect no error during unmarshalling
	if err != nil {
		t.Fatalf("Failed to unmarshal JSON: %v", err)
	}

	// We expect the fields to be correctly parsed
	if cfg.Branch != "main" {
		t.Errorf("Expected Branch to be 'main', got '%s'", cfg.Branch)
	}
	if cfg.Type != "communityBuild" {
		t.Errorf("Expected Type to be 'communityBuild', got '%s'", cfg.Type)
	}
	if !cfg.IsLatestLTATag {
		t.Errorf("Expected IsLatestLTATag to be true, got false")
	}
	if !cfg.IsLatestLTSTag {
		t.Errorf("Expected IsLatestLTSTag to be true, got false")
	}
	if !cfg.IsLatest {
		t.Errorf("Expected IsLatest to be true, got false")
	}
	if cfg.CommitSHA != "abc123def456" {
		t.Errorf("Expected CommitSHA to be 'abc123def456', got '%s'", cfg.CommitSHA)
	}

	// Test default values for optional fields not provided
	jsonInputNoOptional := `
    {
        "branch": "develop",
        "type": "commercialEditions"
    }`
	var cfgNoOptional config.ActiveVersionConfig
	err = json.Unmarshal([]byte(jsonInputNoOptional), &cfgNoOptional)
	if err != nil {
		t.Fatalf("Failed to unmarshal JSON with optional fields omitted: %v", err)
	}
	if cfgNoOptional.IsLatestLTATag != false {
		t.Errorf("Expected IsLatestLTATag to default to false, got %t", cfgNoOptional.IsLatestLTATag)
	}
	if cfgNoOptional.IsLatestLTSTag != false {
		t.Errorf("Expected IsLatestLTSTag to default to false, got %t", cfgNoOptional.IsLatestLTSTag)
	}
	if cfgNoOptional.CommitSHA != "" { // Go's default for string is empty string
		t.Errorf("Expected CommitSHA to default to empty string, got '%s'", cfgNoOptional.CommitSHA)
	}

}

func TestParseMultipleActiveVersionConfigs(t *testing.T) {
	// 1. Define a sample JSON input with an array of objects
	jsonInput := `
    [
        {
            "branch": "main",
            "type": "communityBuild",
            "isLatestLTATag": true
        },
        {
            "branch": "develop",
            "type": "commercialEditions",
            "commitSha": "789def012ghi"
        },
        {
            "branch": "release/1.0",
            "type": "commercialEditions"
        }
    ]`

	// 2. Declare a slice (array) to hold the unmarshaled data
	var configs []config.ActiveVersionConfig

	// 3. Attempt to unmarshal the JSON
	err := json.Unmarshal([]byte(jsonInput), &configs)

	// 4. Assertions:
	// We expect no error during unmarshalling
	if err != nil {
		t.Fatalf("Failed to unmarshal JSON array: %v", err)
	}

	// We expect exactly 3 configurations to be parsed
	if len(configs) != 3 {
		t.Errorf("Expected 3 configurations, got %d", len(configs))
	}

	// Verify the first config
	if configs[0].Branch != "main" {
		t.Errorf("Expected first config's branch to be 'main', got '%s'", configs[0].Branch)
	}
	if configs[0].Type != "communityBuild" {
		t.Errorf("Expected first config's type to be 'communityBuild', got '%s'", configs[0].Type)
	}
	if !configs[0].IsLatestLTATag {
		t.Errorf("Expected first config's IsLatestLTATag to be true, got false")
	}
	if configs[0].CommitSHA != "" { // Should be empty string as not provided
		t.Errorf("Expected first config's CommitSHA to be empty, got '%s'", configs[0].CommitSHA)
	}

	// Verify the second config (checking default for IsLatestLTATag)
	if configs[1].Branch != "develop" {
		t.Errorf("Expected second config's branch to be 'develop', got '%s'", configs[1].Branch)
	}
	if configs[1].Type != "commercialEditions" {
		t.Errorf("Expected second config's type to be 'commercialEditions', got '%s'", configs[1].Type)
	}
	if configs[1].IsLatestLTATag { // Should be false as not provided
		t.Errorf("Expected second config's IsLatestLTATag to be false, got true")
	}
	if configs[1].CommitSHA != "789def012ghi" {
		t.Errorf("Expected second config's CommitSHA to be '789def012ghi', got '%s'", configs[1].CommitSHA)
	}

	// Verify the third config
	if configs[2].Branch != "release/1.0" {
		t.Errorf("Expected third config's branch to be 'release/1.0', got '%s'", configs[2].Branch)
	}
	// ... add more assertions as needed for the third object
}

// TestValidationMandatoryFields tests that mandatory fields are enforced.
func TestValidationMandatoryFields(t *testing.T) {
	tests := []struct {
		name    string
		cfg     config.ActiveVersionConfig
		wantErr bool
	}{
		{
			name: "Valid config",
			cfg: config.ActiveVersionConfig{
				Branch: "main",
				Type:   "communityBuild",
			},
			wantErr: false,
		},
		{
			name: "Missing Branch",
			cfg: config.ActiveVersionConfig{
				Branch: "", // Missing
				Type:   "communityBuild",
			},
			wantErr: true,
		},
		{
			name: "Missing Type",
			cfg: config.ActiveVersionConfig{
				Branch: "main",
				Type:   "", // Missing
			},
			wantErr: true,
		},
		{
			name: "Missing both Branch and Type",
			cfg: config.ActiveVersionConfig{
				Branch: "", // Missing
				Type:   "", // Missing
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.cfg.Validate() // This method doesn't exist yet!
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
			// Optional: If you want to check for specific error messages later,
			// you can add checks like:
			// if tt.wantErr && !strings.Contains(err.Error(), "branch is mandatory") { ... }
		})
	}
}

// TestValidationTypeField tests that the Type field has an allowed value.
func TestValidationTypeField(t *testing.T) {
	tests := []struct {
		name    string
		cfg     config.ActiveVersionConfig
		wantErr bool
	}{
		{
			name: "Valid Type: communityBuild",
			cfg: config.ActiveVersionConfig{
				Branch: "main",
				Type:   "communityBuild",
			},
			wantErr: false,
		},
		{
			name: "Valid Type: commercialEditions",
			cfg: config.ActiveVersionConfig{
				Branch: "main",
				Type:   "commercialEditions",
			},
			wantErr: false,
		},
		{
			name: "Invalid Type: unknown",
			cfg: config.ActiveVersionConfig{
				Branch: "main",
				Type:   "unknown", // Invalid
			},
			wantErr: true,
		},
		{
			name: "Invalid Type: custom",
			cfg: config.ActiveVersionConfig{
				Branch: "main",
				Type:   "custom", // Invalid
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.cfg.Validate() // This method still doesn't exist!
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
			// Optional: check for specific error messages later if needed
		})
	}
}

// TestParseConfigFile tests the parsing of a JSON configuration file.
func TestParseConfigFile(t *testing.T) {
	// 1. Create a temporary directory and a JSON file within it
	tempDir, err := os.MkdirTemp("", "config-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	// Clean up the temporary directory when the test finishes
	defer os.RemoveAll(tempDir)

	configFilePath := filepath.Join(tempDir, "test_config.json")
	jsonContent := `
    [
        {
            "branch": "feature/new",
            "type": "communityBuild"
        },
        {
            "branch": "pathlta",
            "type": "commercialEditions",
            "commitSha": "deadbeef"
        }
    ]`

	// Write the JSON content to the temporary file
	err = os.WriteFile(configFilePath, []byte(jsonContent), 0644) // 0644 is standard file permissions
	if err != nil {
		t.Fatalf("Failed to write temp config file: %v", err)
	}

	configs, err := config.ParseConfigFile(configFilePath)

	// 3. Assertions
	if err != nil {
		t.Fatalf("ParseConfigFile returned an error: %v", err)
	}
	if len(configs) != 2 {
		t.Errorf("Expected 2 configurations, got %d", len(configs))
	}
	if configs[0].Branch != "feature/new" {
		t.Errorf("Expected first config branch 'feature/new', got '%s'", configs[0].Branch)
	}
	if configs[1].CommitSHA != "deadbeef" {
		t.Errorf("Expected second config commitSha 'deadbeef', got '%s'", configs[1].CommitSHA)
	}

	// Test case for invalid JSON (e.g., malformed)
	invalidConfigFilePath := filepath.Join(tempDir, "invalid_config.json")
	invalidJsonContent := `
    [
        {
            "branch": "malformed",
            "type": "communityBuild"
        , // Extra comma makes it invalid JSON
    ]`
	err = os.WriteFile(invalidConfigFilePath, []byte(invalidJsonContent), 0644)
	if err != nil {
		t.Fatalf("Failed to write invalid temp config file: %v", err)
	}

	_, err = config.ParseConfigFile(invalidConfigFilePath)
	if err == nil {
		t.Error("Expected an error for invalid JSON, got nil")
	}

	// Test case for file not found
	_, err = config.ParseConfigFile("non_existent_file.json")
	if err == nil {
		t.Error("Expected an error for non-existent file, got nil")
	}
}
