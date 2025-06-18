package main

import (
	"fmt"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/build"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/config"
	"github.com/SonarSource/docker-sonarqube/docker-official-images/internal/fetcher"
	"log"
	"os"
	"text/template"
)

// main is the entry point of the CLI application.
func main() {
	configFilePath := "active_versions.json"

	activeConfigs, err := config.ParseConfigFile(configFilePath)
	if err != nil {
		log.Fatalf("Error reading or parsing active versions config: %v", err)
	}

	gitFetcher := fetcher.NewGitFetcher()

	var allBuildMetadata []build.ImageBuildMetadata
	for _, cfg := range activeConfigs {

		metadataList, err := build.GetBuildMetadataFromConfig(cfg, gitFetcher)
		if err != nil {
			log.Fatalf("Error processing active config for branch %q: %v", cfg.Branch, err)
		}
		allBuildMetadata = append(allBuildMetadata, metadataList...)
	}

	fmt.Printf("Successfully processed %d image build metadata entries.\n", len(allBuildMetadata))

	templateFilePath := "official_images.tmpl"

	tmpl, err := template.ParseFiles(templateFilePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing template file %s: %v\n", templateFilePath, err)
		os.Exit(1)
	}

	outputFileName := "official_images.txt"

	outputFile, err := os.Create(outputFileName)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error creating output file %s: %v\n", outputFileName, err)
		os.Exit(1)
	}
	defer outputFile.Close()

	err = tmpl.Execute(outputFile, allBuildMetadata)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error executing template: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("CLI application finished.")
}
