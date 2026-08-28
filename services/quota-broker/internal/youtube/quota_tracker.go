package youtube

import (
	"fmt"
	"sync"
	"time"
)

// QuotaTracker tracks daily YouTube Data API quota consumption per project.
type QuotaTracker struct {
	mu       sync.RWMutex
	projects map[string]*ProjectQuota
}

// ProjectQuota holds quota state for one API project.
type ProjectQuota struct {
	ProjectID      string
	DailyLimit     int64
	Consumed       int64
	Reserved       int64
	ResetTime      time.Time
	LastUpdated    time.Time
	OperationLog   []OperationRecord
}

// OperationRecord is a single quota consumption event.
type OperationRecord struct {
	Timestamp time.Time `json:"timestamp"`
	Operation string    `json:"operation"`
	Units     int64     `json:"units"`
	ChannelID string    `json:"channel_id"`
	JobID     string    `json:"job_id"`
}

// NewQuotaTracker creates a tracker with default limits.
func NewQuotaTracker() *QuotaTracker {
	return &QuotaTracker{
		projects: map[string]*ProjectQuota{
			"default": {
				ProjectID:  "default",
				DailyLimit: 10000,
				Consumed:   0,
				Reserved:   0,
				ResetTime:  nextPacificMidnight(),
			},
		},
	}
}

// Allocate attempts to reserve quota units for a batch of operations.
func (qt *QuotaTracker) Allocate(projectID string, ops []OperationRecord) (*AllocationResult, error) {
	qt.mu.Lock()
	defer qt.mu.Unlock()

	pq, ok := qt.projects[projectID]
	if !ok {
		return nil, fmt.Errorf("project %s not found", projectID)
	}
	qt.maybeReset(pq)

	var total int64
	for _, op := range ops {
		units := GetUnitCost(op.Operation)
		total += units
	}

	available := pq.DailyLimit - pq.Consumed - pq.Reserved
	if total > available {
		return &AllocationResult{
			ProjectID: projectID,
			Granted:   false,
			Requested: total,
			Available: available,
			Reason:    "insufficient_quota",
		}, nil
	}

	pq.Reserved += total
	pq.LastUpdated = time.Now().UTC()
	return &AllocationResult{
		ProjectID: projectID,
		Granted:   true,
		Requested: total,
		Allocated: total,
		Available: available - total,
	}, nil
}

// Commit moves reserved quota to consumed.
func (qt *QuotaTracker) Commit(projectID string, ops []OperationRecord) error {
	qt.mu.Lock()
	defer qt.mu.Unlock()

	pq := qt.projects[projectID]
	if pq == nil {
		return fmt.Errorf("project %s not found", projectID)
	}
	qt.maybeReset(pq)

	var total int64
	for _, op := range ops {
		units := GetUnitCost(op.Operation)
		total += units
		pq.OperationLog = append(pq.OperationLog, op)
	}
	pq.Reserved -= total
	pq.Consumed += total
	pq.LastUpdated = time.Now().UTC()
	return nil
}

// Release returns reserved quota that was not used.
func (qt *QuotaTracker) Release(projectID string, units int64) error {
	qt.mu.Lock()
	defer qt.mu.Unlock()

	pq := qt.projects[projectID]
	if pq == nil {
		return fmt.Errorf("project %s not found", projectID)
	}
	if pq.Reserved < units {
		return fmt.Errorf("cannot release %d; only %d reserved", units, pq.Reserved)
	}
	pq.Reserved -= units
	pq.LastUpdated = time.Now().UTC()
	return nil
}

// Status returns current quota state.
func (qt *QuotaTracker) Status(projectID string) (*ProjectQuota, error) {
	qt.mu.RLock()
	defer qt.mu.RUnlock()

	pq, ok := qt.projects[projectID]
	if !ok {
		return nil, fmt.Errorf("project %s not found", projectID)
	}
	qt.maybeReset(pq)
	// Return a copy
	copyPQ := *pq
	return &copyPQ, nil
}

func (qt *QuotaTracker) maybeReset(pq *ProjectQuota) {
	now := time.Now().UTC()
	if now.After(pq.ResetTime) {
		pq.Consumed = 0
		pq.Reserved = 0
		pq.ResetTime = nextPacificMidnight()
		pq.OperationLog = nil
	}
}

func nextPacificMidnight() time.Time {
	now := time.Now().UTC()
	loc, _ := time.LoadLocation("America/Los_Angeles")
	pt := now.In(loc)
	tomorrow := time.Date(pt.Year(), pt.Month(), pt.Day()+1, 0, 0, 0, 0, loc)
	return tomorrow.UTC()
}

// AllocationResult is the response from an allocate call.
type AllocationResult struct {
	ProjectID string `json:"project_id"`
	Granted   bool   `json:"granted"`
	Requested int64  `json:"requested"`
	Allocated int64  `json:"allocated"`
	Available int64  `json:"available"`
	Reason    string `json:"reason,omitempty"`
}
