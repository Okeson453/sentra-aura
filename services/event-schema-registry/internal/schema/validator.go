package schema

import (
	"encoding/json"
	"fmt"
	"sync"

	"github.com/xeipuuv/gojsonschema"
)

// SchemaRegistry holds loaded JSON schemas keyed by name and version.
type SchemaRegistry struct {
	mu      sync.RWMutex
	schemas map[string]*gojsonschema.Schema // key: "name/version"
	loader  SchemaLoader
}

// SchemaLoader abstracts how schemas are loaded from disk or remote.
type SchemaLoader interface {
	Load(name, version string) ([]byte, error)
	List() ([]SchemaRef, error)
}

// SchemaRef identifies a schema.
type SchemaRef struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// ValidationResult is the outcome of validating a payload.
type ValidationResult struct {
	Valid   bool     `json:"valid"`
	Errors  []string `json:"errors,omitempty"`
	Schema  string   `json:"schema"`
	Version string   `json:"version"`
}

// NewRegistry creates a registry and eagerly loads schemas from the loader.
func NewRegistry(basePath string) *SchemaRegistry {
	loader := &fileLoader{basePath: basePath}
	r := &SchemaRegistry{
		schemas: make(map[string]*gojsonschema.Schema),
		loader:  loader,
	}
	_ = r.reload()
	return r
}

// Validate checks a JSON payload against the named schema version.
func (r *SchemaRegistry) Validate(name, version string, payload []byte) (*ValidationResult, error) {
	key := fmt.Sprintf("%s/%s", name, version)
	r.mu.RLock()
	sch, ok := r.schemas[key]
	r.mu.RUnlock()
	if !ok {
		return nil, fmt.Errorf("schema %s not found", key)
	}

	var document interface{}
	if err := json.Unmarshal(payload, &document); err != nil {
		return nil, fmt.Errorf("invalid JSON payload: %w", err)
	}

	result, err := sch.Validate(gojsonschema.NewGoLoader(document))
	if err != nil {
		return nil, fmt.Errorf("validation error: %w", err)
	}

	vr := &ValidationResult{
		Valid:   result.Valid(),
		Schema:  name,
		Version: version,
	}
	if !result.Valid() {
		for _, err := range result.Errors() {
			vr.Errors = append(vr.Errors, err.String())
		}
	}
	return vr, nil
}

// List returns all registered schema references.
func (r *SchemaRegistry) List() ([]SchemaRef, error) {
	return r.loader.List()
}

// GetSchema returns the raw JSON schema document for a name/version.
func (r *SchemaRegistry) GetSchema(name, version string) ([]byte, error) {
	return r.loader.Load(name, version)
}

// RegisterSchema loads and compiles a new schema into the registry.
func (r *SchemaRegistry) RegisterSchema(name, version string, raw []byte) error {
	key := fmt.Sprintf("%s/%s", name, version)
	loader := gojsonschema.NewBytesLoader(raw)
	sch, err := gojsonschema.NewSchema(loader)
	if err != nil {
		return fmt.Errorf("invalid schema: %w", err)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.schemas[key] = sch
	return nil
}

// reload loads all schemas from the loader.
func (r *SchemaRegistry) reload() error {
	refs, err := r.loader.List()
	if err != nil {
		return err
	}
	for _, ref := range refs {
		raw, err := r.loader.Load(ref.Name, ref.Version)
		if err != nil {
			continue
		}
		_ = r.RegisterSchema(ref.Name, ref.Version, raw)
	}
	return nil
}
