package queue_test

import (
	"testing"

	"github.com/sentra-aura/quota-broker/internal/queue"
	"github.com/sentra-aura/quota-broker/internal/youtube"
)

func TestPriorityQueueOrdering(t *testing.T) {
	pq := queue.NewPriorityQueue()

	pq.Enqueue(&queue.QuotaRequest{
		ID:       "low",
		Priority: queue.PriorityLow,
		Ops:      []youtube.OperationRecord{{Operation: "videos.list"}},
	})
	pq.Enqueue(&queue.QuotaRequest{
		ID:       "critical",
		Priority: queue.PriorityCritical,
		Ops:      []youtube.OperationRecord{{Operation: "videos.list"}},
	})
	pq.Enqueue(&queue.QuotaRequest{
		ID:       "normal",
		Priority: queue.PriorityNormal,
		Ops:      []youtube.OperationRecord{{Operation: "videos.list"}},
	})

	first := pq.Dequeue()
	if first == nil || first.ID != "critical" {
		t.Errorf("expected critical first, got: %v", first)
	}

	second := pq.Dequeue()
	if second == nil || second.ID != "normal" {
		t.Errorf("expected normal second, got: %v", second)
	}

	third := pq.Dequeue()
	if third == nil || third.ID != "low" {
		t.Errorf("expected low third, got: %v", third)
	}
}

func TestPriorityQueueEmpty(t *testing.T) {
	pq := queue.NewPriorityQueue()
	item := pq.Dequeue()
	if item != nil {
		t.Error("expected nil from empty queue")
	}
}
