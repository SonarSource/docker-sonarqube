package main

import (
	"log"
	"os"
	"testing"
)

// TestMainFunction provides a basic test for the main function.
func TestMainFunction(t *testing.T) {

	main()

	// Check if the output file was created
	outputFileName := "official_images.txt"
	if _, err := os.Stat(outputFileName); os.IsNotExist(err) {
		t.Fatalf("Output file %s was not created", outputFileName)
	}
	// Clean up the output file after the test
	if err := os.Remove(outputFileName); err != nil {
		log.Printf("Warning: Failed to remove output file %s: %v", outputFileName, err)
	}
}

// Ensure that the output'ed official_images.txt is equal to the contents of
// fixtures/docker-official-sonarqube
func TestOutputFileContent(t *testing.T) {
	renderOfficialImagesTpl("fixtures/active_versions.json")

	expectedContentFile := "fixtures/docker-official-sonarqube"
	// Read the expected content from the fixture file
	expectedContent, err := os.ReadFile(expectedContentFile)
	if err != nil {
		t.Fatalf("Failed to read expected content file %s: %v", expectedContentFile, err)
	}

	// Read the content of the output file
	outputFileName := "official_images.txt"
	content, err := os.ReadFile(outputFileName)
	if err != nil {
		t.Fatalf("Failed to read output file %s: %v", outputFileName, err)
	}

	// Assert that the content matches the expected content
	if string(content) != string(expectedContent) {
		t.Errorf("Output file content does not match expected content.\nExpected:\n%s\nGot:\n%s", expectedContent, content)
	}
	// Clean up the output file after the test
	if err := os.Remove(outputFileName); err != nil {
		log.Printf("Warning: Failed to remove output file %s: %v", outputFileName, err)
	}
}
