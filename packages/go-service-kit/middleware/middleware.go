package middleware

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// TracingMiddleware injects trace_id into request context and response headers.
func TracingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		traceID := c.GetHeader("X-Trace-ID")
		if traceID != "" {
			c.Set("trace_id", traceID)
			c.Writer.Header().Set("X-Trace-ID", traceID)
		}
		c.Next()
	}
}

// TimingMiddleware records request latency.
func TimingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		latency := time.Since(start).Milliseconds()
		c.Writer.Header().Set("X-Response-Time-Ms", string(rune(latency)))
	}
}

// RecoveryMiddleware recovers from panics and returns 500.
func RecoveryMiddleware() gin.HandlerFunc {
	return gin.Recovery()
}
