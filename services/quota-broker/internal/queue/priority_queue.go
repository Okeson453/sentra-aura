package queue

import (
	"container/heap"
	"sync"
	"time"

	"github.com/sentra-aura/quota-broker/internal/youtube"
)

// Priority defines request urgency.
type Priority int

const (
	PriorityLow Priority = iota
	PriorityNormal
	PriorityHigh
	PriorityCritical
)

// QuotaRequest is a pending API operation batch.
type QuotaRequest struct {
	ID        string                `json:"id"`
	ProjectID string                `json:"project_id"`
	Priority  Priority              `json:"priority"`
	Ops       []youtube.OperationRecord `json:"ops"`
	Enqueued  time.Time             `json:"enqueued"`
	index     int
}

// PriorityQueue implements heap.Interface.
type PriorityQueue struct {
	mu    sync.Mutex
	items []*QuotaRequest
}

// NewPriorityQueue creates an empty priority queue.
func NewPriorityQueue() *PriorityQueue {
	pq := &PriorityQueue{}
	heap.Init(pq)
	return pq
}

// Enqueue adds a request to the queue.
func (pq *PriorityQueue) Enqueue(req *QuotaRequest) {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	req.Enqueued = time.Now().UTC()
	heap.Push(pq, req)
}

// Dequeue removes and returns the highest-priority request.
func (pq *PriorityQueue) Dequeue() *QuotaRequest {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	if pq.Len() == 0 {
		return nil
	}
	return heap.Pop(pq).(*QuotaRequest)
}

// ProcessPending attempts to allocate quota for queued requests.
func (pq *PriorityQueue) ProcessPending(tracker *youtube.QuotaTracker) {
	for {
		req := pq.Dequeue()
		if req == nil {
			break
		}
		result, err := tracker.Allocate(req.ProjectID, req.Ops)
		if err != nil || !result.Granted {
			// Re-queue if not granted (with backoff logic in production)
			pq.Enqueue(req)
			break
		}
		// In production, this would dispatch to a worker.
		_ = tracker.Commit(req.ProjectID, req.Ops)
	}
}

// heap.Interface implementation

func (pq PriorityQueue) Len() int { return len(pq.items) }

func (pq PriorityQueue) Less(i, j int) bool {
	if pq.items[i].Priority != pq.items[j].Priority {
		return pq.items[i].Priority > pq.items[j].Priority
	}
	return pq.items[i].Enqueued.Before(pq.items[j].Enqueued)
}

func (pq PriorityQueue) Swap(i, j int) {
	pq.items[i], pq.items[j] = pq.items[j], pq.items[i]
	pq.items[i].index = i
	pq.items[j].index = j
}

func (pq *PriorityQueue) Push(x interface{}) {
	n := len(pq.items)
	item := x.(*QuotaRequest)
	item.index = n
	pq.items = append(pq.items, item)
}

func (pq *PriorityQueue) Pop() interface{} {
	old := pq.items
	n := len(old)
	item := old[n-1]
	old[n-1] = nil
	item.index = -1
	pq.items = old[:n-1]
	return item
}
