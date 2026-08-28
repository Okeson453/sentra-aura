package observability

import (
	"context"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// Tracer wraps OpenTelemetry tracer.
type Tracer struct {
	tracer trace.Tracer
}

// NewTracer creates a new Tracer.
func NewTracer(serviceName string) *Tracer {
	return &Tracer{
		tracer: otel.Tracer(serviceName),
	}
}

// StartSpan starts a new span.
func (t *Tracer) StartSpan(ctx context.Context, name string, attrs ...attribute.KeyValue) (context.Context, trace.Span) {
	return t.tracer.Start(ctx, name, trace.WithAttributes(attrs...))
}

// RecordLatency records latency as a span attribute.
func RecordLatency(span trace.Span, latency time.Duration) {
	span.SetAttributes(attribute.Float64("latency_ms", float64(latency.Milliseconds())))
}
