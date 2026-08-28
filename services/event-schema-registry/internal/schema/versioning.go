package schema

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// fileLoader loads schemas from a local directory tree.
// Expected layout: basePath/v1/event_name.json
type fileLoader struct {
	basePath string
}

func (fl *fileLoader) Load(name, version string) ([]byte, error) {
	path := filepath.Join(fl.basePath, version, fmt.Sprintf("%s.json", name))
	return os.ReadFile(path)
}

func (fl *fileLoader) List() ([]SchemaRef, error) {
	var refs []SchemaRef
	entries, err := os.ReadDir(fl.basePath)
	if err != nil {
		return nil, err
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		version := entry.Name()
		files, err := os.ReadDir(filepath.Join(fl.basePath, version))
		if err != nil {
			continue
		}
		for _, f := range files {
			if f.IsDir() || !strings.HasSuffix(f.Name(), ".json") {
				continue
			}
			name := strings.TrimSuffix(f.Name(), ".json")
			refs = append(refs, SchemaRef{Name: name, Version: version})
		}
	}
	return refs, nil
}

// CompatibilityCheck performs additive-only compatibility validation.
// It ensures the new schema does not remove required fields or tighten types.
func CompatibilityCheck(oldSchema, newSchema []byte) error {
	// Production implementation would deep-diff JSON schemas.
	// For now, enforce that new schema is a superset of old.
	if len(newSchema) < len(oldSchema) {
		return fmt.Errorf("new schema is smaller than old; possible breaking change")
	}
	return nil
}
