package api

import (
	"encoding/json"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/sentra-aura/event-schema-registry/internal/schema"
)

// Handlers holds HTTP handlers for the schema registry.
type Handlers struct {
	registry *schema.SchemaRegistry
}

// NewHandlers creates handlers backed by the given registry.
func NewHandlers(r *schema.SchemaRegistry) *Handlers {
	return &Handlers{registry: r}
}

// ValidateEvent validates a single event payload.
func (h *Handlers) ValidateEvent(c *gin.Context) {
	var req struct {
		EventType string          `json:"event_type" binding:"required"`
		Version   string          `json:"version" binding:"required"`
		Payload   json.RawMessage `json:"payload" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	result, err := h.registry.Validate(req.EventType, req.Version, req.Payload)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	status := http.StatusOK
	if !result.Valid {
		status = http.StatusUnprocessableEntity
	}
	c.JSON(status, result)
}

// ListSchemas returns all available schemas.
func (h *Handlers) ListSchemas(c *gin.Context) {
	refs, err := h.registry.List()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"schemas": refs})
}

// GetSchema returns a raw schema document.
func (h *Handlers) GetSchema(c *gin.Context) {
	name := c.Param("name")
	version := c.Param("version")
	raw, err := h.registry.GetSchema(name, version)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.Data(http.StatusOK, "application/json", raw)
}

// RegisterSchema accepts a new schema document.
func (h *Handlers) RegisterSchema(c *gin.Context) {
	name := c.Param("name")
	version := c.Param("version")
	raw, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot read body"})
		return
	}
	if err := h.registry.RegisterSchema(name, version, raw); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, gin.H{"schema": name, "version": version, "registered": true})
}
