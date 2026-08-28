package schema_test

import (
	"testing"

	"github.com/sentra-aura/event-schema-registry/internal/schema"
)

func TestValidateValidPayload(t *testing.T) {
	// This test requires a schema file to exist. In CI, schemas are mounted.
	// For unit testing, we register schemas in-memory.
	reg := schema.NewRegistry("../../contracts/events")

	// Register a test schema
	testSchema := []byte(`{
		"$schema": "http://json-schema.org/draft-07/schema#",
		"type": "object",
		"properties": {
			"event_type": {"type": "string"},
			"payload": {"type": "object"}
		},
		"required": ["event_type"]
	}`)

	err := reg.RegisterSchema("test.event", "v1", testSchema)
	if err != nil {
		t.Fatalf("failed to register schema: %v", err)
	}

	validPayload := []byte(`{"event_type": "test.event", "payload": {"key": "value"}}`)
	result, err := reg.Validate("test.event", "v1", validPayload)
	if err != nil {
		t.Fatalf("validation failed: %v", err)
	}
	if !result.Valid {
		t.Errorf("expected valid payload, got errors: %v", result.Errors)
	}
}

func TestValidateInvalidPayload(t *testing.T) {
	reg := schema.NewRegistry("../../contracts/events")
	testSchema := []byte(`{
		"$schema": "http://json-schema.org/draft-07/schema#",
		"type": "object",
		"properties": {
			"event_type": {"type": "string"},
			"count": {"type": "integer"}
		},
		"required": ["event_type", "count"]
	}`)

	_ = reg.RegisterSchema("test.event", "v2", testSchema)

	invalidPayload := []byte(`{"event_type": "test.event", "count": "not_an_int"}`)
	result, err := reg.Validate("test.event", "v2", invalidPayload)
	if err != nil {
		t.Fatalf("validation failed: %v", err)
	}
	if result.Valid {
		t.Error("expected invalid payload")
	}
	if len(result.Errors) == 0 {
		t.Error("expected validation errors")
	}
}

func TestSchemaNotFound(t *testing.T) {
	reg := schema.NewRegistry("../../contracts/events")
	_, err := reg.Validate("nonexistent", "v1", []byte(`{}`))
	if err == nil {
		t.Error("expected error for missing schema")
	}
}

func TestCompatibilityCheck(t *testing.T) {
	oldSchema := []byte(`{"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}`)
	newSchema := []byte(`{"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}, "required": ["a"]}`)

	err := schema.CompatibilityCheck(oldSchema, newSchema)
	if err != nil {
		t.Errorf("expected compatible schemas, got: %v", err)
	}

	breakingSchema := []byte(`{"type": "object", "properties": {"a": {"type": "string"}}}`)
	err = schema.CompatibilityCheck(oldSchema, breakingSchema)
	if err == nil {
		t.Error("expected compatibility error for breaking change")
	}
}
