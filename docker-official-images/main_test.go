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
