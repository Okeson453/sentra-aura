package api

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/sentra-aura/quota-broker/internal/queue"
	"github.com/sentra-aura/quota-broker/internal/youtube"
)

// Handlers holds HTTP handlers for the quota broker.
type Handlers struct {
	tracker *youtube.QuotaTracker
	pq      *queue.PriorityQueue
}

// NewHandlers creates handlers.
func NewHandlers(t *youtube.QuotaTracker, pq *queue.PriorityQueue) *Handlers {
	return &Handlers{tracker: t, pq: pq}
}

// AllocateQuotaRequest is the body for allocate endpoint.
type AllocateQuotaRequest struct {
	ProjectID string                    `json:"project_id" binding:"required"`
	Ops       []youtube.OperationRecord `json:"ops" binding:"required"`
}

// AllocateQuota attempts to reserve quota.
func (h *Handlers) AllocateQuota(c *gin.Context) {
	var req AllocateQuotaRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	result, err := h.tracker.Allocate(req.ProjectID, req.Ops)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

// QuotaStatus returns current quota state.
func (h *Handlers) QuotaStatus(c *gin.Context) {
	projectID := c.Query("project_id")
	if projectID == "" {
		projectID = "default"
	}
	status, err := h.tracker.Status(projectID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, status)
}

// ReleaseQuotaRequest is the body for release endpoint.
type ReleaseQuotaRequest struct {
	ProjectID string `json:"project_id" binding:"required"`
	Units     int64  `json:"units" binding:"required"`
}

// ReleaseQuota returns unused reserved quota.
func (h *Handlers) ReleaseQuota(c *gin.Context) {
	var req ReleaseQuotaRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if err := h.tracker.Release(req.ProjectID, req.Units); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"released": req.Units, "project_id": req.ProjectID})
}

// EnqueueRequestRequest is the body for enqueue endpoint.
type EnqueueRequestRequest struct {
	ID        string                    `json:"id" binding:"required"`
	ProjectID string                    `json:"project_id" binding:"required"`
	Priority  queue.Priority            `json:"priority"`
	Ops       []youtube.OperationRecord `json:"ops" binding:"required"`
}

// EnqueueRequest adds a batch to the priority queue.
func (h *Handlers) EnqueueRequest(c *gin.Context) {
	var req EnqueueRequestRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	h.pq.Enqueue(&queue.QuotaRequest{
		ID:        req.ID,
		ProjectID: req.ProjectID,
		Priority:  req.Priority,
		Ops:       req.Ops,
		Enqueued:  time.Now().UTC(),
	})
	c.JSON(http.StatusAccepted, gin.H{"enqueued": true, "id": req.ID})
}
