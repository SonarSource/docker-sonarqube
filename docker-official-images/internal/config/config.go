// internal/config/config.go
package config

import (
	"encoding/json" // For JSON unmarshalling
	"fmt"           // For error formatting
	"os"            // For file reading
)

type ActiveVersionConfig struct {
	Branch         string `json:"branch"`
	Type           string `json:"type"`
	IsLatestLTSTag bool   `json:"isLatestLTSTag,omitempty"`
	IsLatestLTATag bool   `json:"isLatestLTATag,omitempty"`
	IsLatest       bool   `json:"isLatest,omitempty"`
	CommitSHA      string `json:"commitSha,omitempty"`
}

// Validate checks if the ActiveVersionConfig fields are valid.
// It returns an error if any field is invalid, otherwise nil.
func (c ActiveVersionConfig) Validate() error {
	// Check for mandatory Branch
	if c.Branch == "" {
		return fmt.Errorf("branch is mandatory")
	}

	// Check for mandatory Type
	if c.Type == "" {
		return fmt.Errorf("type is mandatory")
	}

	// Check if Type is one of the allowed values
	allowedTypes := []string{"commercialEditions", "communityBuild", "legacy"}
	typeIsValid := false
	for _, allowedType := range allowedTypes {
		if c.Type == allowedType {
			typeIsValid = true
			break
		}
	}
	if !typeIsValid {
		return fmt.Errorf("invalid type '%s': must be one of %v", c.Type, allowedTypes)
	}

	return nil // All checks passed
}

// ParseConfigFile reads a JSON file from the given path,
// unmarshals it into a slice of ActiveVersionConfig,
// and validates each configuration.
func ParseConfigFile(filePath string) ([]ActiveVersionConfig, error) {
	// 1. Read the file content
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file '%s': %w", filePath, err)
	}

	// 2. Unmarshal the JSON content into a slice of ActiveVersionConfig
	var configs []ActiveVersionConfig
	err = json.Unmarshal(data, &configs)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal JSON from '%s': %w", filePath, err)
	}

	// 3. Validate each configuration object
	// We'll return the first validation error encountered.
	// For more complex error reporting (e.g., all errors at once), we could use a custom error type.
	for i, cfg := range configs {
		if err := cfg.Validate(); err != nil {
			return nil, fmt.Errorf("validation failed for config at index %d (branch '%s'): %w", i, cfg.Branch, err)
		}
	}

	return configs, nil // Return the parsed configurations and no error
}
