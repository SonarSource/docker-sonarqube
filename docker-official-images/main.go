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
	var configFilePath string
	configFilePath = "active_versions.json"

	renderOfficialImagesTpl(configFilePath)
}

func renderOfficialImagesTpl(configFilePath string) {
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
		log.Fatalf("Error parsing template file %s: %v", templateFilePath, err)

	}

	outputFileName := "official_images.txt"

	outputFile, err := os.Create(outputFileName)
	if err != nil {
		log.Fatalf("Error creating output file %s: %v", outputFileName, err)

	}
	defer outputFile.Close()

	err = tmpl.Execute(outputFile, allBuildMetadata)
	if err != nil {
		log.Fatalf("Error executing template: %v", err)
	}

	fmt.Println("CLI application finished.")
}
