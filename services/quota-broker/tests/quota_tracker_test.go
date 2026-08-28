package youtube_test

import (
	"testing"

	"github.com/sentra-aura/quota-broker/internal/youtube"
)

func TestAllocateSuccess(t *testing.T) {
	tracker := youtube.NewQuotaTracker()
	ops := []youtube.OperationRecord{
		{Operation: "videos.list"},
		{Operation: "videos.list"},
	}
	result, err := tracker.Allocate("default", ops)
	if err != nil {
		t.Fatalf("allocate failed: %v", err)
	}
	if !result.Granted {
		t.Errorf("expected allocation to be granted, got: %v", result)
	}
	if result.Allocated != 2 {
		t.Errorf("expected 2 units allocated, got %d", result.Allocated)
	}
}

func TestAllocateExceedsQuota(t *testing.T) {
	tracker := youtube.NewQuotaTracker()
	// Request more than the 10,000 daily limit
	ops := make([]youtube.OperationRecord, 10001)
	for i := range ops {
		ops[i] = youtube.OperationRecord{Operation: "videos.list"}
	}
	result, err := tracker.Allocate("default", ops)
	if err != nil {
		t.Fatalf("allocate failed: %v", err)
	}
	if result.Granted {
		t.Error("expected allocation to be denied")
	}
	if result.Reason != "insufficient_quota" {
		t.Errorf("expected insufficient_quota reason, got: %s", result.Reason)
	}
}

func TestCommitAndRelease(t *testing.T) {
	tracker := youtube.NewQuotaTracker()
	ops := []youtube.OperationRecord{{Operation: "videos.insert"}}

	_, _ = tracker.Allocate("default", ops)
	err := tracker.Commit("default", ops)
	if err != nil {
		t.Fatalf("commit failed: %v", err)
	}

	status, err := tracker.Status("default")
	if err != nil {
		t.Fatalf("status failed: %v", err)
	}
	if status.Consumed != 1600 {
		t.Errorf("expected 1600 consumed, got %d", status.Consumed)
	}

	// Release should fail since already committed
	err = tracker.Release("default", 1600)
	if err == nil {
		t.Error("expected release to fail after commit")
	}
}

func TestUnitCosts(t *testing.T) {
	if youtube.GetUnitCost("videos.insert") != 1600 {
		t.Error("expected videos.insert to cost 1600 units")
	}
	if youtube.GetUnitCost("unknown.operation") != 1 {
		t.Error("expected unknown operation to default to 1 unit")
	}
}
